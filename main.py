# main.py
import os
import secrets
import hashlib
import httpx
import re
import asyncio
import json
import time
from datetime import date, datetime
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, Form, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from scraper import get_product_price, detect_platform, cross_platform_search
from database import (
    insert_price, init_db, get_last_price,
    get_tracked_products_by_email, upsert_user_login, get_trusted_users_count,
    was_alert_sent_recently, log_alert_sent,
    get_price_rows_by_email, get_user_password, update_user_password,
    get_user_data, update_user_picture, get_price_history, delete_tracked_product
)
from email_service import send_price_alert
from scheduler import start_price_scheduler, stop_price_scheduler

from pydantic import BaseModel
from google import genai
from google.genai import types

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI()
IS_SHUTTING_DOWN = False
IS_VERCEL = bool(os.getenv("VERCEL"))
IS_RENDER = bool(os.getenv("RENDER"))
DATA_DIR = os.getenv("DATA_DIR") or "."
UPLOADS_DIR = os.path.join(DATA_DIR, "avatars")
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "false" if IS_RENDER else "true").lower() == "true"

# Serve static assets (logo, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR, check_dir=False), name="uploads")

app.add_middleware(
    SessionMiddleware,
    secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32)),
    max_age    = 60 * 60 * 24 * 7,
    same_site  = "lax",
    https_only = os.getenv("SESSION_HTTPS_ONLY", "true" if IS_RENDER else "false").lower() == "true",
)

templates = Jinja2Templates(directory="templates")


