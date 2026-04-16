# scheduler.py
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from database import get_all_tracked_products, insert_price, log_alert_sent, was_alert_sent_recently
from email_service import send_price_alert
from scraper import get_product_price

scheduler = BackgroundScheduler(timezone="Asia/Kolkata")


def check_prices():
    print(f"\n[Scheduler] Price check started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    products = get_all_tracked_products()
    print(f"[Scheduler] Checking {len(products)} tracked product(s)...")

    for product in products:
        url          = product["url"]
        email        = product["email"]
        target_price = product["target_price"]
        platform     = product.get("platform", "flipkart")
        product_name = product.get("product_name")

        try:
            print(f"  → [{platform}] {url[:60]}...")
            price_text, new_price, detected_platform, title = get_product_price(url)

            if new_price is None:
                print(f"    ✗ Could not fetch price")
                continue

            # Use detected title if we don't have a stored name
            name_to_store = product_name or title
            insert_price(url, email, new_price, target_price, detected_platform, name_to_store)
            print(f"    ✓ ₹{new_price:,}")

            if target_price is not None and new_price <= target_price:
                if was_alert_sent_recently(url, email, hours=24):
                    print(f"    ℹ  Target reached but alert already sent in last 24h — skipping")
                    continue

                sent = send_price_alert(
                    email        = email,
                    product_url  = url,
                    current_price= new_price,
                    target_price = target_price,
                    platform     = detected_platform,
                    product_name = name_to_store,
                )
                if sent:
                    log_alert_sent(url, email, new_price)
                    print(f"    📧 Alert sent to {email}")
                else:
                    print(f"    ✗ Alert failed for {email}")

        except Exception as exc:
            print(f"    ✗ Scheduler error for {url}: {exc}")

    print(f"[Scheduler] Done at {datetime.now().strftime('%H:%M:%S')}\n")


def start_price_scheduler():
    if scheduler.running:
        return

    scheduler.add_job(
        check_prices,
        trigger      = "interval",
        hours        = 6,
        id           = "price_check_job",
        replace_existing = True,
        max_instances    = 1,
        coalesce         = True,
        next_run_time    = None,   # don't fire immediately on startup
    )
    scheduler.start()
    print(f"[Scheduler] Started — runs every 6 hours (Asia/Kolkata). "
          f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def stop_price_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("[Scheduler] Stopped")
