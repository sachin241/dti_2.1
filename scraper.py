# scraper.py
"""
Multi-platform price scraper.
Supports: Flipkart · Amazon India · Myntra · Snapdeal
"""
import os
import re
import shutil
import time
import urllib.request
from typing import Tuple, Optional

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


# ── Driver ─────────────────────────────────────────────────────────────────────

def _make_driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    chrome_binary = os.getenv("CHROME_BINARY_PATH") or shutil.which("chromium") or shutil.which("google-chrome")
    driver_path = os.getenv("CHROMEDRIVER_PATH") or shutil.which("chromedriver")

    if chrome_binary:
        options.binary_location = chrome_binary

    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--lang=en-IN")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # Speed optimizations
    options.page_load_strategy = "eager"  # Don't wait for images/stylesheets
    prefs = {"profile.managed_default_content_settings.images": 2}  # Disable images
    options.add_experimental_option("prefs", prefs)
    service = Service(driver_path) if driver_path else Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_price(text: str) -> Optional[int]:
    """Convert '₹74,900.00' or '74,900' or '74900' → 74900 (int)."""
    if not text:
        return None
    # Remove ₹ and spaces, then strip decimal portion
    cleaned = text.replace("₹", "").replace(",", "").replace(" ", "").strip()
    # Take only the integer portion (before decimal point)
    cleaned = cleaned.split(".")[0]
    digits = re.sub(r"[^\d]", "", cleaned)
    if not digits:
        return None
    val = int(digits)
    # Sanity check: reject prices below ₹1 or above ₹10 crore
    if val < 1 or val > 10_000_000:
        return None
    return val


def _wait_for_any(driver, selectors: list, timeout: int = 8) -> Optional[str]:
    """Return the text of the first matching CSS selector, or None."""
    wait = WebDriverWait(driver, timeout)
    for sel in selectors:
        try:
            el = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, sel)))
            text = el.text.strip() or el.get_attribute("textContent").strip()
            if text and re.search(r"\d", text):
                return text
        except Exception:
            continue
    return None


def _rupee_scan(driver) -> Optional[str]:
    """Last-resort: find any visible element containing a ₹ price."""
    try:
        els = driver.find_elements(By.XPATH, "//*[contains(text(),'₹')]")
        for el in els:
            try:
                txt = el.text.strip()
                if re.search(r"₹\s?\d{2,}", txt):
                    # Return the first price-like chunk
                    match = re.search(r"₹[\s\d,\.]+", txt)
                    if match:
                        return match.group(0).strip()
            except Exception:
                continue
    except Exception:
        pass
    return None


def _get_attr_price(driver, selectors: list) -> Optional[str]:
    """Try reading price from aria-label or content attributes (Amazon offscreen spans)."""
    for sel in selectors:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in els:
                for attr in ("textContent", "aria-label", "content"):
                    val = el.get_attribute(attr) or ""
                    if "₹" in val and re.search(r"\d{3}", val):
                        return val.strip()
        except Exception:
            continue
    return None


def _extract_title(driver, selectors: list) -> Optional[str]:
    for sel in selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            text = (el.text or el.get_attribute("textContent") or "").strip()
            if text:
                return text[:220]
        except Exception:
            continue
    return None


# ── Platform scrapers ─────────────────────────────────────────────────────────

def _scrape_flipkart(driver, url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    driver.get(url)

    # Dismiss login popup
    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button._2KpZ6l._2doB4z, button.hNksqM"))
        ).click()
    except Exception:
        pass

    time.sleep(0.4)
    driver.execute_script("window.scrollTo(0, 400);")
    time.sleep(0.2)

    price_text = _wait_for_any(driver, [
        # 2024-25 selectors
        "div.Nx9bqj.CxhGGd",
        "div.Nx9bqj",
        # older selectors
        "div._30jeq3._16Jk6d",
        "div._30jeq3",
        "div._3I9_wc._2p6lqe",
        "div._16Jk6d",
        "div.CEmiEU > div.Nx9bqj",
    ]) or _rupee_scan(driver)

    title = _extract_title(driver, [
        "span.VU-ZEz",       # 2024-25
        "h1._6EBuvT span",
        "span.B_NuCI",
        "h1 span",
    ])
    return price_text, _parse_price(price_text), title


