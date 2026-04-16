# scraper.py
"""
Multi-platform price scraper.
Supports: Flipkart · Amazon India · Myntra · Snapdeal
"""
import re
import time
from typing import Optional, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1280,900")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )


def _parse_price(text: str) -> Optional[int]:
    """Convert '₹74,900' or '74900' → 74900."""
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _try_selectors(driver, selectors: list, wait_sec: int = 15) -> Optional[str]:
    """Try each CSS selector in order, return first matched text."""
    wait = WebDriverWait(driver, wait_sec)
    for selector in selectors:
        try:
            el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            text = el.text.strip()
            if text:
                return text
        except Exception:
            continue
    return None


def _fallback_rupee_scan(driver) -> Optional[str]:
    """Last-resort: scan all elements for a ₹ price pattern."""
    elements = driver.find_elements(By.XPATH, "//*[contains(text(),'₹')]")
    for el in elements:
        txt = el.text.strip()
        if re.match(r"₹\s?\d{1,3}(,\d{3})*", txt):
            return txt
    return None


def _extract_title(driver, selectors: list) -> Optional[str]:
    for selector in selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            text = el.text.strip()
            if text:
                return text[:200]
        except Exception:
            continue
    return None


# ── Platform scrapers ─────────────────────────────────────────────────────────

def _scrape_flipkart(driver, url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    driver.get(url)
    # Dismiss login popup
    try:
        WebDriverWait(driver, 4).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button._2KpZ6l._2doB4z"))
        ).click()
    except Exception:
        pass

    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")

    price_text = _try_selectors(driver, [
        "div._30jeq3._16Jk6d",
        "div._30jeq3",
        "div.Nx9bqj.CxhGGd",
        "div._3I9_wc._2p6lqe",
    ]) or _fallback_rupee_scan(driver)

    title = _extract_title(driver, [
        "span.B_NuCI",
        "h1.yhB1nd span",
        "h1._6EBuvT span",
    ])
    return price_text, _parse_price(price_text), title


def _scrape_amazon(driver, url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    driver.get(url)
    time.sleep(2)

    price_text = _try_selectors(driver, [
        "span.a-price-whole",
        "span#priceblock_ourprice",
        "span#priceblock_dealprice",
        "span.apexPriceToPay span.a-offscreen",
        "span#price_inside_buybox",
        "span.a-color-price",
    ])
    if price_text:
        price_text = "₹" + price_text.replace(",", "").strip(".") if "₹" not in price_text else price_text

    title = _extract_title(driver, [
        "span#productTitle",
        "h1.a-size-large",
    ])
    return price_text, _parse_price(price_text), title


def _scrape_myntra(driver, url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    driver.get(url)
    time.sleep(3)

    price_text = _try_selectors(driver, [
        "span.pdp-price strong",
        "span.pdp-discounted-price strong",
        "div.pdp-price",
        "span.pdp-price",
    ]) or _fallback_rupee_scan(driver)

    title = _extract_title(driver, [
        "h1.pdp-title",
        "h1.pdp-name",
        "div.pdp-name",
    ])
    return price_text, _parse_price(price_text), title


def _scrape_snapdeal(driver, url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    driver.get(url)
    time.sleep(2)

    price_text = _try_selectors(driver, [
        "span#selling-price-id",
        "div.payBlkBig",
        "span.lfloat.product-price",
    ]) or _fallback_rupee_scan(driver)

    title = _extract_title(driver, [
        "h1.pdp-e-i-head",
        "h1#pdpProductName",
    ])
    return price_text, _parse_price(price_text), title


# ── Dispatcher ────────────────────────────────────────────────────────────────

PLATFORM_MAP = {
    "flipkart.com":  ("flipkart",  _scrape_flipkart),
    "amazon.in":     ("amazon",    _scrape_amazon),
    "myntra.com":    ("myntra",    _scrape_myntra),
    "snapdeal.com":  ("snapdeal",  _scrape_snapdeal),
}

SUPPORTED_PLATFORMS = list(PLATFORM_MAP.keys())


def detect_platform(url: str) -> Optional[str]:
    for domain in PLATFORM_MAP:
        if domain in url:
            return PLATFORM_MAP[domain][0]
    return None


def get_product_price(url: str) -> Tuple[Optional[str], Optional[int], str, Optional[str]]:
    """
    Scrape a product URL from any supported platform.

    Returns: (price_text, price_number, platform_name, product_title)
    Example: ("₹74,900", 74900, "flipkart", "Apple iPhone 15")
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
        return price_text, price_number, platform_key, title
    except Exception as exc:
        print(f"[Scraper] Error on {url}: {exc}")
        return None, None, platform_key or "unknown", None
    finally:
        driver.quit()


# Backward-compatible alias for old code that calls get_flipkart_price
def get_flipkart_price(url: str) -> Tuple[Optional[str], Optional[int]]:
    price_text, price_number, _, _ = get_product_price(url)
    return price_text, price_number
