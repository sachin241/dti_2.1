# 🛡️ Antigravity: The Development Chronicle (v2.1)

This document tracks the end-to-end evolution of the **Smart Price Tracker** project, detailing every major milestone, refactor, and enhancement implemented from scratch.

---

## 🏗️ Phase 1: Core Foundation & Scraping Reliability

**Objective:** Build a robust, multi-platform engine that doesn't break under site changes.

- **Multi-Platform Scraper:** Engineered a unified `scraper.py` using Selenium and WebDriverManager. 
    - Supports **Amazon India, Flipkart, Myntra, and Snapdeal**.
    - Implemented **dynamic CSS selectors** for each platform to handle layout shifts.
    - Replaced brittle `time.sleep()` calls with **Explicit Waits** (`WebDriverWait`) for faster, more reliable execution.
- **Background Scheduler:** Integrated `APScheduler` to run price checks every 6 hours (IST).
    - Added protection against task overlap (`coalesce=True`, `max_instances=1`).
    - Implemented a "No-Duplicate" alert logic (prevents spamming emails for the same price drop within 24 hours).
- **Database Architecture:** Built `database.py` using a context-manager pattern.
    - Ensures clean connection handling and prevents "Database Locked" errors.
    - Schema supports platform-specific metadata, alert logging, and product history.

---

## 🎨 Phase 2: The "Ember Noir" UI Transformation

**Objective:** Elevate a basic tool into a premium, high-end web application.

- **Design System:** Transitioned to the **Ember Noir** theme.
    - **Palette:** Warm charcoal backgrounds, vibrant ember orange accents, and sleek glassmorphism cards.
    - **Typography:** Switched to modern sans-serif fonts (Inter/Outfit) for a tech-forward feel.
- **Interactive Login Page:** Created a unique, creative sign-in experience.
    - Features a **"Interactive Lamp" animation**: The room starts dark, and clicking the lamp "switches on" the light to reveal the login form.
- **Advanced Analytics Dashboard:**
    - Integrated **Chart.js** to provide 6 distinct data-driven visualizations.
    - Metrics include Price Trends, Platform Price Distribution, Target Gap Analysis, and Savings Potential.
- **Responsive Navigation:** Implemented a custom mobile-first hamburger menu and a persistent, animated sidebar for desktop.

---

## 🔒 Phase 3: Security & Performance Audit

**Objective:** Hardening the application and ensuring data integrity.

- **Credential Management:** Scrubbed all hardcoded emails and passwords. 
    - Implemented a `.env` system using `python-dotenv`.
    - Fixed a critical bug where credentials wouldn't load if `os.getenv` was called before `load_dotenv`.
- **User Security:**
    - Implemented **password hashing** using SHA-256 (hashlib) for secure storage.
    - Added session-based authentication to protect private dashboards.
- **Image Processing:** Added an avatar upload system.
    - Uses **Pillow (PIL)** to auto-resize and center-crop user photos to a uniform 200×200 circular format.

---

## 🤖 Phase 4: AI Integration & Final Polish

**Objective:** Add a layer of intelligent interaction.

- **Antigravity Chatbot:** Integrated a sitewide AI assistant powered by **Google Gemini**.
    - The assistant has a specialized "Antigravity" personality.
    - It can analyze the user's tracking history and provide personalized product recommendations.
- **UI/UX Micro-animations:**
    - Hover-scaling on product cards.
    - Smooth fade-in transitions for page loads.
    - Branded, platform-specific HTML email alerts with "Buy Now" buttons.

---

## 📊 Project Stats At-a-Glance

| Feature | Status | Implementation Detail |
| :--- | :--- | :--- |
| **Platforms** | 4 | Amazon, Flipkart, Myntra, Snapdeal |
| **Theme** | Premium | Ember Noir / Glassmorphism |
| **Database** | SQLite | Context-manager safe |
| **Security** | High | Hashed passwords + `.env` |
| **AI** | Integrated | Google Gemini (Antigravity Assistant) |

---

> **Note:** This project is built as a standalone application with no external automation dependencies (like n8n), ensuring maximum privacy and speed.
