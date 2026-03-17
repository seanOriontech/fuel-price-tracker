# Fuel Price Tracker — Wars, Oil & What South Africans Pay

Interactive analytics dashboard showing how global conflicts impact oil prices and what South Africans end up paying at the pump. Tracks the Rand factor, government levies, and projects future prices.

## The Story

Oil prices spike when wars break out — but by the time it hits a South African pump, the impact is amplified by:
- **The Rand** — oil is priced in USD, and the ZAR has weakened ~660% since 1990
- **Government levies** — R6.93+ per litre in taxes (General Fuel Levy, RAF, DSML, etc.)
- **Regulated pricing** — SA pump prices are set monthly by DMRE, not the market

This dashboard tells that story with data.

## Features

### Conflict Analysis
- Brent crude price with conflict period overlays (Gulf War through Middle East 2024)
- Impact scoreboard — which war spiked oil the most?
- SA pump price impact during each conflict
- Rand movement correlation during conflicts

### Price Breakdown
- Barrel vs pump price comparison (dual-axis USD/ZAR)
- Coastal vs inland pricing gap
- Full levy breakdown stack chart (1990–2026)
- Government take as % of pump price over time

### Interactive Tools
- **"What If" Calculator** — slide Brent and ZAR/USD to see projected pump price
- **Pump price breakdown pie** — see exactly what makes up each litre
- **12-month projection** — based on current oil/forex trends

### Key Data
- Brent crude prices (1990–2026)
- SA pump prices — 95 ULP, 93 ULP, Diesel (coastal & inland)
- ZAR/USD exchange rates
- 11 major conflicts mapped and analyzed
- Full SA fuel levy history with 7 levy components

## Quick Start

```bash
cd fuel-price-tracker
pip install -r requirements.txt
streamlit run dashboard.py
```

## Update Live Data

```bash
python data_fetcher.py          # Pull latest oil & forex data
python data_fetcher.py --oil    # Oil prices only
python data_fetcher.py --forex  # Exchange rates only
```

## Project Structure

```
fuel-price-tracker/
├── dashboard.py              # Streamlit web dashboard
├── analytics.py              # Analytics engine
├── data_fetcher.py           # Live data API fetcher
├── requirements.txt
├── data/
│   ├── brent_oil_prices.csv  # Brent crude + conflict tags
│   ├── conflicts.csv         # War/conflict database
│   ├── sa_fuel_prices.csv    # SA pump prices + ZAR/USD
│   └── sa_fuel_levies.csv    # Full levy breakdown
├── output/                   # Generated charts
├── assets/                   # Logo & images
└── .streamlit/config.toml
```

## Conflicts Tracked

| Conflict | Year | Peak Oil Impact |
|----------|------|----------------|
| Gulf War | 1990 | +130% |
| Iraq War | 2003 | +60% |
| Libya Civil War | 2011 | +25% |
| ISIS/Syria | 2014 | +15% |
| Saudi-Russia Price War | 2020 | -71% |
| Russia-Ukraine War | 2022 | +50% |
| Israel-Hamas War | 2023 | +15% |
| Middle East Escalation | 2024 | +20% |

---
**Powered by OrionTech** — Data-Driven Intelligence
