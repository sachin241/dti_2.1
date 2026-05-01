# Project Research: DTi-2.1 Price Tracker

Prepared from source inspection on 2026-04-30.

## 1. Project Summary

This project is a multi-platform price tracking web application built with FastAPI, SQLite, Selenium, Jinja2 templates, and SMTP email alerts. Its main goal is to let a user:

- sign in with email/password or Google OAuth
- add product URLs from supported shopping sites
- store a target price per product
- check live prices manually
- run automated background price checks every 6 hours
- send email alerts when a tracked product reaches the target price
- view dashboard, analytics, and comparison pages
- use an AI shopping assistant backed by Gemini

## 2. Supported Platforms

The scraper currently supports:

- Flipkart
- Amazon India
- Myntra
- Snapdeal

Platform detection is done from the product URL in `scraper.py`.

## 3. Main Technology Stack

Backend:

- FastAPI
- Starlette session middleware
- Jinja2 templates

Scraping:

- Selenium
- Chrome WebDriver
- webdriver-manager

Storage:

- SQLite (`prices.db`)

Background jobs:

- APScheduler

Email:

- Python `smtplib` over Gmail SMTP SSL

AI assistant:

- `google-genai`

Frontend:

- Server-rendered HTML templates
- custom CSS
- Chart.js
- GSAP on the login page

## 4. High-Level Architecture

```text
Browser
  -> FastAPI app (main.py)
      -> scraper.py        for live product price extraction
      -> database.py       for SQLite reads/writes
      -> email_service.py  for SMTP alerts
      -> scheduler.py      for 6-hour recurring checks
      -> Gemini API        for AI shopping assistant replies
```

## 5. Core Files and Responsibilities

`main.py`

- application entry point
- loads environment variables
- configures sessions and static files
- starts database initialization and scheduler
- defines auth, profile, tracking, dashboard, analytics, compare, and chat routes

`database.py`

- manages SQLite connection lifecycle with a context manager
- creates and migrates tables
- stores products, user login data, and alert history
- provides read/write helper functions

`scraper.py`

- creates a headless Chrome driver
- detects the platform from the URL
- contains separate scraping routines for Flipkart, Amazon, Myntra, and Snapdeal
- extracts both product title and numeric price

`email_service.py`

- builds HTML and plain-text alert emails
- uses environment-based Gmail credentials
- sends target-price alerts

`scheduler.py`

- runs `check_prices()` every 6 hours in `Asia/Kolkata`
- refreshes all tracked products
- inserts new price rows
- sends deduplicated alerts

`templates/`

- `login.html`: animated sign-in page with optional Google login
- `index.html`: landing page after login
- `track.html`: add product URL and target price
- `dashboard.html`: tracked product overview
- `analytics.html`: chart-based statistics
- `compare.html`: live cross-platform comparison
- `profile.html`: avatar, password, and preference UI
- `base.html`: shared layout, navbar, theme toggle, chatbot widget

## 6. Database Model

The current SQLite schema includes:

### `products`

- `id`
- `url`
- `platform`
- `product_name`
- `email`
- `price`
- `target_price`
- `created_at`

Important behavior:

- every new manual check or scheduler refresh inserts another row
- latest state is usually derived by selecting the newest row per URL or per URL/email pair
- history is preserved for analytics

### `user_logins`

- `email`
- `provider`
- `last_login_at`
- `password`
- `picture`

### `alert_log`

- `id`
- `url`
- `email`
- `price`
- `sent_at`

Used to prevent duplicate email alerts inside a 24-hour window.

## 7. User Flow

1. User signs in through email/password or Google OAuth.
2. User opens `/track` and submits a product URL, alert email, and target price.
3. The app calls `get_product_price()` and stores the current price in SQLite.
4. If the live price is at or below target, an email alert is queued.
5. The scheduler later re-checks all tracked products every 6 hours.
6. Dashboard and analytics pages read the stored tracking history.
7. Compare mode refreshes live prices for matching tracked products in parallel.
8. The chatbot can answer shopping questions using Gemini and user tracking context.

## 8. Main Routes

Authentication:

