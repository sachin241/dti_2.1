# scheduler.py
import os
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from database import get_all_tracked_products, insert_price, log_alert_sent, was_alert_sent_recently
from email_service import send_price_alert
from scraper import get_product_price

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Kolkata")


def check_prices():
    """Main price checking function with comprehensive logging."""
    start_time = datetime.now()
    logger.info(f"[Scheduler] Price check started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Step 1: Get all tracked products
        logger.info("[Scheduler] Fetching tracked products from database...")
        products = get_all_tracked_products()
        logger.info(f"[Scheduler] Found {len(products)} tracked product(s)")

        if not products:
            logger.warning("[Scheduler] No products to check - database might be empty")
            return

        processed_count = 0
        alert_count = 0
        error_count = 0

        # Step 2: Process each product
        for i, product in enumerate(products, 1):
            url = product.get("url")
            email = product.get("email")
            target_price = product.get("target_price")
            platform = product.get("platform", "flipkart")
            product_name = product.get("product_name")

            logger.info(f"[Scheduler] Processing {i}/{len(products)}: [{platform}] {url[:60]}... (email: {email})")

            # Validate required fields
            if not url or not email:
                logger.error(f"[Scheduler] Missing url or email for product: {product}")
                error_count += 1
                continue

            try:
                # Step 3: Scrape current price
                logger.debug(f"[Scheduler] Scraping price for: {url}")
                price_text, new_price, detected_platform, title = get_product_price(url)

                if new_price is None:
                    logger.warning(f"[Scheduler] Could not fetch price for {url} - scraper returned None")
                    error_count += 1
                    continue

                logger.info(f"[Scheduler] Successfully scraped price: ₹{new_price:,} (detected platform: {detected_platform})")

                # Step 4: Store price in database
                name_to_store = product_name or title
                logger.debug(f"[Scheduler] Storing price in database: url={url}, email={email}, price={new_price}")
                insert_price(url, email, new_price, target_price, detected_platform, name_to_store)
                logger.debug("[Scheduler] Price stored successfully")

                processed_count += 1

                # Step 5: Check if alert should be sent
                if target_price is None:
                    logger.debug(f"[Scheduler] No target price set for {url} - skipping alert check")
                    continue

                if new_price > target_price:
                    logger.debug(f"[Scheduler] Current price ₹{new_price:,} > target ₹{target_price:,} - no alert needed")
                    continue

                logger.info(f"[Scheduler] Target reached! Current: ₹{new_price:,} <= Target: ₹{target_price:,}")

                # Step 6: Check dedup guard
                logger.debug(f"[Scheduler] Checking if alert was sent recently for {url} + {email}")
                if was_alert_sent_recently(url, email, hours=24):
                    logger.info(f"[Scheduler] Alert already sent in last 24h for {url} - skipping")
                    continue

                # Step 7: Send email alert
                logger.info(f"[Scheduler] Sending alert email to {email} for {url}")
                sent = send_price_alert(
                    email=email,
                    product_url=url,
                    current_price=new_price,
                    target_price=target_price,
                    platform=detected_platform,
                    product_name=name_to_store,
                )

                if sent:
                    # Step 8: Log successful alert
                    logger.info(f"[Scheduler] Alert sent successfully to {email}")
                    log_alert_sent(url, email, new_price)
                    alert_count += 1
                else:
                    logger.error(f"[Scheduler] Alert failed to send to {email}")
                    error_count += 1

            except Exception as exc:
                logger.error(f"[Scheduler] Error processing {url}: {exc}", exc_info=True)
                error_count += 1

        # Step 9: Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(f"[Scheduler] Completed in {duration:.1f}s")
        logger.info(f"[Scheduler] Summary: {processed_count} processed, {alert_count} alerts sent, {error_count} errors")

    except Exception as exc:
        logger.error(f"[Scheduler] Critical error in check_prices(): {exc}", exc_info=True)


def start_price_scheduler():
    """Start the price checking scheduler with logging."""
    if scheduler.running:
        logger.warning("[Scheduler] Scheduler already running - skipping start")
        return

    try:
        logger.info("[Scheduler] Adding price check job (every 6 hours)...")
        scheduler.add_job(
            check_prices,
            trigger="interval",
            hours=6,
            id="price_check_job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            next_run_time=None,  # don't fire immediately on startup
        )

        logger.info("[Scheduler] Starting scheduler...")
        scheduler.start()

        # Log next run time
        job = scheduler.get_job("price_check_job")
        if job:
            next_run = job.next_run_time
            logger.info(f"[Scheduler] Started successfully - next run at {next_run.strftime('%Y-%m-%d %H:%M:%S %Z') if next_run else 'unknown'}")
        else:
            logger.error("[Scheduler] Job was not added successfully")

    except Exception as exc:
        logger.error(f"[Scheduler] Failed to start scheduler: {exc}", exc_info=True)


def stop_price_scheduler():
    """Stop the price checking scheduler."""
    if scheduler.running:
        logger.info("[Scheduler] Stopping scheduler...")
        scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Stopped successfully")
    else:
        logger.info("[Scheduler] Scheduler was not running")


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
