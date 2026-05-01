# 📊 Price Tarcker — Smart Multi-Platform Price Tracker

> Track Flipkart · Amazon India · Myntra · Snapdeal — all in one place.

---

## 🚀 What's New (v2.1)

- ✅ **4-platform scraping** — Flipkart, Amazon.in, Myntra, Snapdeal
- ✅ **Upgraded database** — platform field, product name storage, alert log, migration-safe
- ✅ **Rich HTML email alerts** — per-platform branded emails with buy button
- ✅ **Dedup guard** — no duplicate alerts within 24 hours
- ✅ **6-hour scheduler** — APScheduler with IST timezone, coalesce + max_instances protection
- ✅ **Priority fixes** — no hardcoded credentials, no duplicate DB functions, no `time.sleep` abuse
- ✅ **Ember Noir UI** — warm charcoal + ember orange theme, glassmorphism cards
- ✅ **Avatar upload** — Pillow resize/center-crop to 200×200
- ✅ **Delete tracking** — remove products from dashboard with confirmation
- ✅ **Sitewide AI chatbot** — Gemini-powered assistant on every page
- ✅ **Mobile hamburger nav** — responsive dropdown for small screens
- ✅ **Password hashing** — SHA-256 via hashlib
- ✅ **No n8n dependency** — standalone backend, no external automation required

---

## 🏗️ Architecture

```
Browser (Ember Noir Dark UI)
  ↓
FastAPI (main.py)  — Auth · Track · Dashboard · Compare · Profile
  ↓               ↓               ↓
scraper.py    database.py    email_service.py
(Selenium)    (SQLite)       (SMTP Gmail)
  ↑
scheduler.py   (APScheduler, every 6h, IST)
```

---

## 🛠️ Tech Stack

| Layer      | Technology                        |
|------------|-----------------------------------|
| Backend    | FastAPI (Python)                  |
| Scraping   | Selenium + WebDriverManager       |
| Database   | SQLite (context-manager safe)     |
| Email      | smtplib SMTP_SSL + HTML templates |
| Scheduling | APScheduler BackgroundScheduler   |
| Images     | Pillow (avatar resize/crop)       |
| AI         | Google Gemini (chatbot)           |
| Frontend   | Jinja2 HTML/CSS (no framework)    |

---

## ⚡ Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env file
SENDER_EMAIL=your_gmail@gmail.com
APP_PASSWORD=your_gmail_app_password
SECRET_KEY=your_random_secret_key
GEMINI_API_KEY=your_gemini_api_key

# Optional: Google OAuth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# 3. Run
uvicorn main:app --reload --port 8000
```

Open http://127.0.0.1:8000

---

## 📋 Supported Platforms

| Platform   | Domain          | Price Selectors                     |
|------------|-----------------|--------------------------------------|
| Flipkart   | flipkart.com    | `div._30jeq3`, `div.Nx9bqj`         |
| Amazon.in  | amazon.in       | `span.a-price-whole`, `#priceblock` |
| Myntra     | myntra.com      | `span.pdp-price strong`             |
| Snapdeal   | snapdeal.com    | `span#selling-price-id`             |

Auto-detected from the URL — no manual selection needed.

---

## 🐛 Known Issues & Fixes

| Issue | Status | Fix Applied |
|-------|--------|-------------|
| Email credentials not loading | ✅ Fixed | Moved `os.getenv()` calls inside `send_price_alert()` function body (were at module-level before `load_dotenv()` ran) |
| `static/` dir crash on startup | ✅ Fixed | `os.makedirs("static/avatars", exist_ok=True)` in `startup_event()` |
| Passwords in plain text | ✅ Fixed | SHA-256 hashing via `hashlib` |
| Compare chart showing fake data | ✅ Fixed | Real price history from DB, null-padded for Chart.js |
| No products on GET /track | ✅ Fixed | `get_tracked_products_by_email()` called on GET as well as POST |
| No delete tracking button | ✅ Fixed | `POST /track/delete` + dashboard delete button |
| Mobile nav unusable | ✅ Fixed | Hamburger menu in base.html |

---

## 🔒 Production Checklist

- [ ] Set a strong `SECRET_KEY` (at least 32 random bytes)
- [ ] Use HTTPS (set `https_only=True` in SessionMiddleware)
- [ ] Rotate Gmail `APP_PASSWORD` regularly
- [ ] Never commit `.env` to version control (`.gitignore` covers this)
- [ ] Consider switching from SHA-256 to `bcrypt` for passwords in production
- [ ] Add rate limiting on `/login` endpoint
- [ ] Set `GOOGLE_CLIENT_ID` for OAuth sign-in
- [ ] Add `debug-3b2a57.log` to `.gitignore` (already done)

---

## Render Deployment

- Deploy with `render.yaml` as a Docker web service.
- A persistent disk is mounted at `/var/data` for:
  - `prices.db`
  - uploaded avatars
- The app exposes a health check at `/health`.
- Selenium runs in Docker with system `chromium` and `chromedriver`.
- Set these Render environment variables:
  - Required: `GEMINI_API_KEY`
  - Optional: `SENDER_EMAIL`, `APP_PASSWORD`
  - Optional: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`
- `SECRET_KEY` is generated automatically by `render.yaml`.
- `ENABLE_SCHEDULER` defaults to `false` in Render to avoid duplicate background jobs on scaled instances.

If you want the scheduler on Render, turn `ENABLE_SCHEDULER=true` and keep the service at a single instance.

---

## 📂 File Structure

```
price-tracker/
├── main.py           # FastAPI app + routes
├── scraper.py        # Multi-platform Selenium scraper
├── database.py       # SQLite with context managers
├── email_service.py  # HTML email alerts (no hardcoded creds)
├── scheduler.py      # APScheduler 6h price checks
├── requirements.txt  # Python dependencies
├── templates/        # Jinja2 HTML templates
│   ├── base.html     # Layout, Ember Noir theme, chatbot, hamburger nav
│   ├── dashboard.html
│   ├── track.html
│   ├── compare.html
│   ├── analytics.html
│   ├── profile.html
│   └── login.html
├── static/
│   └── avatars/      # User-uploaded avatars (auto-created)
└── prices.db         # SQLite database (auto-created)
```

---

## 🔮 Future Enhancements

- ML price prediction (Prophet / ARIMA)
- Webhook / Telegram alerts
- Docker deployment
- Multi-currency support
