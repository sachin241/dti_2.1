import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_TIMEOUT = 30.0

PLATFORM_COLORS = {
    "flipkart": "#2874F0",
    "amazon": "#FF9900",
    "myntra": "#FF3F6C",
    "snapdeal": "#E40000",
}

PLATFORM_NAMES = {
    "flipkart": "Flipkart",
    "amazon": "Amazon",
    "myntra": "Myntra",
    "snapdeal": "Snapdeal",
}


def _resolve_sender_email() -> Optional[str]:
    return os.getenv("RESEND_FROM_EMAIL") or os.getenv("SENDER_EMAIL")


def _resolve_sender_name() -> str:
    return os.getenv("RESEND_FROM_NAME", "Smart Price Tracker")


def _build_html(
    product_url: str,
    product_name: str,
    current_price: int,
    target_price: int,
    platform: str,
) -> str:
    color = PLATFORM_COLORS.get(platform, "#4F46E5")
    pname = PLATFORM_NAMES.get(platform, platform.title())
    display = product_name or product_url[:80] + ("..." if len(product_url) > 80 else "")

    savings = ""
    if target_price and current_price < target_price:
        diff = target_price - current_price
        savings = f"<p style='color:#16a34a;font-weight:600;margin:0 0 16px'>You save Rs.{diff:,} vs your target!</p>"

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:'Segoe UI',Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:40px 0">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">

        <tr>
          <td style="background:{color};padding:28px 32px">
            <p style="margin:0;color:rgba(255,255,255,.8);font-size:13px;letter-spacing:1.5px;text-transform:uppercase">{pname} Price Alert</p>
            <h1 style="margin:6px 0 0;color:#fff;font-size:24px;font-weight:700">Target Price Reached!</h1>
          </td>
        </tr>

        <tr>
          <td style="padding:32px">
            <p style="margin:0 0 8px;color:#6b7280;font-size:13px">Product</p>
            <p style="margin:0 0 24px;color:#111827;font-size:15px;font-weight:600;line-height:1.4">{display}</p>

            <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;border-radius:12px;margin-bottom:24px">
              <tr>
                <td style="padding:20px 24px;border-right:1px solid #e5e7eb" width="50%">
                  <p style="margin:0 0 4px;color:#6b7280;font-size:12px;text-transform:uppercase;letter-spacing:.8px">Current Price</p>
                  <p style="margin:0;color:{color};font-size:28px;font-weight:700">Rs.{current_price:,}</p>
                </td>
                <td style="padding:20px 24px" width="50%">
                  <p style="margin:0 0 4px;color:#6b7280;font-size:12px;text-transform:uppercase;letter-spacing:.8px">Your Target</p>
                  <p style="margin:0;color:#374151;font-size:28px;font-weight:700">Rs.{target_price:,}</p>
                </td>
              </tr>
            </table>

            {savings}

            <a href="{product_url}"
               style="display:block;text-align:center;background:{color};color:#fff;text-decoration:none;padding:14px 24px;border-radius:10px;font-weight:600;font-size:15px">
              Buy Now on {pname} ->
            </a>
          </td>
        </tr>

        <tr>
          <td style="padding:16px 32px;background:#f9fafb;border-top:1px solid #f3f4f6">
            <p style="margin:0;color:#9ca3af;font-size:12px;text-align:center">
              Smart Price Tracker - You're receiving this because you set a target price alert.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def _build_plain_text(
    product_url: str,
    product_name: str,
    current_price: int,
    target_price: int,
    platform: str,
) -> str:
    display = product_name or product_url
    pname = PLATFORM_NAMES.get(platform, platform.title())
    return (
        f"Price alert for: {display}\n\n"
        f"Current price : Rs.{current_price:,}\n"
        f"Your target   : Rs.{target_price:,}\n"
        f"Platform      : {pname}\n\n"
        f"Buy now: {product_url}"
    )


def send_price_alert(
    email: str,
    product_url: str,
    current_price: int,
    target_price: int = 0,
    platform: str = "flipkart",
    product_name: str = None,
) -> bool:
    """Send a transactional price alert through Resend's HTTPS API."""
    resend_api_key = os.getenv("RESEND_API_KEY")
    sender_email = _resolve_sender_email()
    sender_name = _resolve_sender_name()

    logger.info("[Email] Attempting Resend alert to %s for %s", email, product_url)
    logger.debug("[Email] RESEND_API_KEY set: %s", bool(resend_api_key))
    logger.debug("[Email] Sender email configured: %s", bool(sender_email))

    if not resend_api_key:
        logger.error("[Email] RESEND_API_KEY is not set - cannot send email")
        return False
    if not sender_email:
        logger.error("[Email] RESEND_FROM_EMAIL (or fallback SENDER_EMAIL) is not set - cannot send email")
        return False

    pname = PLATFORM_NAMES.get(platform, platform.title())
    subject = f"Target reached! Rs.{current_price:,} on {pname}"
    html = _build_html(product_url, product_name, current_price, target_price, platform)
    text = _build_plain_text(product_url, product_name, current_price, target_price, platform)

    payload = {
        "from": f"{sender_name} <{sender_email}>",
        "to": [email],
        "subject": subject,
        "html": html,
        "text": text,
        "tags": [
            {"name": "category", "value": "price_alert"},
            {"name": "platform", "value": (platform or "other").lower()},
        ],
    }
    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json",
        "User-Agent": "dti-price-tracker/1.0",
    }

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.post(RESEND_API_URL, headers=headers, json=payload)

        if response.is_success:
            response_data = response.json()
            logger.info(
                "[Email] Alert sent successfully to %s via Resend (id=%s)",
                email,
                response_data.get("id", "unknown"),
            )
            return True

        body_preview = response.text[:500]
        logger.error(
            "[Email] Resend API rejected alert to %s: status=%s body=%s",
            email,
            response.status_code,
            body_preview,
        )

        if response.status_code in {401, 403}:
            logger.error("[Email] Check RESEND_API_KEY and verify the sender domain/address in Resend.")
        elif response.status_code == 422:
            logger.error("[Email] Resend validation failed. Check sender email formatting and recipient payload.")
        elif response.status_code == 429:
            logger.error("[Email] Resend rate limit reached. Retry later or batch traffic.")
    except httpx.TimeoutException:
        logger.error("[Email] Timeout while calling Resend for %s", email, exc_info=True)
    except httpx.RequestError as exc:
        logger.error("[Email] Network error while calling Resend for %s: %s", email, exc, exc_info=True)
    except Exception as exc:
        logger.error("[Email] Unexpected error sending to %s via Resend: %s", email, exc, exc_info=True)

    return False
