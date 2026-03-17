"""
Live Data Fetcher
====================
Pulls latest oil prices, exchange rates, and SA fuel data
from reliable public sources and updates the CSV files used
by the dashboard.

Sources:
  - Oil:   Alpha Vantage (free key) → Yahoo Finance fallback
  - Forex: ExchangeRate-API (free, no key) → Alpha Vantage FX
  - Fuel:  AA.co.za scraper → DMRE gazette PDF → manual fallback

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
from pathlib import Path
from datetime import datetime, timedelta

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("Note: Install requests — pip install requests")

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

DATA_DIR = Path(__file__).parent / "data"
ENV_FILE = Path(__file__).parent / ".env"

# ── Config ──────────────────────────────────────────────────
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; OrionTech-FuelTracker/2.0)"}


# ════════════════════════════════════════════════════════════
#  OIL PRICES
# ════════════════════════════════════════════════════════════

def fetch_oil_alpha_vantage() -> list[dict]:
    """Fetch Brent crude prices from Alpha Vantage (free, 25 req/day)."""
    if not HAS_REQUESTS or not ALPHA_VANTAGE_KEY:
        if not ALPHA_VANTAGE_KEY:
            print("  No ALPHA_VANTAGE_KEY set — skipping Alpha Vantage")
        return []

    print("  [Alpha Vantage] Fetching Brent crude prices...")

    url = "https://www.alphavantage.co/query"
    params = {"function": "BRENT", "interval": "monthly", "apikey": ALPHA_VANTAGE_KEY}

    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

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
        resp = requests.get(url, headers=HEADERS, timeout=15)
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


def update_oil_csv(new_records: list[dict]):
    """
    Merge new oil price records into the existing CSV,
    preserving hand-curated event_tag labels.
    """
    filepath = DATA_DIR / "brent_oil_prices.csv"

    # Load existing data with event_tags
    existing = {}
    if filepath.exists():
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing[row["date"]] = row

    added = 0
    updated = 0
    for rec in new_records:
        date = rec["date"]
        if date in existing:
            # Update price but keep existing event_tag
            old_price = existing[date].get("brent_usd", "")
            if str(rec["brent_usd"]) != str(old_price):
                existing[date]["brent_usd"] = rec["brent_usd"]
                updated += 1
        else:
            existing[date] = rec
            added += 1

    # Write sorted by date
    rows = sorted(existing.values(), key=lambda r: r["date"])
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "brent_usd", "event_tag"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"    Oil CSV: {added} added, {updated} updated, {len(rows)} total")


# ════════════════════════════════════════════════════════════
#  EXCHANGE RATES
# ════════════════════════════════════════════════════════════

def fetch_current_zar_usd() -> float | None:
    """Fetch current ZAR/USD rate from ExchangeRate-API (free, no key)."""
    if not HAS_REQUESTS:
        return None

    print("  [ExchangeRate-API] Fetching ZAR/USD...")

    try:
        resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("result") != "success":
            return None

        rate = data.get("rates", {}).get("ZAR")
        if rate:
            print(f"    Current ZAR/USD: R{rate:.2f}")
            return round(rate, 2)

    except Exception as e:
        print(f"    Error: {e}")

    return None


# ════════════════════════════════════════════════════════════
#  SA FUEL PRICES
# ════════════════════════════════════════════════════════════

def fetch_sa_fuel_from_aa() -> dict | None:
    """
    Scrape current SA fuel prices from AA (Automobile Association).
    Returns dict with coastal/inland prices or None.
    """
    if not HAS_REQUESTS:
        return None

    print("  [AA.co.za] Scraping fuel prices...")

    try:
        resp = requests.get("https://aa.co.za/fuel-pricing/", headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"    AA returned {resp.status_code}")
            return None

        html = resp.text

        # AA page has fuel prices in a structured format
        # Look for price patterns near fuel type labels
        result = {}

        # Try to extract prices — AA typically lists them as "R XX.XX"
        # Match patterns like "95 ULP" followed by prices
        price_pattern = r'R\s*(\d{1,2}\.\d{2})'
        all_prices = re.findall(price_pattern, html)

        if all_prices:
            prices = [float(p) for p in all_prices if 10 < float(p) < 35]
            if len(prices) >= 2:
                # AA typically lists coastal then inland
                result["petrol_95_coastal"] = prices[0]
                result["petrol_95_inland"] = prices[1] if len(prices) > 1 else None
                print(f"    95 Coastal: R{prices[0]:.2f}")
                if len(prices) > 1:
                    print(f"    95 Inland: R{prices[1]:.2f}")
                return result

        print("    Could not parse AA prices")
        return None

    except Exception as e:
        print(f"    AA scrape failed: {e}")
        return None


def fetch_sa_fuel_from_petrolprice() -> dict | None:
    """
    Scrape current SA fuel prices from petrol-price.co.za.
    Returns dict with fuel prices or None.
    """
    if not HAS_REQUESTS:
        return None

    print("  [petrol-price.co.za] Scraping fuel prices...")

    try:
        resp = requests.get("https://www.petrol-price.co.za/", headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"    petrol-price.co.za returned {resp.status_code}")
            return None

        html = resp.text
        result = {}

        # Look for price values — site shows inland and coastal
        # Patterns: "R20.30" or "2030" (cents)
        price_pattern = r'R\s*(\d{1,2}\.\d{2})'
        all_prices = re.findall(price_pattern, html)

        fuel_prices = [float(p) for p in all_prices if 10 < float(p) < 35]

        if fuel_prices:
            # Deduplicate keeping order
            seen = set()
            unique = []
            for p in fuel_prices:
                if p not in seen:
                    seen.add(p)
                    unique.append(p)
            fuel_prices = unique

            if len(fuel_prices) >= 2:
                # Sort to identify coastal (lower) and inland (higher)
                sorted_prices = sorted(fuel_prices[:6])
                result["petrol_95_coastal"] = sorted_prices[0]
                result["petrol_95_inland"] = sorted_prices[1] if len(sorted_prices) > 1 else None

                print(f"    Found {len(fuel_prices)} price values")
                for p in fuel_prices[:6]:
                    print(f"      R{p:.2f}")
                return result

        print("    Could not parse prices")
        return None

    except Exception as e:
        print(f"    Scrape failed: {e}")
        return None


def fetch_sa_fuel_from_dmre_pdf() -> dict | None:
    """
    Download and parse the latest DMRE fuel price breakdown PDF.
    The DMRE publishes monthly at a predictable URL pattern.
    """
    if not HAS_REQUESTS:
        return None

    print("  [DMRE PDF] Attempting gazette download...")

    # Try current month first, then previous month
    now = datetime.now()
    months_to_try = [
        now,
        now.replace(day=1) - timedelta(days=1),  # previous month
    ]

    for dt in months_to_try:
        month_name = dt.strftime("%B")
        year = dt.strftime("%Y")

        url = (
            f"https://www.dmre.gov.za/Portals/0/Resources/"
            f"Fuel%20Prices%20Adjustments/Fuel%20Prices%20Per%20Zone/"
            f"{year}/{month_name}%20{year}/Breakdown-of-Prices.pdf"
        )

        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 200 and len(resp.content) > 1000:
                print(f"    Downloaded {month_name} {year} gazette ({len(resp.content)} bytes)")
                return _parse_dmre_pdf(resp.content, dt)
        except Exception:
            pass

        print(f"    {month_name} {year} PDF not found")

    return None


def _parse_dmre_pdf(pdf_bytes: bytes, ref_date: datetime) -> dict | None:
    """
    Parse fuel prices from DMRE gazette PDF.
    DMRE format lists prices in cents/litre with entries like:
      "2030.00 c/l" for 95 ULP Inland = R20.30
    Each entry spans multiple lines with date, cents, fuel type, and region.
    """
    try:
        import pdfplumber
    except ImportError:
        print("    pdfplumber not installed — pip install pdfplumber")
        return _parse_dmre_pdf_basic(pdf_bytes, ref_date)

    import io
    result = {}

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = ""
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"

        if not text:
            print("    No text extracted from PDF")
            return None

        # DMRE format: price in cents appears near fuel type and region
        # e.g. "2030.00 c/l" followed by "(95 ULP &" and "Inland Region"
        # Strategy: find all cents values with their surrounding context

        # Extract all price blocks: cents value + nearby text
        # Pattern: number like 1947.00 or 1853.83 followed by "c/l"
        blocks = re.findall(
            r'(\d{3,4}(?:\.\d{1,3})?)\s*c/l.*?(?:(\d{2,3})\s*(?:ULP|ppm|%))?.*?(Inland|Coastal)',
            text, re.IGNORECASE | re.DOTALL
        )

        if not blocks:
            # Fallback: scan line by line with lookahead
            lines = text.split("\n")
            full_text = " ".join(lines)

            # Find cents values and map to fuel type + region from surrounding context
            cents_matches = list(re.finditer(r'(\d{3,4}(?:\.\d{1,3})?)\s*c/l', full_text))

            for match in cents_matches:
                cents_val = float(match.group(1))
                if cents_val < 500 or cents_val > 3500:
                    continue

                # Look at context around this match (200 chars before and after)
                start = max(0, match.start() - 200)
                end = min(len(full_text), match.end() + 200)
                context = full_text[start:end].lower()

                rands = round(cents_val / 100, 2)
                is_inland = "inland" in context
                is_coastal = "coastal" in context

                if "95" in context and "ulp" in context:
                    if is_inland:
                        result["petrol_95_inland"] = rands
                    elif is_coastal:
                        result["petrol_95_coastal"] = rands
                elif "93" in context and "ulp" in context:
                    if is_inland:
                        result["petrol_93_inland"] = rands
                    elif is_coastal:
                        result["petrol_93_coastal"] = rands
                elif "0.05%" in context and "0.005%" not in context:
                    if is_inland:
                        result["diesel_50ppm_inland"] = rands
                elif "0.005%" in context:
                    # Skip 500ppm diesel — we only track 50ppm
                    pass
        else:
            for cents_str, fuel_grade, region in blocks:
                rands = round(float(cents_str) / 100, 2)
                region_key = "inland" if "inland" in region.lower() else "coastal"
                if fuel_grade == "95":
                    result[f"petrol_95_{region_key}"] = rands
                elif fuel_grade == "93":
                    result[f"petrol_93_{region_key}"] = rands

        # DMRE format puts entries sequentially:
        # 93 Inland, 95 Inland, 93 Coastal, 95 Coastal, Diesel Inland...
        # If regex missed, try ordered extraction
        if not result:
            all_cents = re.findall(r'(\d{3,4}(?:\.\d{1,3})?)\s*c/l', text)
            prices = [round(float(c) / 100, 2) for c in all_cents if 500 < float(c) < 3500]

            if len(prices) >= 4:
                # DMRE order: 93 inland, 95 inland, 93 coastal, 95 coastal
                result["petrol_93_inland"] = prices[0]
                result["petrol_95_inland"] = prices[1]
                result["petrol_93_coastal"] = prices[2]
                result["petrol_95_coastal"] = prices[3]
            if len(prices) >= 5:
                result["diesel_50ppm_inland"] = prices[4]
            if len(prices) >= 6:
                result["diesel_50ppm_coastal"] = prices[5] if prices[5] < prices[4] else prices[4]

        if result:
            print(f"    Parsed from DMRE gazette:")
            for k, v in sorted(result.items()):
                print(f"      {k}: R{v:.2f}")
            return result

        print("    Could not parse structured prices from PDF")
        return None

    except Exception as e:
        print(f"    PDF parsing error: {e}")
        return None


def _parse_dmre_pdf_basic(pdf_bytes: bytes, ref_date: datetime) -> dict | None:
    """Basic PDF text extraction without pdfplumber."""
    # Try PyPDF2 as fallback
    try:
        from PyPDF2 import PdfReader
        import io
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""

        if text:
            # Same parsing logic as above
            cents_values = re.findall(r'(\d{4}\.\d{2})', text)
            fuel_prices = [round(float(c) / 100, 2) for c in cents_values if 1000 < float(c) < 3500]

            if len(fuel_prices) >= 2:
                return {
                    "petrol_95_coastal": fuel_prices[0],
                    "petrol_95_inland": fuel_prices[1],
                }
    except ImportError:
        print("    Neither pdfplumber nor PyPDF2 installed")
        print("    pip install pdfplumber  (recommended)")
    except Exception as e:
        print(f"    Basic PDF parse failed: {e}")

    return None


def fetch_sa_fuel_prices() -> dict | None:
    """
    Fetch latest SA fuel prices from multiple sources.
    Returns dict with price fields or None.
    Tries: AA → petrol-price.co.za → DMRE PDF
    """
    result = fetch_sa_fuel_from_aa()
    if result:
        return result

    result = fetch_sa_fuel_from_petrolprice()
    if result:
        return result

    result = fetch_sa_fuel_from_dmre_pdf()
    if result:
        return result

    print("    All fuel price sources failed")
    print("    Update manually from: https://aa.co.za/fuel-pricing/")
    return None


def update_fuel_csv(fuel_prices: dict, zar_rate: float | None):
    """
    Add a new row to sa_fuel_prices.csv with the latest prices.
    Only adds if the month doesn't already exist.
    """
    filepath = DATA_DIR / "sa_fuel_prices.csv"
    today = datetime.now().strftime("%Y-%m-01")  # Normalize to 1st of month

    # Read existing
    existing_dates = set()
    rows = []
    fieldnames = [
        "date", "petrol_95_coastal", "petrol_95_inland",
        "petrol_93_coastal", "petrol_93_inland",
        "diesel_50ppm_coastal", "diesel_50ppm_inland", "zar_usd",
    ]

    if filepath.exists():
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                fieldnames = reader.fieldnames
            for row in reader:
                existing_dates.add(row["date"])
                rows.append(row)

    if today in existing_dates:
        # Update existing row for this month
        for row in rows:
            if row["date"] == today:
                updated = False
                for key, val in fuel_prices.items():
                    if val is not None and key in fieldnames:
                        row[key] = val
                        updated = True
                if zar_rate:
                    row["zar_usd"] = zar_rate
                    updated = True
                if updated:
                    print(f"    Updated existing row for {today}")
                break
    else:
        # Create new row
        new_row = {"date": today}
        for key, val in fuel_prices.items():
            if val is not None:
                new_row[key] = val
        if zar_rate:
            new_row["zar_usd"] = zar_rate

        # Fill missing columns from previous row
        if rows:
            prev = rows[-1]
            for field in fieldnames:
                if field not in new_row or not new_row[field]:
                    if field in prev and prev[field]:
                        new_row[field] = prev[field]

        rows.append(new_row)
        print(f"    Added new row for {today}")

    # Write back
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    latest = rows[-1]
    print(f"    Latest: 95 Coastal R{latest.get('petrol_95_coastal', '?')}, "
          f"95 Inland R{latest.get('petrol_95_inland', '?')}, "
          f"ZAR/USD R{latest.get('zar_usd', '?')}")


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════

def update_all():
    """Fetch and update all data sources."""
    print("""