- `GET /login`
- `POST /login`
- `GET /logout`
- `GET /auth/google`
- `GET /auth/google/callback`

Profile:

- `GET /profile`
- `POST /profile/password`
- `POST /profile/avatar`

Tracking and views:

- `GET /`
- `GET /track`
- `POST /track`
- `POST /track/delete`
- `GET /dashboard`
- `GET /analytics`
- `GET /compare`

APIs:

- `GET /api/compare`
- `POST /api/chat`

## 9. Environment and Configuration

The inspected configuration files indicate these environment keys are used:

- `GEMINI_API_KEY`
- `SECRET_KEY`
- `SENDER_EMAIL`
- `APP_PASSWORD`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`

Operational note:

- the debug log shows that email credentials were missing in some earlier runs and present in later runs, so email delivery appears environment-dependent rather than permanently broken

## 10. Functional Strengths

- clear separation between app routes, scraping, storage, scheduling, and email logic
- automatic schema-upgrade behavior in `init_db()`
- duplicate alert suppression through `alert_log`
- support for both manual refresh and scheduled refresh
- live compare endpoint uses parallel refreshes with `ThreadPoolExecutor`
- analytics page uses stored historical rows instead of only latest values
- static avatar upload and resize flow is already implemented
- Gemini assistant can incorporate the user's tracked products into its prompt

## 11. Research Findings and Risks

### A. README is currently broken

`README.md` contains unresolved merge conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) and mixed encoding artifacts. This means the top-level project documentation is not currently trustworthy as-is.

### B. Password storage is weak for production

Passwords are hashed with plain SHA-256 in `main.py` instead of a password-specific algorithm such as bcrypt or argon2. This is acceptable for a demo but not for a production authentication system.

### C. `requirements.txt` appears incomplete

The code uses Pillow in the avatar upload flow:

- `from PIL import Image`

But `Pillow` is not listed in `requirements.txt`. A clean environment may fail when profile image upload is used.

### D. Some profile settings are UI-only

The profile page contains toggles for:

- email alerts
- weekly summary
- appearance mode
- currency
- timezone

Only theme switching is implemented client-side. The rest do not appear to persist to the database or server configuration.

### E. Delete behavior removes full product history for that user and URL

`delete_tracked_product()` deletes all rows for a given `email` and `url`, not just the latest tracking entry. This may be fine, but it removes analytics history for that tracked product.

### F. Compare page chart is not based on true historical comparison data

The compare page renders a "Price trend simulation (7 days)" chart from synthetic step values in client-side JavaScript rather than using the real `history` returned by the compare API.

### G. Scraping reliability remains a moving target

The scraper includes multiple fallback selectors and even an Amazon HTTP fallback, which is good. However, e-commerce DOM structures change often, so selector maintenance will remain an ongoing requirement.

## 12. Notable Implementation Details

- scheduler timezone is explicitly set to `Asia/Kolkata`
- scheduler avoids duplicate concurrent runs with `max_instances=1`
- scheduler does not fire immediately on startup because `next_run_time=None`
- sessions are cookie-based through Starlette middleware
- `prices.db` is the default database file name
- the app creates `static/avatars` automatically on startup
- login currently behaves like a lightweight auto-registration flow for new email/password users

## 13. Suggested Next Improvements

1. Fix `README.md` and replace the conflicted content with clean setup and feature documentation.
2. Replace SHA-256 password hashing with bcrypt or argon2.
3. Add `Pillow` to `requirements.txt`.
4. Persist profile preferences instead of keeping them as visual-only controls.
5. Decide whether deleting a product should also delete historical analytics rows.
6. Use real comparison history in `compare.html` instead of simulated chart data.
7. Add automated tests for auth, tracking, scheduler logic, and alert deduplication.
8. Consider moving scraper jobs into a task queue if product volume grows.

## 14. Conclusion

This is a solid feature-rich prototype of a smart price tracker with scraping, scheduling, email alerts, analytics, and AI assistance already connected. The project is strongest as a full-stack demo or academic project and is close to being a polished portfolio app. Its main gaps are around production-hardening, documentation cleanup, dependency completeness, and a few frontend features that currently look more complete than their backend support.
