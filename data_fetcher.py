"""
Live Data Fetcher
====================
Pulls latest oil prices, exchange rates, and SA fuel data
from reliable public APIs.

Sources:
  - Oil:   Alpha Vantage (free key) → fallback Yahoo Finance
  - Forex: ExchangeRate-API (free 1500 req/month) → fallback Open ER API
  - Fuel:  DMRE gazette scraper (energy.gov.za)

Setup:
  1. Get free Alpha Vantage key:  https://www.alphavantage.co/support/#api-key
  2. Set env var:  export ALPHA_VANTAGE_KEY=your_key_here
     (or add to .env file in this directory)

Usage:
    python data_fetcher.py              # Update all data
    python data_fetcher.py --oil        # Update oil prices only
    python data_fetcher.py --forex      # Update exchange rates only
    python data_fetcher.py --fuel       # Scrape latest SA pump prices
"""

import os
import re
import sys
import csv
import json
from pathlib import Path
from datetime import datetime, timedelta

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("Note: Install requests — pip install requests")

DATA_DIR = Path(__file__).parent / "data"
ENV_FILE = Path(__file__).parent / ".env"

# ── Config ──────────────────────────────────────────────────
# Load .env file if it exists
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "")


# ════════════════════════════════════════════════════════════
#  OIL PRICES
# ════════════════════════════════════════════════════════════

def fetch_oil_alpha_vantage() -> list[dict]:
    """
    Fetch Brent crude prices from Alpha Vantage.
    Free tier: 25 requests/day.
    Endpoint: WTI & Brent monthly via BRENT commodity function.
    """
    if not HAS_REQUESTS:
        print("  requests library required. pip install requests")
        return []

    if not ALPHA_VANTAGE_KEY:
        print("  No ALPHA_VANTAGE_KEY set — skipping Alpha Vantage")
        print("  Get a free key: https://www.alphavantage.co/support/#api-key")
        return []

    print("  [Alpha Vantage] Fetching Brent crude prices...")

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "BRENT",
        "interval": "monthly",
        "apikey": ALPHA_VANTAGE_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        # Check for API limit message
        if "Note" in data or "Information" in data:
            msg = data.get("Note", data.get("Information", ""))
            print(f"    API limit: {msg[:80]}")
            return []

        records = []
        for entry in data.get("data", []):
            val = entry.get("value", ".")
            if val != ".":
                records.append({
                    "date": entry["date"],
                    "brent_usd": round(float(val), 2),
                    "event_tag": "",
                })

        # Sort chronologically
        records.sort(key=lambda r: r["date"])

        print(f"    Got {len(records)} monthly data points")
        if records:
            print(f"    Latest: ${records[-1]['brent_usd']}/bbl ({records[-1]['date']})")
        return records

    except Exception as e:
        print(f"    Error: {e}")
        return []


def fetch_oil_yahoo_fallback() -> list[dict]:
    """Fallback: Fetch Brent crude from Yahoo Finance."""
    if not HAS_REQUESTS:
        return []

    print("  [Yahoo Finance] Fallback — fetching Brent crude...")

    end = int(datetime.now().timestamp())
    start = int((datetime.now() - timedelta(days=365 * 2)).timestamp())

    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/BZ=F"
        f"?period1={start}&period2={end}&interval=1mo"
    )

    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]

        records = []
        for ts, close in zip(timestamps, closes):
            if close is not None:
                dt = datetime.fromtimestamp(ts)
                records.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "brent_usd": round(close, 2),
                    "event_tag": "",
                })

        print(f"    Got {len(records)} monthly data points")
        return records

    except Exception as e:
        print(f"    Yahoo also failed: {e}")
        return []


def fetch_oil_prices() -> list[dict]:
    """Fetch oil prices — Alpha Vantage first, Yahoo fallback."""
    records = fetch_oil_alpha_vantage()
    if not records:
        records = fetch_oil_yahoo_fallback()
    return records


# ════════════════════════════════════════════════════════════
#  EXCHANGE RATES
# ════════════════════════════════════════════════════════════

def fetch_zar_exchangerate_api() -> list[dict]:
    """
    Fetch ZAR/USD from ExchangeRate-API.
    Free tier: 1500 requests/month, no key needed for open endpoint.
    """
    if not HAS_REQUESTS:
        return []

    print("  [ExchangeRate-API] Fetching ZAR/USD...")

    url = "https://open.er-api.com/v6/latest/USD"

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("result") != "success":
            print(f"    API error: {data.get('error-type', 'unknown')}")
            return []

        zar_rate = data.get("rates", {}).get("ZAR")
        if not zar_rate:
            print("    ZAR rate not found in response")
            return []

        last_update = data.get("time_last_update_utc", "")
        print(f"    Current ZAR/USD: R{zar_rate:.2f}")
        print(f"    Last updated: {last_update[:25]}")

        return [{
            "date": datetime.now().strftime("%Y-%m-%d"),
            "zar_usd": round(zar_rate, 2),
            "source": "exchangerate-api",
        }]

    except Exception as e:
        print(f"    Error: {e}")
        return []