def format_datetime(value, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Format datetime-like values safely for templates."""
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime(fmt)
    if isinstance(value, date):
        return value.strftime(fmt)
    return str(value)


def _json_ready(value):
    """Convert datetime values to strings so template JSON stays portable."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    return value


templates.env.filters["datetimeformat"] = format_datetime

LOGGED_IN_USERS: set = set()

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/auth/google/callback")



@app.middleware("http")
async def suppress_cancelled_error_logs(request: Request, call_next):
    """
    Gracefully handle request cancellation (browser close / Ctrl+C shutdown).
    Prevent noisy ASGI tracebacks for expected cancellation paths.
    """
    try:
        return await call_next(request)
    except asyncio.CancelledError:
        return JSONResponse(
            {"detail": "Request cancelled."},
            status_code=499,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def current_user(request: Request):
    return request.session.get("user")


def require_login(request: Request):
    if not current_user(request):
        return RedirectResponse(url="/login", status_code=302)
    return None


def base_ctx(request: Request, user, active: str = "", extra: dict = None) -> dict:
    """Build template context with variables shared by every page."""
    ctx = {
        "request":         request,
        "user":            user,
        "active":          active,
        "logged_in_count": len(LOGGED_IN_USERS),
        "trusted_count":   get_trusted_users_count(),
        "email_alerts_enabled": bool(os.getenv("RESEND_API_KEY")) and bool(os.getenv("RESEND_FROM_EMAIL") or os.getenv("SENDER_EMAIL")),
    }
    if extra:
        ctx.update(extra)
    return ctx


def _normalize_compare_key(text: str) -> str:
    """Build a loose key so similar product names can be grouped."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", (text or "").lower())
    tokens = [t for t in cleaned.split() if len(t) > 2]
    stop_words = {
        "with", "from", "for", "and", "the", "new", "best", "buy", "edition",
        "india", "online", "inches", "inch", "color", "black", "white", "blue",
    }
    filtered = [t for t in tokens if t not in stop_words]
    return " ".join(filtered[:6]).strip()


def _is_probable_url(value: str) -> bool:
    if not value:
        return False
    return value.startswith("http://") or value.startswith("https://")


def _key_tokens(value: str) -> set:
    return {t for t in _normalize_compare_key(value).split() if t}


def _keys_match(a: str, b: str) -> bool:
    a_key = _normalize_compare_key(a)
    b_key = _normalize_compare_key(b)
    if not a_key or not b_key:
        return False
    if a_key == b_key:
        return True
    a_tokens = set(a_key.split())
    b_tokens = set(b_key.split())
    overlap = len(a_tokens & b_tokens)
    return overlap >= 2


def _safe_get_product_price(url: str):
    """Protect compare API from scraper/bootstrap failures."""
    try:
        return get_product_price(url)
    except Exception:
        return None, None, detect_platform(url) or "unknown", None


# ── Lifecycle ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup_event():
    global IS_SHUTTING_DOWN
    IS_SHUTTING_DOWN = False

    print(f"[Startup] Environment: IS_RENDER={IS_RENDER}, IS_VERCEL={IS_VERCEL}")
    print(f"[Startup] ENABLE_SCHEDULER={ENABLE_SCHEDULER}")
    print(f"[Startup] DATA_DIR={DATA_DIR}")
    print(f"[Startup] Database URL set: {bool(os.getenv('DATABASE_URL'))}")

    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        print(f"[Startup] Created uploads directory: {UPLOADS_DIR}")
    except Exception as e:
        print(f"[Startup] Warning: Could not create uploads directory: {e}")

    try:
        init_db()
        print("[Startup] Database initialized successfully")
    except Exception as e:
        print(f"[Startup] ERROR: Database initialization failed: {e}")
        raise

    if not IS_VERCEL and ENABLE_SCHEDULER:
        print("[Startup] Starting price scheduler...")
        try:
            start_price_scheduler()
            print("[Startup] Price scheduler started successfully")
        except Exception as e:
            print(f"[Startup] ERROR: Failed to start scheduler: {e}")
            raise
    else:
        print("[Startup] Scheduler not started (Vercel mode or disabled)")

    print("[Startup] Ember Noir theme loaded. Application ready.")


@app.on_event("shutdown")
def shutdown_event():
    global IS_SHUTTING_DOWN
    IS_SHUTTING_DOWN = True
    if not IS_VERCEL and ENABLE_SCHEDULER:
        stop_price_scheduler()


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = None):
    if current_user(request):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "request": request,
            "user": None,
            "active": "",
            "error": error,
            "google_enabled": bool(GOOGLE_CLIENT_ID),
        },
    )


@app.post("/login", response_class=HTMLResponse)
def do_login(request: Request, email: str = Form(...), password: str = Form(...)):
    if not email or len(password) < 6:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "user": None,
                "active": "",
                "error": "Password must be at least 6 characters.",
                "google_enabled": bool(GOOGLE_CLIENT_ID),
            },
            status_code=400,
        )

    # Check password logic
    hashed_input = hashlib.sha256(password.encode()).hexdigest()
    user_data = get_user_data(email.lower())
    if user_data:
        if user_data.get("password") and user_data["password"] != hashed_input:
            return templates.TemplateResponse(
                request,
                "login.html",
                {
                    "request": request,
                    "user": None,
                    "active": "",
                    "error": "Incorrect password.",
                    "google_enabled": bool(GOOGLE_CLIENT_ID),
                },
                status_code=400,
            )
    else:
        # First time login with this email, register it
        upsert_user_login(email.lower(), "free", hashed_input)
        user_data = {"picture": None, "provider": "free"}

    request.session["user"] = {
        "email":    email,
        "name":     email.split("@")[0].replace(".", " ").title(),
        "picture":  user_data.get("picture"),
        "provider": "free",
    }
    LOGGED_IN_USERS.add(email.lower())
    
    return RedirectResponse(url="/", status_code=302)


@app.get("/logout")
def logout(request: Request):
    user = current_user(request)
    if user and user.get("email"):
        LOGGED_IN_USERS.discard(user["email"].lower())
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


# ── Google OAuth ──────────────────────────────────────────────────────────────

@app.get("/auth/google")
def google_login(request: Request):
    if not GOOGLE_CLIENT_ID:
        return RedirectResponse(
            url="/login?error=Google+OAuth+not+configured.+Set+GOOGLE_CLIENT_ID.",
            status_code=302,
        )
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    params = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid+email+profile"
        f"&state={state}"
        f"&access_type=offline&prompt=select_account"
    )
    return RedirectResponse(url=params, status_code=302)


@app.get("/auth/google/callback")
async def google_callback(
    request: Request,
    code: str  = None,
    state: str = None,
    error: str = None,
):
    if error or not code:
        return RedirectResponse(url="/login?error=Google+sign-in+cancelled.", status_code=302)
    if state != request.session.get("oauth_state"):
        return RedirectResponse(url="/login?error=OAuth+state+mismatch.", status_code=302)

    async with httpx.AsyncClient() as client:
        token_data = (await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code":          code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  GOOGLE_REDIRECT_URI,
                "grant_type":    "authorization_code",
            },
        )).json()

        if "error" in token_data:
            return RedirectResponse(
                url=f"/login?error=Google+token+error:+{token_data['error']}",
                status_code=302,
            )

        userinfo = (await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )).json()

    request.session["user"] = {
        "email":    userinfo.get("email"),
        "name":     userinfo.get("name"),
        "picture":  userinfo.get("picture"),
        "provider": "google",
    }
    if userinfo.get("email"):
        LOGGED_IN_USERS.add(userinfo["email"].lower())
        upsert_user_login(userinfo["email"].lower(), "google", picture=userinfo.get("picture"))
    request.session.pop("oauth_state", None)
    return RedirectResponse(url="/", status_code=302)


# ══════════════════════════════════════════════════════════════════════════════
#  PROFILE / AVATAR
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/profile/password")
def profile_password(request: Request, old_password: str = Form(...), new_password: str = Form(...)):
    r = require_login(request)
    if r: return r
    user = current_user(request)
    if user["provider"] != "free":
        return templates.TemplateResponse(request, "profile.html", base_ctx(request, user, active="profile", extra={"err": "Google accounts cannot change password here."}))

    db_pw = get_user_password(user["email"])
    if db_pw != hashlib.sha256(old_password.encode()).hexdigest():
        return templates.TemplateResponse(request, "profile.html", base_ctx(request, user, active="profile", extra={"err": "Current password incorrect."}))

    update_user_password(user["email"], hashlib.sha256(new_password.encode()).hexdigest())
    return templates.TemplateResponse(request, "profile.html", base_ctx(request, user, active="profile", extra={"msg": "Password updated successfully!"}))


@app.post("/profile/avatar")
async def profile_avatar(request: Request, avatar: UploadFile = File(...)):
    r = require_login(request)
    if r: return r
    user = current_user(request)
    if IS_VERCEL:
        return RedirectResponse(
            url="/profile?err=Avatar upload is disabled on this Vercel deployment",
            status_code=302,
        )
    
    if not avatar.content_type.startswith("image/"):
        return RedirectResponse(url="/profile?err=Only images allowed", status_code=302)

    try:
        from PIL import Image
        import io
        contents = await avatar.read()
        img = Image.open(io.BytesIO(contents))
        img = img.convert("RGB")
        
        # Center crop and resize to 200x200
        w, h = img.size
        min_dim = min(w, h)
        left = (w - min_dim) / 2
        top = (h - min_dim) / 2
        img = img.crop((left, top, left + min_dim, top + min_dim))
        img = img.resize((200, 200), Image.Resampling.LANCZOS)

        filename = f"{hashlib.sha256(user['email'].encode()).hexdigest()[:12]}.jpg"
        filepath = os.path.join(UPLOADS_DIR, filename)
        img.save(filepath, "JPEG", quality=90)

        url = f"/uploads/{filename}"
        update_user_picture(user["email"], url)
        
        # Update session
        u = request.session["user"]
        u["picture"] = url
        request.session["user"] = u
        
        return RedirectResponse(url="/profile?msg=Avatar updated!", status_code=302)
    except Exception as e:
        return RedirectResponse(url=f"/profile?err=Upload failed: {str(e)[:40]}", status_code=302)

# ══════════════════════════════════════════════════════════════════════════════
#  APP ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    r = require_login(request)
    if r: return r
    return templates.TemplateResponse(
        request,
        "index.html",
        base_ctx(request, current_user(request), active="home"),
    )


@app.get("/health")
def healthcheck():
    """Enhanced health check with scheduler and database status."""
    import time
    from scheduler import scheduler
    from database import get_db, IS_POSTGRES

    health = {
        "status": "ok",
        "timestamp": time.time(),
        "environment": {
            "is_render": IS_RENDER,
            "is_vercel": IS_VERCEL,
            "enable_scheduler": ENABLE_SCHEDULER,
            "database_url_set": bool(os.getenv("DATABASE_URL")),
            "is_postgres": IS_POSTGRES,
            "data_dir": DATA_DIR,
        },
        "scheduler": {
            "enabled": ENABLE_SCHEDULER and not IS_VERCEL,
            "running": scheduler.running if hasattr(scheduler, 'running') else False,
            "jobs": []
        },
        "database": {
            "connection_ok": False,
            "product_count": 0,
            "user_count": 0,
            "alert_count": 0,
        }
    }

    # Check scheduler jobs
    if scheduler.running:
        try:
            jobs = scheduler.get_jobs()
            health["scheduler"]["jobs"] = [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger)
                } for job in jobs
            ]
        except Exception as e:
            health["scheduler"]["error"] = str(e)

    # Check database
    try:
        with get_db() as conn:
            if IS_POSTGRES:
                health["database"]["product_count"] = conn.execute("SELECT COUNT(*) FROM products").fetchone()["count"]
                health["database"]["user_count"] = conn.execute("SELECT COUNT(*) FROM user_logins").fetchone()["count"]
                health["database"]["alert_count"] = conn.execute("SELECT COUNT(*) FROM alert_log").fetchone()["count"]
            else:
                health["database"]["product_count"] = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
                health["database"]["user_count"] = conn.execute("SELECT COUNT(*) FROM user_logins").fetchone()[0]
                health["database"]["alert_count"] = conn.execute("SELECT COUNT(*) FROM alert_log").fetchone()[0]
            health["database"]["connection_ok"] = True
    except Exception as e:
        health["database"]["error"] = str(e)
        health["status"] = "error"

    return health


@app.post("/debug/trigger-price-check")
def debug_trigger_price_check():
    """Debug endpoint to manually trigger price check (requires ENABLE_SCHEDULER=true)."""
    if not ENABLE_SCHEDULER:
        return {"error": "Scheduler is disabled"}

    try:
        from scheduler import check_prices
        import threading

        # Run in background thread to avoid blocking
        thread = threading.Thread(target=check_prices)
        thread.daemon = True
        thread.start()

        return {"status": "Price check triggered in background thread"}

    except Exception as e:
        return {"error": f"Failed to trigger price check: {e}"}


# ── Profile ───────────────────────────────────────────────────────────────────
@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, msg: str = None, err: str = None):
    r = require_login(request)
    if r: return r
    user = current_user(request)
    return templates.TemplateResponse(
        request,
        "profile.html",
        base_ctx(request, user, active="profile", extra={"msg": msg, "err": err}),
    )


# ── Track ─────────────────────────────────────────────────────────────────────

@app.get("/track", response_class=HTMLResponse)
def track_page(request: Request):
    r = require_login(request)
    if r: return r
    user = current_user(request)
    products = get_tracked_products_by_email(user["email"])
    return templates.TemplateResponse(
        request,
        "track.html",
        base_ctx(request, user, active="track", extra={"products": products}),
    )


@app.post("/track", response_class=HTMLResponse)
def fetch_price(
    request:      Request,
    background_tasks: BackgroundTasks,
    product_url:  str = Form(...),
    email:        str = Form(...),
    target_price: int = Form(...),
):
    r = require_login(request)
    if r: return r
    user = current_user(request)

    price_text, price_number, platform, product_name = get_product_price(product_url)

    if price_text and price_number:
        old_price = get_last_price(product_url)

        if old_price is None:
            status  = "first"
            message = "First time tracking this product"
        elif price_number < old_price:
            status  = "drop"
            message = f"Price dropped from ₹{old_price:,} to {price_text} 📉"
        elif price_number > old_price:
            status  = "rise"
            message = f"Price increased from ₹{old_price:,} to {price_text} 📈"
        else:
            status  = "same"
            message = "Price unchanged"

        target_hit = price_number <= target_price
        alert_result = None
        alert_hint = None
        if target_hit:
            message += " — 🎯 Target price reached!"
            if was_alert_sent_recently(product_url, email, hours=24):
                alert_result = "skipped"
                alert_hint = "Alert already sent in the last 24 hours, so duplicate email was skipped."
            else:
                def email_task():
                    sent = send_price_alert(
                        email         = email,
                        product_url   = product_url,
                        current_price = price_number,
                        target_price  = target_price,
                        platform      = platform,
                        product_name  = product_name,
                    )
                    if sent:
                        log_alert_sent(product_url, email, price_number)

                background_tasks.add_task(email_task)
                alert_result = "sent"
                alert_hint = f"Email alert is being dispatched to {email} instantly in the background!"

        insert_price(product_url, email, price_number, target_price, platform, product_name)

        # Background task to automatically track on other platforms
        if product_name:
            def auto_track_others_task():
                try:
                    results = cross_platform_search(product_name, source_platform=platform)
                    for res in results:
                        if res.get("url") and res.get("price"):
                            insert_price(
                                url=res["url"],
                                email=email,
                                price=res["price"],
                                target_price=target_price,
                                platform=res["platform"],
                                product_name=res["name"]
                            )
                except Exception as e:
                    print(f"[Auto-Track] Error: {e}")

            background_tasks.add_task(auto_track_others_task)
        products = get_tracked_products_by_email(email)

        return templates.TemplateResponse(request, "track.html", base_ctx(
            request, user, active="track", extra={
                "price":        price_text,
                "price_num":    price_number,
                "message":      message,
                "status":       status,
                "target_hit":   target_hit,
                "alert_result": alert_result,
                "alert_hint":   alert_hint,
                "platform":     platform,
                "product_name": product_name,
                "product_url":  product_url,
                "products":     products,
            }
        ))

    return templates.TemplateResponse(request, "track.html", base_ctx(
        request, user, active="track", extra={
            "error": "Could not fetch price. Check the URL — supported platforms: Flipkart, Amazon.in, Myntra, Snapdeal.",
        }
    ))


@app.post("/track/delete")
def delete_product(request: Request, url: str = Form(...)):
    r = require_login(request)
    if r: return r
    delete_tracked_product(current_user(request)["email"], url)
    return RedirectResponse(url="/dashboard", status_code=302)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    r = require_login(request)
    if r: return r
    user     = current_user(request)
    products = get_tracked_products_by_email(user["email"])
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        base_ctx(request, user, active="dashboard", extra={"products": products}),
    )



# ── Compare ───────────────────────────────────────────────────────────────────

@app.get("/compare", response_class=HTMLResponse)
def compare_page(request: Request):
    r = require_login(request)
    if r: return r
    return templates.TemplateResponse(
        request,
        "compare.html",
        base_ctx(request, current_user(request), active="compare"),
    )


@app.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request):
    r = require_login(request)
    if r: return r
    user = current_user(request)
    rows = get_price_rows_by_email(user["email"], limit=300)
    return templates.TemplateResponse(
        request,
        "analytics.html",
        base_ctx(request, user, active="analytics", extra={"rows": _json_ready(rows)}),
    )


@app.get("/api/compare")
def price_comparison_api(request: Request, q: str = ""):
    if IS_SHUTTING_DOWN:
        return JSONResponse(
            {"comparisons": [], "message": "Server is shutting down. Try again in a moment."},
            status_code=503,
        )

    user = current_user(request)
    if not user:
        return JSONResponse({"comparisons": []}, status_code=401)

    q_clean = q.strip()
    q_norm = q_clean.lower()
    products = get_tracked_products_by_email(user["email"])
    products_to_compare = products
    reference_key = ""

    if q_norm and _is_probable_url(q_clean):
        q_platform = detect_platform(q_norm)
        if not q_platform:
            return JSONResponse({
                "comparisons": [],
                "message": "Unsupported URL. Use Flipkart, Amazon.in, Myntra, or Snapdeal product links.",
            })

        _, q_live_price, _, q_live_name = _safe_get_product_price(q_clean)
        reference_name = q_live_name or q_clean
        reference_key = _normalize_compare_key(reference_name)
        q_tokens = _key_tokens(reference_name)

        # Restrict to likely matching tracked products so pasted-link compare is fast.
        narrowed = []
        for p in products:
            candidate_name = p.get("product_name") or p.get("url") or ""
            if _keys_match(candidate_name, reference_name):
                narrowed.append(p)
                continue
            c_tokens = _key_tokens(candidate_name)
            if q_tokens and len(q_tokens & c_tokens) >= 2:
                narrowed.append(p)

        products_to_compare = narrowed
        if q_live_price:
            products_to_compare.append({
                "url": q_clean,
                "price": q_live_price,
                "platform": q_platform,
                "product_name": reference_name,
                "target_price": None,
            })
    elif q_norm:
        products_to_compare = [
            p for p in products
            if q_norm in (p.get("product_name") or "").lower() or q_norm in (p.get("url") or "").lower()
        ]

    if q_norm and not products_to_compare:
        return JSONResponse({
            "comparisons": [],
            "message": "No related tracked products found. Track the same product on at least two platforms first.",
        })

    if not q_norm:
        products_to_compare = products[:8]

    if q_norm and not _is_probable_url(q_clean):
        products = [
            p for p in products_to_compare
            if q_norm in (p.get("product_name") or "").lower() or q_norm in (p.get("url") or "").lower()
        ]
        products_to_compare = products

    if not products_to_compare:
        return JSONResponse({"comparisons": []})

    # Refresh current price from live URLs in parallel for better speed.
    refreshed = []
    capped = products_to_compare[:12]

    def _refresh_one(product_row: dict):
        url = product_row.get("url")
        if not url:
            return None
        _, live_price, platform, live_name = _safe_get_product_price(url)
        effective_price = live_price or product_row.get("price")
        if not effective_price:
            return None
        normalized_platform = (platform or product_row.get("platform") or "unknown").lower()
        normalized_name = live_name or product_row.get("product_name") or url
        return {
            "url": url,
            "price": effective_price,
            "platform": normalized_platform,
            "product_name": normalized_name,
            "target_price": product_row.get("target_price"),
        }

    max_workers = min(4, max(1, len(capped)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_refresh_one, p) for p in capped]
        for fut in as_completed(futures):
            try:
                row = fut.result()
            except Exception:
                continue
            if not row:
                continue
            refreshed.append(row)
            try:
                insert_price(
                    url=row["url"],
                    email=user["email"],
                    price=row["price"],
                    target_price=row.get("target_price"),
                    platform=row["platform"],
                    product_name=row["product_name"],
                )
            except Exception:
                pass

    grouped = {}
    for row in refreshed:
        key = _normalize_compare_key(row["product_name"]) or row["product_name"].lower()[:50]
        if reference_key and not _keys_match(row["product_name"], reference_key):
            continue
        grouped.setdefault(key, []).append(row)

    comparisons = []
    for rows in grouped.values():
        by_platform = {}
        for row in rows:
            plat = row["platform"]
            current = by_platform.get(plat)
            if current is None or row["price"] < current["price"]:
                by_platform[plat] = row

        if len(by_platform) < 2:
            continue

        prices = []
        for plat in ("flipkart", "amazon", "myntra", "snapdeal"):
            if plat in by_platform:
                prices.append({"site": plat.title(), "price": int(by_platform[plat]["price"])})

        prices = sorted(prices, key=lambda x: x["price"])
        lowest = prices[0]["site"]
        savings = max(0, prices[-1]["price"] - prices[0]["price"])
        # Fetch real price history (last 7 entries) for each platform
        history = {}
        for plat, row_data in by_platform.items():
            h = get_price_history(row_data["url"], user["email"], limit=7)
            h.reverse()  # oldest first
            history[plat.title()] = [entry["price"] for entry in h]

        comparisons.append({
            "product": rows[0]["product_name"],
            "prices": prices,
            "lowest": lowest,
            "savings": savings,
            "history": history,
        })

    comparisons = sorted(comparisons, key=lambda x: x["savings"], reverse=True)
    return JSONResponse({"comparisons": comparisons[:6]})


# ── AI Chatbot ────────────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str        # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []

@app.post("/api/chat")
def api_chat(req: ChatRequest, request: Request):
    user = current_user(request)

    # Build user context
    user_context_lines = []
    if user:
        products = get_tracked_products_by_email(user["email"])
        if products:
            items = []
            for p in products[:10]:
                name = p.get("product_name") or p.get("url", "")[:60]
                price = p.get("price", 0)
                target = p.get("target_price")
                platform = p.get("platform", "")
                gap = f", target ₹{target:,}" if target else ""
                items.append(f"  • {name} — ₹{price:,} on {platform}{gap}")
            user_context_lines.append("User's currently tracked products:\n" + "\n".join(items))
        else:
            user_context_lines.append("The user has no tracked products yet.")

    user_context = "\n".join(user_context_lines)
    
    system_prompt = f"""You are the Price Tracker AI Assistant, a smart and friendly shopping advisor built into Price Tarcker — a multi-platform price tracking app for Indian e-commerce (Flipkart, Amazon.in, Myntra, Snapdeal).

Your role is to help users:
- Compare prices and find the best deal across platforms
- Understand if a price is fair or inflated for a product category
- Know the best time to buy (upcoming sales, seasonal trends)
- Interpret their tracked product data and price history
- Make fast, confident purchasing decisions

Personality: Direct, analytical, concise, friendly. Always use ₹ for Indian prices (e.g. ₹40,999). Give concrete recommendations — don't be vague.

Website features you can reference:
- /track — Add a product URL with a target price to get email alerts when price drops
- /dashboard — View all tracked products and their current status
- /compare — Compare a product URL live across all 4 platforms instantly
- /analytics — See price trend charts and savings statistics

{user_context}

Rules:
- Keep responses under 5 bullet points for simple questions
- Never make up prices — only use data provided in context
- Format as: ₹X,XX,XXX (Indian rupee notation)
- For compare page analysis: always end with a clear BUY NOW / WAIT FOR SALE / SKIP verdict
- If asked about non-shopping topics, briefly redirect to shopping help"""

    # Build conversation turns for multi-turn context
    conversation_parts = []
    for turn in (req.history or [])[-6:]:  # last 6 turns max
        role = "user" if turn.role == "user" else "model"
        conversation_parts.append({"role": role, "parts": [{"text": turn.content}]})
    # Add the new user message
    conversation_parts.append({"role": "user", "parts": [{"text": req.message}]})

    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key or api_key.startswith("your_"):
            return JSONResponse({
                "answer": "⚠ Antigravity AI is not configured yet. Add your GEMINI_API_KEY to the .env file to enable the assistant."
            }, status_code=503)

        client = genai.Client(api_key=api_key)

        # Try Gemini 2.5 Flash first, fall back to 1.5 Flash on 503
        for model_name in ("gemini-2.5-flash", "gemini-1.5-flash"):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=conversation_parts,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        max_output_tokens=600,
                        temperature=0.7,
                    ),
                )
                return JSONResponse({"answer": response.text})
            except Exception as e:
                err_str = str(e)
                if ("503" in err_str or "UNAVAILABLE" in err_str or "demand" in err_str.lower()) \
                        and model_name != "gemini-1.5-flash":
                    continue  # try fallback
                raise e

    except Exception as e:
        return JSONResponse({
            "answer": f"Oops! Something went wrong with Antigravity AI: {str(e)[:120]}"
        }, status_code=500)


# ── Comparison API ───────────────────────────────────────────────────────────
@app.get("/api/cross-search")
def api_cross_search(url: str, request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"message": "Authentication required"}, status_code=401)
    
    url_clean = url.strip()
    platform = detect_platform(url_clean)
    if not platform:
        return JSONResponse({"message": "Unsupported URL"}, status_code=400)
    
    _, live_price, _, live_name = _safe_get_product_price(url_clean)
    if not live_price:
         return JSONResponse({"message": "Could not fetch price from source URL"}, status_code=404)
    
    results = cross_platform_search(live_name or url_clean, source_platform=platform)
    
    results.append({
        "platform": platform,
        "price": live_price,
        "url": url_clean,
        "name": live_name or "Source Product"
    })
    
    return JSONResponse({
        "results": results,
        "product_name": live_name or "Product",
        "source_platform": platform
    })

