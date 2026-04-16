<<<<<<< HEAD
# 📊 Price Tarcker — Smart Multi-Platform Price Tracker

> Track Flipkart · Amazon India · Myntra · Snapdeal — all in one place.

---

## 🚀 What's New (v2)

- ✅ **4-platform scraping** — Flipkart, Amazon.in, Myntra, Snapdeal
- ✅ **Upgraded database** — platform field, product name storage, alert log, migration-safe
- ✅ **Rich HTML email alerts** — per-platform branded emails with buy button
- ✅ **Dedup guard** — no duplicate alerts within 24 hours
- ✅ **6-hour scheduler** — APScheduler with IST timezone, coalesce + max_instances protection
- ✅ **Priority fixes** — no hardcoded credentials, no duplicate DB functions, no `time.sleep` abuse
- ✅ **Vibrant dark UI** — Clash Display + Satoshi fonts, gradient blobs, progress bars, platform badges
- ✅ **No n8n dependency** — standalone backend, no external automation required

---

## 🏗️ Architecture

```
Browser (Dark UI)
  ↓
FastAPI (main.py)  — Auth · Track · Dashboard · Compare
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
| Frontend   | Inline HTML/CSS (no framework)    |

---

## ⚡ Quick Start

```bash
# 1. Install dependencies
pip install fastapi uvicorn selenium webdriver-manager \
            apscheduler httpx python-multipart \
            starlette itsdangerous

# 2. Set environment variables
export SENDER_EMAIL="your_gmail@gmail.com"
export APP_PASSWORD="your_gmail_app_password"
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"

# Optional: Google OAuth
export GOOGLE_CLIENT_ID="..."
export GOOGLE_CLIENT_SECRET="..."

# 3. Run
uvicorn main:app --reload --port 8000
```

Open http://127.0.0.1:8000

---

## 📋 Supported Platforms

| Platform   | Domain          | Price Selectors                    |
|------------|-----------------|-------------------------------------|
| Flipkart   | flipkart.com    | `div._30jeq3`, `div.Nx9bqj`        |
| Amazon.in  | amazon.in       | `span.a-price-whole`, `#priceblock` |
| Myntra     | myntra.com      | `span.pdp-price strong`            |
| Snapdeal   | snapdeal.com    | `span#selling-price-id`            |

Auto-detected from the URL — no manual selection needed.

---

## 🔐 Security Notes

- All credentials loaded from **environment variables only** — never hardcoded
- Session secret key auto-generated if not set
- Alert dedup prevents email spam (24-hour cooldown per product/user)
- Demo login accepts any email + 6-char password — replace with bcrypt for production

---

## 📂 File Structure

```
price-tracker/
├── main.py           # FastAPI app + inline HTML UI
├── scraper.py        # Multi-platform Selenium scraper
├── database.py       # SQLite with context managers
├── email_service.py  # HTML email alerts (no hardcoded creds)
├── scheduler.py      # APScheduler 6h price checks
├── test_email.py     # Email smoke test
└── prices.db         # SQLite database (auto-created)
```

---

## 🔮 Future Enhancements

- ML price prediction (Prophet / ARIMA)
- Webhook / Telegram alerts
- Price history charts (Chart.js)
- Multi-currency support
- Docker deployment
=======
# dti_2.1
This project is a smart multi-platform price tracker built with FastAPI, SQLite, Selenium, and HTML templates. It lets a user log in, add product URLs from supported shopping sites, store a target price, track the latest known price, and get an email alert when the product reaches or drops below the target
>>>>>>> origin/main