def fetch_zar_alpha_vantage() -> list[dict]:
    """Fetch ZAR/USD monthly from Alpha Vantage forex endpoint."""
    if not HAS_REQUESTS or not ALPHA_VANTAGE_KEY:
        return []

    print("  [Alpha Vantage] Fetching ZAR/USD historical...")

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "FX_MONTHLY",
        "from_symbol": "USD",
        "to_symbol": "ZAR",
        "apikey": ALPHA_VANTAGE_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        if "Note" in data or "Information" in data:
            msg = data.get("Note", data.get("Information", ""))
            print(f"    API limit: {msg[:80]}")
            return []

        ts_key = "Time Series FX (Monthly)"
        time_series = data.get(ts_key, {})

        records = []
        for date_str, values in sorted(time_series.items()):
            close = values.get("4. close")
            if close:
                records.append({
                    "date": date_str,
                    "zar_usd": round(float(close), 2),
                    "source": "alpha-vantage",
                })

        print(f"    Got {len(records)} monthly data points")
        if records:
            latest = records[-1]
            print(f"    Latest: R{latest['zar_usd']:.2f}/$ ({latest['date']})")
        return records

    except Exception as e:
        print(f"    Error: {e}")
        return []


def fetch_zar_usd() -> list[dict]:
    """Fetch exchange rates — ExchangeRate-API first, Alpha Vantage historical."""
    records = fetch_zar_exchangerate_api()

    # Also grab historical if Alpha Vantage key is available
    if ALPHA_VANTAGE_KEY:
        historical = fetch_zar_alpha_vantage()
        if historical:
            # Merge: keep historical + add today's rate
            existing_dates = {r["date"] for r in historical}
            for r in records:
                if r["date"] not in existing_dates:
                    historical.append(r)
            return sorted(historical, key=lambda x: x["date"])

    return records


# ════════════════════════════════════════════════════════════
#  SA FUEL PRICES (DMRE Scraper)
# ════════════════════════════════════════════════════════════

def fetch_sa_fuel_prices() -> list[dict]:
    """
    Scrape latest SA fuel prices from DMRE (energy.gov.za).
    The DMRE publishes monthly fuel price adjustments.
    This attempts to get the latest published prices.
    """
    if not HAS_REQUESTS:
        return []

    print("  [DMRE] Scraping SA fuel prices...")

    # DMRE fuel price page
    url = "https://www.energy.gov.za/files/esources/petroleum/petroleum_fuelprices.html"

    try:
        resp = requests.get(url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (compatible; FuelTracker/1.0)"
        })

        if resp.status_code != 200:
            print(f"    DMRE page returned {resp.status_code}")
            return _try_sapia_fallback()

        html = resp.text

        # Look for price data in the page
        # DMRE typically has tables with current fuel prices
        # Pattern: look for petrol 95 prices in cents/litre
        records = _parse_dmre_html(html)

        if records:
            print(f"    Found {len(records)} fuel price entries")
            return records

        print("    Could not parse prices from DMRE page")
        return _try_sapia_fallback()

    except Exception as e:
        print(f"    DMRE scrape failed: {e}")
        return _try_sapia_fallback()


def _parse_dmre_html(html: str) -> list[dict]:
    """Parse fuel prices from DMRE HTML page."""
    records = []

    # Try to find price patterns — DMRE uses various formats
    # Common pattern: prices in cents like "2574.00" for R25.74
    # Look for Petrol 95 patterns
    patterns = [
        # Pattern: "Petrol 95 ULP ... 2574"
        r'(?:Petrol|95\s*ULP)[^0-9]*?(\d{3,4}(?:\.\d{1,2})?)',
        # Pattern: "R 25.74" or "R25.74"
        r'R\s*(\d{1,2}\.\d{2})',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            for match in matches[:4]:  # Take first few matches
                val = float(match)
                # If in cents, convert to rands
                if val > 100:
                    val = val / 100
                if 8 < val < 40:  # Sanity check for realistic fuel price
                    records.append({
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "price_type": "petrol_95",
                        "price_rands": round(val, 2),
                        "source": "dmre",
                    })
            break

    return records


def _try_sapia_fallback() -> list[dict]:
    """Fallback: try SAPIA (SA Petroleum Industry Association) for fuel data."""
    if not HAS_REQUESTS:
        return []

    print("  [SAPIA] Trying fallback...")

    try:
        url = "https://www.sapia.org.za/fuel-prices"
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; FuelTracker/1.0)"
        })

        if resp.status_code == 200:
            # Try basic pattern matching for prices
            matches = re.findall(r'R\s*(\d{1,2}\.\d{2})', resp.text)
            records = []
            for match in matches[:4]:
                val = float(match)
                if 8 < val < 40:
                    records.append({
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "price_type": "petrol_95",
                        "price_rands": round(val, 2),
                        "source": "sapia",
                    })
            if records:
                print(f"    Found {len(records)} prices from SAPIA")
                return records

    except Exception as e:
        print(f"    SAPIA fallback failed: {e}")

    print("    No live fuel price data available")
    print("    Update manually from: https://www.energy.gov.za/files/esources/petroleum/")
    return []


