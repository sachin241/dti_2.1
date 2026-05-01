# 🔍 Email Alert Pipeline Audit & Fixes

## 📋 Root Cause Analysis

### **Primary Issue: Silent Failures**
The original code had minimal logging and swallowed exceptions, making production debugging impossible.

### **Secondary Issues Found:**

1. **Database Query Incompatibility**
   - `get_all_tracked_products()` used raw SQL without PostgreSQL/SQLite branching
   - Could fail silently on NeonDB (PostgreSQL)

2. **Insufficient Logging**
   - Scheduler used `print()` instead of proper logging
   - No visibility into SMTP failures
   - No startup verification

3. **Exception Handling**
   - Broad `except Exception` blocks hid real errors
   - No differentiation between recoverable vs critical failures

4. **Health Monitoring**
   - Basic `/health` endpoint provided no diagnostic info
   - No way to verify scheduler/database status

---

## ✅ Fixes Applied

### **1. Comprehensive Logging System**

#### **Scheduler Logging** (`scheduler.py`)
```python
# Added structured logging with levels
logger.info(f"[Scheduler] Price check started at {start_time}")
logger.debug(f"[Scheduler] Scraping price for: {url}")
logger.error(f"[Scheduler] Error processing {url}: {exc}", exc_info=True)
```

**Benefits:**
- ✅ Timestamped logs for debugging
- ✅ Different log levels (INFO, DEBUG, ERROR)
- ✅ Exception tracebacks with `exc_info=True`
- ✅ Step-by-step progress tracking

#### **Email Service Logging** (`email_service.py`)
```python
logger.info(f"[Email] Attempting to send alert to {email}")
logger.error(f"[Email] SMTP Authentication failed: {exc}")
logger.debug(f"[Email] Connected to SMTP server")
```

**Benefits:**
- ✅ SMTP connection status
- ✅ Authentication verification
- ✅ Credential validation
- ✅ Send success/failure tracking

#### **Startup Logging** (`main.py`)
```python
print(f"[Startup] Environment: IS_RENDER={IS_RENDER}, ENABLE_SCHEDULER={ENABLE_SCHEDULER}")
print(f"[Startup] Database URL set: {bool(os.getenv('DATABASE_URL'))}")
```

**Benefits:**
- ✅ Environment variable verification
- ✅ Database initialization status
- ✅ Scheduler startup confirmation

### **2. Database Compatibility Fix**

#### **PostgreSQL Support** (`database.py`)
```python
def get_all_tracked_products() -> List[dict]:
    with get_db() as conn:
        if IS_POSTGRES:
            # PostgreSQL-specific query
        else:
            # SQLite-specific query
```

**Benefits:**
- ✅ Works with both SQLite (local) and PostgreSQL (Render/NeonDB)
- ✅ Proper parameter binding for both databases
- ✅ No more silent query failures

### **3. Enhanced Health Check**

#### **Diagnostic Endpoint** (`/health`)
```json
{
  "status": "ok",
  "environment": {
    "is_render": true,
    "enable_scheduler": true,
    "database_url_set": true,
    "is_postgres": true
  },
  "scheduler": {
    "enabled": true,
    "running": true,
    "jobs": [{
      "id": "price_check_job",
      "next_run": "2026-05-01T18:00:00+05:30"
    }]
  },
  "database": {
    "connection_ok": true,
    "product_count": 15,
    "user_count": 3,
    "alert_count": 2
  }
}
```

**Benefits:**
- ✅ Real-time scheduler status
- ✅ Database connection verification
- ✅ Data counts for validation
- ✅ Environment configuration check

### **4. Debug Endpoint**

#### **Manual Price Check Trigger** (`POST /debug/trigger-price-check`)
```bash
curl -X POST https://your-app.onrender.com/debug/trigger-price-check
```

**Benefits:**
- ✅ Test alerts without waiting 6 hours
- ✅ Immediate feedback on pipeline issues
- ✅ Safe background execution

---

## 🔧 How to Debug Production Issues

### **Step 1: Check Application Health**
```bash
curl https://your-app.onrender.com/health
```

**Expected Response:**
```json
{
  "status": "ok",
  "scheduler": {
    "enabled": true,
    "running": true,
    "jobs": [/* job details */]
  },
  "database": {
    "connection_ok": true,
    "product_count": 5
  }
}
```

**If Issues Found:**
- `scheduler.running: false` → Scheduler not started
- `database.connection_ok: false` → Database connection failed
- `product_count: 0` → No tracked products

### **Step 2: Check Application Logs**
```bash
# In Render dashboard → Logs tab
# Look for these patterns:
```

**Successful Startup:**
```
[Startup] Environment: IS_RENDER=True, ENABLE_SCHEDULER=True
[Startup] Database URL set: True
[Startup] Database initialized successfully
[Startup] Price scheduler started successfully
[Scheduler] Started — next run at 2026-05-01 18:00:00 IST
```

**Successful Price Check:**
```
[Scheduler] Price check started at 2026-05-01 12:00:00
[Scheduler] Found 3 tracked product(s)
[Scheduler] Processing 1/3: [flipkart] https://www.flipkart.com/... (email: user@example.com)
[Scheduler] Successfully scraped price: ₹1,299
[Scheduler] Target reached! Current: ₹1,299 <= Target: ₹1,500
[Scheduler] Sending alert email to user@example.com
[Email] Alert sent successfully to user@example.com
[Scheduler] Summary: 3 processed, 1 alerts sent, 0 errors
```