╔══════════════════════════════════════════════════════════╗
║         ORIONTECH FUEL TRACKER — DATA UPDATER            ║
║  Sources: Alpha Vantage, ExchangeRate-API, AA, DMRE      ║
╚══════════════════════════════════════════════════════════╝
""")

    if ALPHA_VANTAGE_KEY:
        masked = ALPHA_VANTAGE_KEY[:4] + "..." + ALPHA_VANTAGE_KEY[-4:]
        print(f"  Alpha Vantage key: {masked}")
    else:
        print("  Alpha Vantage key: NOT SET")
        print("    Get free key: https://www.alphavantage.co/support/#api-key")
        print()

    DATA_DIR.mkdir(exist_ok=True)

    # ── Oil prices ──
    print("\n  ── Oil Prices ──────────────────────────")
    oil_records = fetch_oil_prices()
    if oil_records:
        update_oil_csv(oil_records)
    else:
        print("    Using existing data (no live data fetched)")

    # ── Exchange rates ──
    print("\n  ── Exchange Rates ──────────────────────")
    zar_rate = fetch_current_zar_usd()

    # ── SA fuel prices ──
    print("\n  ── SA Fuel Prices ─────────────────────")
    fuel_prices = fetch_sa_fuel_prices()
    if fuel_prices:
        update_fuel_csv(fuel_prices, zar_rate)
    elif zar_rate:
        # At minimum update the exchange rate
        print("    No new fuel prices — updating ZAR rate only")
        update_fuel_csv({}, zar_rate)
    else:
        print("    No updates available")

    print(f"""
  ─────────────────────────────────────
  Done. Run the dashboard:
    streamlit run dashboard.py

  Data sources:
    Oil:   Alpha Vantage → Yahoo Finance (fallback)
    Forex: ExchangeRate-API (free, no key needed)
    Fuel:  AA.co.za → petrol-price.co.za → DMRE gazette PDF
""")


def update_oil_only():
    """Update only oil price data."""
    records = fetch_oil_prices()
    if records:
        update_oil_csv(records)


def update_forex_only():
    """Update only exchange rate data."""
    rate = fetch_current_zar_usd()
    if rate:
        print(f"  Current ZAR/USD: R{rate:.2f}")


def update_fuel_only():
    """Update only SA fuel price data."""
    zar_rate = fetch_current_zar_usd()
    fuel_prices = fetch_sa_fuel_prices()
    if fuel_prices:
        update_fuel_csv(fuel_prices, zar_rate)


if __name__ == "__main__":
    if "--oil" in sys.argv:
        update_oil_only()
    elif "--forex" in sys.argv:
        update_forex_only()
    elif "--fuel" in sys.argv:
        update_fuel_only()
    else:
        update_all()
