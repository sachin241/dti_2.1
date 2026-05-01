# email_service.py
import os
import smtplib
import json
import time
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


PLATFORM_COLORS = {
    "flipkart": "#2874F0",
    "amazon":   "#FF9900",
    "myntra":   "#FF3F6C",
    "snapdeal": "#E40000",
}

PLATFORM_NAMES = {
    "flipkart": "Flipkart",
    "amazon":   "Amazon",
    "myntra":   "Myntra",
    "snapdeal": "Snapdeal",
}


def _build_html(product_url: str, product_name: str, current_price: int,
                target_price: int, platform: str) -> str:
    color   = PLATFORM_COLORS.get(platform, "#4F46E5")
    pname   = PLATFORM_NAMES.get(platform, platform.title())
    display = product_name or product_url[:80] + ("…" if len(product_url) > 80 else "")

    savings = ""
    if target_price and current_price < target_price:
        diff = target_price - current_price
        savings = f"<p style='color:#16a34a;font-weight:600;margin:0 0 16px'>You save ₹{diff:,} vs your target!</p>"

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:'Segoe UI',Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:40px 0">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">

        <!-- Header -->
        <tr>
          <td style="background:{color};padding:28px 32px">
            <p style="margin:0;color:rgba(255,255,255,.8);font-size:13px;letter-spacing:1.5px;text-transform:uppercase">{pname} Price Alert</p>
            <h1 style="margin:6px 0 0;color:#fff;font-size:24px;font-weight:700">🎯 Target Price Reached!</h1>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px">
            <p style="margin:0 0 8px;color:#6b7280;font-size:13px">Product</p>
            <p style="margin:0 0 24px;color:#111827;font-size:15px;font-weight:600;line-height:1.4">{display}</p>

            <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;border-radius:12px;margin-bottom:24px">
              <tr>
                <td style="padding:20px 24px;border-right:1px solid #e5e7eb" width="50%">
                  <p style="margin:0 0 4px;color:#6b7280;font-size:12px;text-transform:uppercase;letter-spacing:.8px">Current Price</p>
                  <p style="margin:0;color:{color};font-size:28px;font-weight:700">₹{current_price:,}</p>
                </td>
                <td style="padding:20px 24px" width="50%">
                  <p style="margin:0 0 4px;color:#6b7280;font-size:12px;text-transform:uppercase;letter-spacing:.8px">Your Target</p>
                  <p style="margin:0;color:#374151;font-size:28px;font-weight:700">₹{target_price:,}</p>
                </td>
              </tr>
            </table>

            {savings}

            <a href="{product_url}"
               style="display:block;text-align:center;background:{color};color:#fff;text-decoration:none;padding:14px 24px;border-radius:10px;font-weight:600;font-size:15px">
              Buy Now on {pname} →
            </a>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:16px 32px;background:#f9fafb;border-top:1px solid #f3f4f6">
            <p style="margin:0;color:#9ca3af;font-size:12px;text-align:center">
              Smart Price Tracker · You're receiving this because you set a target price alert.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def send_price_alert(email: str, product_url: str, current_price: int,
                     target_price: int = 0, platform: str = "flipkart",
                     product_name: str = None) -> bool:
    """Send price alert email with comprehensive logging."""
    logger.info(f"[Email] Attempting to send alert to {email} for {product_url}")

    # Get credentials
    sender_email = os.getenv("SENDER_EMAIL")
    app_password = os.getenv("APP_PASSWORD")

    logger.debug(f"[Email] SENDER_EMAIL set: {bool(sender_email)}")
    logger.debug(f"[Email] APP_PASSWORD set: {bool(app_password)}")

    if not sender_email or not app_password:
        logger.error("[Email] SENDER_EMAIL or APP_PASSWORD not set - cannot send email")
        logger.error(f"[Email] SENDER_EMAIL: '{sender_email}'")
        logger.error(f"[Email] APP_PASSWORD: '{'*' * len(app_password) if app_password else 'None'}'")
        return False

    try:
        # Build email content
        pname = PLATFORM_NAMES.get(platform, platform.title())
        subject = f"🎯 Price Drop! ₹{current_price:,} on {pname}"

        logger.debug(f"[Email] Building email: subject='{subject}', platform='{platform}'")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Smart Price Tracker <{sender_email}>"
        msg["To"] = email

        # Plain text fallback
        display = product_name or product_url
        plain = (
            f"Price alert for: {display}\n\n"
            f"Current price : ₹{current_price:,}\n"
            f"Your target   : ₹{target_price:,}\n"
            f"Platform      : {pname}\n\n"
            f"Buy now: {product_url}"
        )
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(
            _build_html(product_url, product_name, current_price, target_price, platform),
            "html"
        ))

        logger.debug(f"[Email] Email content built, size: {len(str(msg))} chars")

        # Send email
        logger.info(f"[Email] Connecting to SMTP server...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            logger.debug("[Email] Connected to SMTP server")
            logger.debug(f"[Email] Logging in as {sender_email}")
            server.login(sender_email, app_password)
            logger.debug("[Email] Login successful")

            logger.debug(f"[Email] Sending message to {email}")
            server.send_message(msg)
            logger.debug("[Email] Message sent successfully")

        logger.info(f"[Email] Alert sent successfully to {email}")
        return True

    except smtplib.SMTPAuthenticationError as exc:
        logger.error(f"[Email] SMTP Authentication failed for {email}: {exc}")
        logger.error("[Email] Check APP_PASSWORD and SENDER_EMAIL credentials")
    except smtplib.SMTPConnectError as exc:
        logger.error(f"[Email] SMTP Connection failed for {email}: {exc}")
        logger.error("[Email] Check internet connection and Gmail SMTP settings")
    except smtplib.SMTPException as exc:
        logger.error(f"[Email] SMTP error for {email}: {exc}")
    except Exception as exc:
        logger.error(f"[Email] Unexpected error sending to {email}: {exc}", exc_info=True)

    return False