### **Step 3: Manual Testing**
```bash
# Trigger immediate price check
curl -X POST https://your-app.onrender.com/debug/trigger-price-check
```

**Check logs immediately after** to see the full pipeline execution.

### **Step 4: Email-Specific Debugging**

**If emails not sending:**
1. Check SMTP credentials in Render env vars
2. Look for these log patterns:
   ```
   [Email] SENDER_EMAIL set: True
   [Email] APP_PASSWORD set: True
   [Email] Connecting to SMTP server...
   [Email] Login successful
   ```

**Common Email Issues:**
- `SMTPAuthenticationError` → Invalid Gmail credentials
- `SMTPConnectError` → Network/firewall issues
- `SENDER_EMAIL set: False` → Environment variable not set

### **Step 5: Database Debugging**

**If no products found:**
```sql
-- Check via NeonDB dashboard or psql
SELECT COUNT(*) FROM products;
SELECT url, email, target_price FROM products LIMIT 5;
```

**If database connection fails:**
- Check `DATABASE_URL` format
- Verify NeonDB connection string
- Check Render environment variables

---

## 🚀 Deployment Checklist

### **Render Environment Variables**
```bash
ENABLE_SCHEDULER=true
DATABASE_URL=postgresql://user:pass@host/db
GEMINI_API_KEY=your_key
SENDER_EMAIL=your_gmail@gmail.com
APP_PASSWORD=your_app_password
```

### **Verification Steps**
1. ✅ Deploy to Render
2. ✅ Check `/health` endpoint
3. ✅ Verify scheduler is running
4. ✅ Confirm database connection
5. ✅ Test manual price check
6. ✅ Monitor logs for 24 hours

### **Expected Behavior**
- Scheduler starts on app startup
- Price checks run every 6 hours
- Emails sent when targets reached
- Dedup prevents duplicate alerts
- All activity logged with timestamps

---

## 📊 Monitoring & Alerts

### **Key Metrics to Monitor**
- Scheduler job execution frequency
- Email send success rate
- Database connection stability
- Product count changes

### **Alert Conditions**
- ❌ No scheduler jobs running
- ❌ Database connection failures
- ❌ Email send failures > 10%
- ❌ No price checks in 7+ hours

### **Log Patterns to Watch**
```
✅ [Scheduler] Started — next run at...
✅ [Email] Alert sent successfully to...
✅ [Startup] Price scheduler started successfully

❌ [Scheduler] Failed to start scheduler
❌ [Email] SMTP Authentication failed
❌ [Database] Connection failed
```

---

## 🔍 Troubleshooting Guide

### **Issue: Scheduler Not Starting**
**Symptoms:** `/health` shows `"scheduler": {"running": false}`
**Causes:**
- `ENABLE_SCHEDULER=false` (check env var)
- Database initialization failed
- Import errors in scheduler.py

**Fix:**
1. Set `ENABLE_SCHEDULER=true` in Render
2. Check startup logs for errors
3. Verify database connection

### **Issue: No Products Found**
**Symptoms:** `"product_count": 0` in health check
**Causes:**
- Database migration issues
- Wrong database connection
- Products stored in different database

**Fix:**
1. Check database directly via NeonDB dashboard
2. Verify `DATABASE_URL` is correct
3. Check if app is using SQLite vs PostgreSQL

### **Issue: Emails Not Sending**
**Symptoms:** Price checks run but no emails
**Causes:**
- SMTP credentials missing/invalid
- Gmail app password expired
- Network restrictions

**Fix:**
1. Verify `SENDER_EMAIL` and `APP_PASSWORD` env vars
2. Generate new Gmail app password
3. Check SMTP logs for specific errors

### **Issue: Database Connection Errors**
**Symptoms:** `"database": {"connection_ok": false}`
**Causes:**
- Invalid `DATABASE_URL`
- NeonDB instance down
- SSL certificate issues

**Fix:**
1. Verify NeonDB connection string format
2. Check NeonDB dashboard for instance status
3. Add `?sslmode=require` to connection string

---

## 📝 Code Changes Summary

| File | Changes | Impact |
|------|---------|--------|
| `scheduler.py` | Added comprehensive logging, better error handling | ✅ Full visibility into price checking pipeline |
| `email_service.py` | Added SMTP logging, credential validation | ✅ Email send issues now diagnosable |
| `database.py` | Fixed PostgreSQL compatibility | ✅ Works with both SQLite and PostgreSQL |
| `main.py` | Enhanced startup logging, health check, debug endpoint | ✅ Production monitoring and debugging |

---

## 🎯 Next Steps

1. **Deploy the updated code** to Render
2. **Check `/health` endpoint** for status
3. **Monitor logs** for the next 24 hours
4. **Test manual trigger** if needed
5. **Verify email delivery** when targets are hit

The enhanced logging will now show exactly where the pipeline is failing, making production issues much easier to diagnose and fix.

---

*Audit completed: May 1, 2026*  
*Status: Production-ready with full diagnostics* ✅