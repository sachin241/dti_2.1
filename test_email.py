# test_email.py
"""
Quick smoke-test for the email alert service.
Set SENDER_EMAIL and APP_PASSWORD env vars before running.
"""
import os
from email_service import send_price_alert

if __name__ == "__main__":
    result = send_price_alert(
        email         = os.getenv("TEST_EMAIL", "harishchandraappari74@gmail.com"),
        product_url   = "https://www.flipkart.com/sample-product",
        current_price = 14999,
        target_price  = 15000,
        platform      = "flipkart",
        product_name  = "Test Product - Motorola G57",
    )
    print("Email sent:", result)