def _scrape_amazon(driver, url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    # Ensure we hit the Indian store
    url = re.sub(r"amazon\.(com|co\.uk|de|fr|es|it|ca|com\.au)", "amazon.in", url)
    driver.get(url)
    time.sleep(1)

    price_text = _wait_for_any(driver, [
        # The most reliable 2024-25 selectors
        "span.a-price-whole",
        "#corePrice_desktop .a-price .a-offscreen",
        "#apex_offerDisplay_desktop .a-offscreen",
        "span#priceToPay .a-offscreen",
        "span.apexPriceToPay .a-offscreen",
        "span.a-price .a-offscreen",
        "#corePriceDisplay_desktop_feature_div .a-offscreen",
    ])

    # a-price-whole gives just the integer (e.g. "74,900") without ₹ symbol
    if price_text and "₹" not in price_text:
        # Try to prepend ₹ only if it looks like a number
        if re.search(r"^\d[\d,\.]*$", price_text.strip()):
            price_text = "₹" + price_text.strip()

    # Attribute-based fallback
    if not price_text:
        price_text = _get_attr_price(driver, [
            "span.a-price .a-offscreen",
            "span#priceToPay .a-offscreen",
        ])

    # DOM scan fallback
    if not price_text:
        price_text = _rupee_scan(driver)

    # HTTP fallback if Selenium was blocked
    if not _parse_price(price_text):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-IN,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
            html = urllib.request.urlopen(req, timeout=12).read().decode("utf-8", errors="ignore")

            # Extract title
            tm = re.search(r'<span id="productTitle"[^>]*>\s*([^<]+)\s*</span>', html)
            title_http = tm.group(1).strip() if tm else None

            # a-price-whole
            pm = re.search(r'class="a-price-whole">([^<]+)</span>', html)
            if not pm:
                pm = re.search(r'class="a-offscreen">₹([\d,]+)', html)
            if pm:
                raw = pm.group(1).replace(",", "").strip().split(".")[0]
                price_text = f"₹{int(raw):,}"
                title = title_http
                return price_text, _parse_price(price_text), title
        except Exception as e:
            print(f"[Amazon HTTP fallback] {e}")

    title = _extract_title(driver, [
        "span#productTitle",
        "h1.a-size-large span",
        "h1 span",
    ])
    return price_text, _parse_price(price_text), title


def _scrape_myntra(driver, url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    driver.get(url)
    time.sleep(1.5)  # Myntra is heavily JS-driven

    price_text = _wait_for_any(driver, [
        "span.pdp-price strong",
        "span.pdp-discounted-price strong",
        "div.pdp-price-container .pdp-price strong",
        "span.pdp-price",
        ".pdp-discounted-price",
        "p.pdp-price",
    ]) or _rupee_scan(driver)

    title = _extract_title(driver, [
        "h1.pdp-title",
        "h1.pdp-name",
        "div.pdp-name",
        "h1",
    ])
    return price_text, _parse_price(price_text), title


def _scrape_snapdeal(driver, url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    driver.get(url)
    time.sleep(1)

    price_text = _wait_for_any(driver, [
        "span.payBlkBig",
        "span#selling-price-id",
        "span.lfloat.product-price",
        "div.paymentBlock span.price",
        ".product-price",
    ]) or _rupee_scan(driver)

    title = _extract_title(driver, [
        "h1.pdp-e-i-head",
        "h1#pdpProductName",
        "h1",
    ])
    return price_text, _parse_price(price_text), title


# ── Dispatcher ─────────────────────────────────────────────────────────────────

PLATFORM_MAP = {
    "flipkart.com": ("flipkart", _scrape_flipkart),
    "amazon.in":    ("amazon",   _scrape_amazon),
    "myntra.com":   ("myntra",   _scrape_myntra),
    "snapdeal.com": ("snapdeal", _scrape_snapdeal),
}

SUPPORTED_PLATFORMS = list(PLATFORM_MAP.keys())


def detect_platform(url: str) -> Optional[str]:
    for domain, (pname, _) in PLATFORM_MAP.items():
        if domain in url:
            return pname
    return None


def get_product_price(url: str) -> Tuple[Optional[str], Optional[int], str, Optional[str]]:
    """
    Scrape a product URL from any supported platform.
    Returns: (price_text, price_number, platform_name, product_title)
    """
    platform_key = None
    scrape_fn    = None

    for domain, (pname, fn) in PLATFORM_MAP.items():
        if domain in url:
            platform_key = pname
            scrape_fn    = fn
            break

    if scrape_fn is None:
        return None, None, "unknown", None

    driver = _make_driver()
    try:
        price_text, price_number, title = scrape_fn(driver, url)
        # Ensure price_text always has ₹ symbol
        if price_number and price_text and "₹" not in price_text:
            price_text = f"₹{price_number:,}"
        return price_text, price_number, platform_key, title
    except Exception as exc:
        print(f"[Scraper] Error on {url}: {exc}")
        return None, None, platform_key or "unknown", None
    finally:
        try:
            driver.quit()
        except Exception:
            pass



# ── Cross-platform SEARCH scrapers ────────────────────────────────────────────

import urllib.parse


def _search_flipkart(driver, query: str):
    """Search Flipkart and return first result's price + URL."""
    search_url = f"https://www.flipkart.com/search?q={urllib.parse.quote(query)}&otracker=search"
    driver.get(search_url)
    # Dismiss login popup
    try:
        WebDriverWait(driver, 4).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button._2KpZ6l._2doB4z, button.hNksqM, button[class*='close']")
        )).click()
    except Exception:
        pass
    time.sleep(1.5)

    # Price selectors — updated for 2025
    price_text = _wait_for_any(driver, [
        "div.Nx9bqj.CxhGGd",
        "div.Nx9bqj",
        "div._30jeq3._16Jk6d",
        "div._30jeq3",
        "div.CEmiEU div.Nx9bqj",
        "div._25b18c div._30jeq3",
    ], timeout=8) or _rupee_scan(driver)
    price_num = _parse_price(price_text)

    product_url = None
    product_name = None
    try:
        # Updated link selectors for 2025 Flipkart layout
        for sel in ["a.CGtC98", "a._1fQZEK", "a.s1Q9rs", "a._2rpwqI", "div._13oc-S a", "a[href*='/p/']"]:
            try:
                link_el = driver.find_element(By.CSS_SELECTOR, sel)
                href = link_el.get_attribute("href") or ""
                if href and "/p/" in href:
                    product_url = href if href.startswith("http") else f"https://www.flipkart.com{href}"
                    break
            except Exception:
                continue
        for sel in ["div._4rR01T", "a.s1Q9rs", "div.KzDlHZ", "div._2WkVRV", "div.col-7-12 a div"]:
            try:
                name_el = driver.find_element(By.CSS_SELECTOR, sel)
                t = (name_el.text or "").strip()
                if t:
                    product_name = t[:150]
                    break
            except Exception:
                continue
    except Exception:
        pass

    if not product_url:
        product_url = search_url  # fallback to search page itself
    return price_num, product_url, product_name


def _search_amazon(driver, query: str):
    """Search Amazon.in for a product and return first result's price + URL."""
    search_url = f"https://www.amazon.in/s?k={urllib.parse.quote(query)}"
    driver.get(search_url)
    time.sleep(1.5)

    price_text = _wait_for_any(driver, [
        "span.a-price-whole",
        "span.a-price .a-offscreen",
        ".s-price-instructions-style span.a-price .a-offscreen",
    ], timeout=8) or _rupee_scan(driver)
    price_num = _parse_price(price_text)

    product_url = None
    product_name = None
    try:
        link_el = driver.find_element(By.CSS_SELECTOR,
            "div[data-component-type='s-search-result'] h2 a.a-link-normal")
        href = link_el.get_attribute("href") or ""
        product_url = href if href.startswith("http") else f"https://www.amazon.in{href}"
        product_name = (link_el.text or "").strip()[:150]
    except Exception:
        pass

    if not product_url:
        product_url = search_url
    return price_num, product_url, product_name


def _search_myntra(driver, query: str):
    """Search Myntra for a product and return first result's price + URL."""
    # Use proper search endpoint
    search_url = f"https://www.myntra.com/search?rawQuery={urllib.parse.quote(query)}"
    driver.get(search_url)
    time.sleep(2.5)

    price_text = _wait_for_any(driver, [
        "span.product-discountedPrice",
        "span.pdp-price strong",
        "div.product-price span",
        ".product-base .product-price",
        "span.product-strike",
    ], timeout=10) or _rupee_scan(driver)
    price_num = _parse_price(price_text)

    product_url = None
    product_name = None
    try:
        for sel in ["li.product-base a", "a.product-imageSliderContainer", ".product-base a[href]"]:
            try:
                link_el = driver.find_element(By.CSS_SELECTOR, sel)
                href = link_el.get_attribute("href") or ""
                if href:
                    product_url = href if href.startswith("http") else f"https://www.myntra.com{href}"
                    break
            except Exception:
                continue
        for sel in ["li.product-base h3.product-brand", "li.product-base h4.product-product", ".product-base .product-brand"]:
            try:
                name_el = driver.find_element(By.CSS_SELECTOR, sel)
                t = (name_el.text or "").strip()
                if t:
                    product_name = t[:150]
                    break
            except Exception:
                continue
    except Exception:
        pass

    if not product_url:
        product_url = search_url
    return price_num, product_url, product_name


def _search_snapdeal(driver, query: str):
    """Search Snapdeal for a product and return first result's price + URL."""
    search_url = f"https://www.snapdeal.com/search?keyword={urllib.parse.quote(query)}&sort=rlvncy"
    driver.get(search_url)
    time.sleep(2)

    price_text = _wait_for_any(driver, [
        "span.lfloat.product-price",
        "span.product-price",
        ".product-tuple-listing span.product-price",
        "div.product-desc-rating span",
    ], timeout=10) or _rupee_scan(driver)
    price_num = _parse_price(price_text)

    product_url = None
    product_name = None
    try:
        for sel in ["div.product-tuple-listing a.dp-widget-link", ".product-tuple-listing a[href*='snapdeal']", "a.dp-widget-link"]:
            try:
                link_el = driver.find_element(By.CSS_SELECTOR, sel)
                href = link_el.get_attribute("href") or ""
                if href:
                    product_url = href if href.startswith("http") else f"https://www.snapdeal.com{href}"
                    break
            except Exception:
                continue
        for sel in ["div.product-tuple-listing p.product-title", ".product-tuple-listing .product-title"]:
            try:
                name_el = driver.find_element(By.CSS_SELECTOR, sel)
                t = (name_el.text or "").strip()
                if t:
                    product_name = t[:150]
                    break
            except Exception:
                continue
    except Exception:
        pass

    if not product_url:
        product_url = search_url
    return price_num, product_url, product_name


SEARCH_MAP = {
    "flipkart": _search_flipkart,
    "amazon":   _search_amazon,
    "myntra":   _search_myntra,
    "snapdeal": _search_snapdeal,
}


def _search_one_platform(platform: str, search_fn, query: str) -> dict | None:
    """Run a single platform search in its own browser. Returns result dict or None."""
    driver = _make_driver()
    try:
        price_num, product_url, found_name = search_fn(driver, query)
        print(f"[CrossSearch] {platform}: price={price_num}, url={product_url}")
        if price_num and price_num > 0:
            return {
                "platform": platform,
                "price": price_num,
                "url": product_url or "",
                "name": found_name or query,
            }
        return None
    except Exception as e:
        print(f"[CrossSearch] {platform} failed: {e}")
        return None
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def cross_platform_search(product_name: str, source_platform: str = None) -> list:
    """
    Search all supported platforms for a product by name IN PARALLEL.
    Returns list of dicts: [{platform, price, url, name}]
    Uses one browser per platform concurrently for maximum speed.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not product_name:
        return []

    # Clean the query
    query = re.sub(r"(flipkart|amazon|myntra|snapdeal|\.com|\.in|https?://|www\.)", "", product_name, flags=re.I)
    query = re.sub(r"[^\w\s]", " ", query).strip()
    words = [w for w in query.split() if len(w) > 1][:8]
    query = " ".join(words)
    if not query:
        return []

    print(f"[CrossSearch] Parallel query: '{query}'")

    platforms_to_search = {
        p: fn for p, fn in SEARCH_MAP.items()
        if p != source_platform
    }

    results = []
    with ThreadPoolExecutor(max_workers=len(platforms_to_search)) as executor:
        futures = {
            executor.submit(_search_one_platform, platform, fn, query): platform
            for platform, fn in platforms_to_search.items()
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    return results


# Backward-compatible alias
def get_flipkart_price(url: str) -> Tuple[Optional[str], Optional[int]]:
    price_text, price_number, _, _ = get_product_price(url)
    return price_text, price_number