# ════════════════════════════════════════════════════════════
#  CSV UTILITIES
# ════════════════════════════════════════════════════════════

def append_to_csv(filepath: str, records: list[dict], key_field: str = "date"):
    """Append new records to an existing CSV, avoiding duplicates."""
    filepath = Path(filepath)

    existing_keys = set()
    existing_rows = []
    fieldnames = []

    if filepath.exists():
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            for row in reader:
                existing_keys.add(row.get(key_field, ""))
                existing_rows.append(row)

    new_records = [r for r in records if r.get(key_field, "") not in existing_keys]

    if not new_records:
        print(f"    No new records to add to {filepath.name}")
        return

    # Merge fieldnames
    if existing_rows:
        all_fields = list(dict.fromkeys(list(fieldnames) + list(new_records[0].keys())))
    else:
        all_fields = list(new_records[0].keys())

    all_rows = existing_rows + new_records

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"    Added {len(new_records)} new records to {filepath.name}")


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════

def update_all():
    """Fetch and update all data sources."""
    print("""
╔══════════════════════════════════════════════════════════╗
║              LIVE DATA FETCHER v2.0                      ║
║   Sources: Alpha Vantage, ExchangeRate-API, DMRE         ║
╚══════════════════════════════════════════════════════════╝
""")

    # Show config status
    if ALPHA_VANTAGE_KEY:
        masked = ALPHA_VANTAGE_KEY[:4] + "..." + ALPHA_VANTAGE_KEY[-4:]
        print(f"  Alpha Vantage key: {masked}")
    else:
        print("  Alpha Vantage key: NOT SET")
        print("    Get free key: https://www.alphavantage.co/support/#api-key")
        print("    Then: export ALPHA_VANTAGE_KEY=your_key")
        print()

    DATA_DIR.mkdir(exist_ok=True)

    # ── Oil prices ──
    print("\n  ── Oil Prices ──")
    oil_records = fetch_oil_prices()
    if oil_records:
        append_to_csv(str(DATA_DIR / "brent_oil_prices.csv"), oil_records)
    else:
        print("    Using existing sample data")

    # ── Exchange rates ──
    print("\n  ── Exchange Rates ──")
    forex_records = fetch_zar_usd()
    if forex_records:
        latest = forex_records[-1]
        print(f"    Latest ZAR/USD: R{latest['zar_usd']:.2f}")

    # ── SA fuel prices ──
    print("\n  ── SA Fuel Prices ──")
    fuel_records = fetch_sa_fuel_prices()
    if fuel_records:
        for r in fuel_records:
            print(f"    {r.get('price_type', 'fuel')}: R{r.get('price_rands', 0):.2f}")

    print(f"""
  ─────────────────────────────────────
  Done. Run the dashboard:
    streamlit run dashboard.py

  Data sources:
    Oil:   Alpha Vantage → Yahoo Finance (fallback)
    Forex: ExchangeRate-API → Alpha Vantage FX (historical)
    Fuel:  DMRE gazette → SAPIA (fallback)
""")


if __name__ == "__main__":
    if "--oil" in sys.argv:
        records = fetch_oil_prices()
        if records:
            append_to_csv(str(DATA_DIR / "brent_oil_prices.csv"), records)
    elif "--forex" in sys.argv:
        records = fetch_zar_usd()
        if records:
            print(f"  Latest ZAR/USD: R{records[-1]['zar_usd']:.2f}")
    elif "--fuel" in sys.argv:
        records = fetch_sa_fuel_prices()
        if records:
            for r in records:
                print(f"  {r.get('price_type', 'fuel')}: R{r.get('price_rands', 0):.2f}")
    else:
        update_all()
