#!/usr/bin/env python3
"""Walmart restock monitor.

Checks a single Walmart product page and sends a push notification the moment
it flips from out-of-stock to in-stock. Uses ntfy.sh (free, no account needed).
Designed to run on GitHub Actions every ~15 min.

All secrets are read from environment variables (set as GitHub Actions Secrets).
Nothing sensitive is ever hardcoded.
"""
import json
import os
import re
import sys

import requests

PRODUCT_URL = os.environ.get("PRODUCT_URL", "PASTE_WALMART_PRODUCT_URL_HERE")
STATE_FILE = "state.json"

_id_match = re.search(r"/ip/[^/]*/(\d+)", PRODUCT_URL)
TARGET_ITEM_ID = _id_match.group(1) if _id_match else ""

SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "")
SCRAPER_ENDPOINT = "https://api.scraperapi.com"

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BLOCK_MARKERS = ["robot or human", "px-captcha", "verify your identity",
                 "access denied", "/blocked"]


def fetch_html(url):
    try:
        if SCRAPER_API_KEY:
            r = requests.get(
                SCRAPER_ENDPOINT,
                params={"api_key": SCRAPER_API_KEY, "url": url, "country_code": "us"},
                timeout=60,
            )
        else:
            r = requests.get(url, headers=HEADERS, timeout=30)
        return r.status_code, r.text
    except requests.RequestException as e:
        print("Request error:", e)
        return None, ""


def looks_blocked(status, body):
    if status != 200:
        return True
    if len(body) < 5000:
        return True
    low = body.lower()
    return any(m in low for m in BLOCK_MARKERS)


ID_KEYS = ("usItemId", "productId", "itemId", "id")


def collect_availability(obj, found):
    if isinstance(obj, dict):
        status = obj.get("availabilityStatus")
        if isinstance(status, str):
            item_id = None
            for k in ID_KEYS:
                v = obj.get(k)
                if isinstance(v, str) and v.isdigit():
                    item_id = v
                    break
            found.append((item_id, status))
        for v in obj.values():
            collect_availability(v, found)
    elif isinstance(obj, list):
        for item in obj:
            collect_availability(item, found)


def detect_in_stock(body):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', body, re.S)
    if not m:
        return None, "no __NEXT_DATA__ block found (page may be blocked or changed)"
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None, "__NEXT_DATA__ present but did not parse as JSON"

    found = []
    collect_availability(data, found)
    if not found:
        return None, "no availabilityStatus fields found in the page JSON"

    for item_id, status in found:
        if TARGET_ITEM_ID and item_id == TARGET_ITEM_ID:
            return (status.upper() == "IN_STOCK", f"item {item_id}: {status}")

    summary = ", ".join(f"{i or '?'}={s}" for i, s in found[:8])
    return None, (f"no node matched item {TARGET_ITEM_ID or '(none in URL)'}; "
                  f"found instead: {summary}")


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def send_notification(text):
    if not NTFY_TOPIC:
        print("!! NTFY_TOPIC not set — would have sent:", text)
        return
    r = requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=text.encode("utf-8"),
        headers={"Title": "Walmart Restock Alert", "Priority": "high", "Tags": "shopping_cart"},
        timeout=30,
    )
    print("ntfy.sh status:", r.status_code)
    if r.status_code >= 300:
        print(r.text)


def main():
    if "PASTE_WALMART" in PRODUCT_URL:
        sys.exit("Set the PRODUCT_URL secret first.")

    status, body = fetch_html(PRODUCT_URL)
    if looks_blocked(status, body):
        print(f"BLOCKED or bad response (status={status}, {len(body)} bytes). "
              "If this keeps happening, set the SCRAPER_API_KEY secret. Skipping run.")
        return

    in_stock, how = detect_in_stock(body)
    print(f"Detected in_stock={in_stock}  ({how})")
    if in_stock is None:
        print("Could not read stock status - page structure may have changed. "
              "Paste this run's HTML to me and I'll fix the parser.")
        return

    state = load_state()
    was_in_stock = state.get("in_stock", False)
    state["in_stock"] = in_stock
    save_state(state)

    if in_stock and not was_in_stock:
        send_notification("IN STOCK at Walmart!\n" + PRODUCT_URL)
        print("Restock alert sent.")
    else:
        print("No out->in transition; no alert.")


if __name__ == "__main__":
    main()
