"""
Fuel Price Analytics Engine
==============================
Analyzes the relationship between global conflicts, oil prices,
exchange rates, and South African fuel costs.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def load_oil_prices(path: str = None) -> pd.DataFrame:
    """Load Brent crude oil price data."""
    if path is None:
        path = str(DATA_DIR / "brent_oil_prices.csv")
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return df


def load_conflicts(path: str = None) -> pd.DataFrame:
    """Load conflict/event data."""
    if path is None:
        path = str(DATA_DIR / "conflicts.csv")
    df = pd.read_csv(path)
    df["start_date"] = pd.to_datetime(df["start_date"])
    df["end_date"] = pd.to_datetime(df["end_date"])
    return df


def load_sa_fuel_prices(path: str = None) -> pd.DataFrame:
    """Load SA pump prices and exchange rates."""
    if path is None:
        path = str(DATA_DIR / "sa_fuel_prices.csv")
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return df


def load_sa_levies(path: str = None) -> pd.DataFrame:
    """Load SA fuel levy breakdown over time."""
    if path is None:
        path = str(DATA_DIR / "sa_fuel_levies.csv")
    df = pd.read_csv(path)
    df["effective_date"] = pd.to_datetime(df["effective_date"])
    df["year"] = df["effective_date"].dt.year
    return df


def merge_oil_and_fuel(oil_df: pd.DataFrame, fuel_df: pd.DataFrame) -> pd.DataFrame:
    """Merge oil prices with SA fuel prices on nearest date."""
    merged = pd.merge_asof(
        fuel_df.sort_values("date"),
        oil_df[["date", "brent_usd", "event_tag"]].sort_values("date"),
        on="date",
        direction="nearest",
    )
    # Calculate barrel-to-pump ratio (1 barrel = ~159 litres)
    if "petrol_95_inland" in merged.columns and "brent_usd" in merged.columns:
        merged["barrel_in_zar"] = merged["brent_usd"] * merged["zar_usd"]
        merged["barrel_per_litre_zar"] = merged["barrel_in_zar"] / 159
        merged["pump_premium"] = merged["petrol_95_inland"] - merged["barrel_per_litre_zar"]
        merged["pump_premium_pct"] = (merged["pump_premium"] / merged["petrol_95_inland"]) * 100
    return merged


def conflict_impact_analysis(oil_df: pd.DataFrame, conflicts_df: pd.DataFrame) -> pd.DataFrame:
    """Analyze oil price before, during, and after each conflict."""
    results = []

    for _, conflict in conflicts_df.iterrows():
        tag = conflict["event_tag"]
        start = conflict["start_date"]
        end = conflict["end_date"]
        duration_days = (end - start).days

        # Pre-conflict: 6 months before
        pre_mask = (oil_df["date"] >= start - pd.Timedelta(days=180)) & (oil_df["date"] < start)
        pre_prices = oil_df.loc[pre_mask, "brent_usd"]

        # During conflict
        during_mask = (oil_df["date"] >= start) & (oil_df["date"] <= end)
        during_prices = oil_df.loc[during_mask, "brent_usd"]

        # Post-conflict: 6 months after
        post_mask = (oil_df["date"] > end) & (oil_df["date"] <= end + pd.Timedelta(days=180))
        post_prices = oil_df.loc[post_mask, "brent_usd"]

        pre_avg = pre_prices.mean() if len(pre_prices) > 0 else None
        during_avg = during_prices.mean() if len(during_prices) > 0 else None
        during_peak = during_prices.max() if len(during_prices) > 0 else None
        post_avg = post_prices.mean() if len(post_prices) > 0 else None

        price_change_pct = None
        if pre_avg and during_peak:
            price_change_pct = ((during_peak - pre_avg) / pre_avg) * 100

        results.append({
            "event_tag": tag,
            "event_name": conflict["event_name"],
            "region": conflict["region"],
            "start_date": start,
            "end_date": end,
            "duration_days": duration_days,
            "pre_avg_usd": round(pre_avg, 2) if pre_avg else None,
            "during_avg_usd": round(during_avg, 2) if during_avg else None,
            "during_peak_usd": round(during_peak, 2) if during_peak else None,
            "post_avg_usd": round(post_avg, 2) if post_avg else None,
            "price_change_pct": round(price_change_pct, 1) if price_change_pct else None,
        })

    return pd.DataFrame(results)


def sa_impact_during_conflicts(merged_df: pd.DataFrame, conflicts_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate SA pump price impact during each conflict."""
    results = []

    for _, conflict in conflicts_df.iterrows():
        start = conflict["start_date"]
        end = conflict["end_date"]

        pre_mask = (merged_df["date"] >= start - pd.Timedelta(days=180)) & (merged_df["date"] < start)
        during_mask = (merged_df["date"] >= start) & (merged_df["date"] <= end)

        pre_prices = merged_df.loc[pre_mask, "petrol_95_inland"]
        during_prices = merged_df.loc[during_mask, "petrol_95_inland"]
        pre_zar = merged_df.loc[pre_mask, "zar_usd"]
        during_zar = merged_df.loc[during_mask, "zar_usd"]

        pre_pump = pre_prices.mean() if len(pre_prices) > 0 else None
        during_pump = during_prices.mean() if len(during_prices) > 0 else None
        peak_pump = during_prices.max() if len(during_prices) > 0 else None
        pre_rand = pre_zar.mean() if len(pre_zar) > 0 else None
        during_rand = during_zar.mean() if len(during_zar) > 0 else None

        pump_change = None
        if pre_pump and peak_pump:
            pump_change = ((peak_pump - pre_pump) / pre_pump) * 100

        rand_change = None
        if pre_rand and during_rand:
            rand_change = ((during_rand - pre_rand) / pre_rand) * 100

        results.append({
            "event_name": conflict["event_name"],
            "pre_pump_price": round(pre_pump, 2) if pre_pump else None,
            "peak_pump_price": round(peak_pump, 2) if peak_pump else None,
            "pump_change_pct": round(pump_change, 1) if pump_change else None,
            "pre_zar_usd": round(pre_rand, 2) if pre_rand else None,
            "during_zar_usd": round(during_rand, 2) if during_rand else None,
            "rand_change_pct": round(rand_change, 1) if rand_change else None,
        })

    return pd.DataFrame(results)


def levy_analysis(levies_df: pd.DataFrame) -> dict:
    """Analyze levy trends over time."""
    latest = levies_df.iloc[-1]
    earliest = levies_df.iloc[0]

    return {
        "current_total_levy": latest["total_levies"],
        "current_levy_pct": latest["levy_pct_of_pump"],
        "earliest_total_levy": earliest["total_levies"],
        "earliest_levy_pct": earliest["levy_pct_of_pump"],
        "levy_increase_rands": latest["total_levies"] - earliest["total_levies"],
        "levy_increase_pct": ((latest["total_levies"] - earliest["total_levies"]) / earliest["total_levies"]) * 100,
        "general_fuel_levy": latest["general_fuel_levy"],
        "raf_levy": latest["raf_levy"],
        "customs_excise": latest["customs_excise"],
        "pipeline_levy": latest["pipeline_levy"],
        "slate_levy": latest["slate_levy"],
        "dsml_levy": latest["dsml_levy"],
    }


def project_fuel_price(merged_df: pd.DataFrame, months_ahead: int = 12,
                       brent_scenario: float = None, zar_scenario: float = None) -> pd.DataFrame:
    """Project future SA fuel prices based on scenarios."""
    latest = merged_df.iloc[-1]

    if brent_scenario is None:
        # Use average of last 6 months trend
        recent = merged_df.tail(6)
        brent_trend = recent["brent_usd"].pct_change().mean()
        brent_scenario = latest["brent_usd"]
    if zar_scenario is None:
        recent = merged_df.tail(6)
        zar_trend = recent["zar_usd"].pct_change().mean()
        zar_scenario = latest["zar_usd"]

    projections = []
    last_date = latest["date"]
    current_brent = brent_scenario
    current_zar = zar_scenario

    # Historical correlation: pump price ~ (brent * zar / 159) + levies + margin
    latest_levy = 6.926  # Current total levies
    latest_margin = latest["pump_premium"] if "pump_premium" in latest.index else 8.0

    for m in range(1, months_ahead + 1):
        proj_date = last_date + pd.DateOffset(months=m)

        # Apply small random variation for realism
        brent_var = current_brent * (1 + np.random.normal(0, 0.02))
        zar_var = current_zar * (1 + np.random.normal(0, 0.01))

        barrel_zar = brent_var * zar_var
        barrel_per_litre = barrel_zar / 159
        projected_pump = barrel_per_litre + latest_levy + (latest_margin * 0.5)

        projections.append({
            "date": proj_date,
            "brent_usd": round(brent_var, 2),
            "zar_usd": round(zar_var, 2),
            "projected_pump_price": round(projected_pump, 2),
            "type": "projection",
        })

    return pd.DataFrame(projections)


def scenario_calculator(brent_usd: float, zar_usd: float, total_levies: float = 6.926) -> dict:
    """Calculate pump price for a given Brent/ZAR scenario."""
    barrel_zar = brent_usd * zar_usd
    barrel_per_litre = barrel_zar / 159

    # BFP components: barrel cost + shipping + insurance + margins
    shipping_insurance = 0.45
    wholesale_margin = 0.35
    retail_margin = 0.28
    delivery_cost = 0.32

    bfp = barrel_per_litre + shipping_insurance
    pump_price = bfp + total_levies + wholesale_margin + retail_margin + delivery_cost

    return {
        "brent_usd": brent_usd,
        "zar_usd": zar_usd,
        "barrel_zar": round(barrel_zar, 2),
        "barrel_per_litre": round(barrel_per_litre, 2),
        "bfp": round(bfp, 2),
        "total_levies": round(total_levies, 2),
        "margins_delivery": round(wholesale_margin + retail_margin + delivery_cost, 2),
        "estimated_pump_price": round(pump_price, 2),
    }


def generate_all_charts(output_dir: str = "output"):
    """Generate all analytics charts to PNG files."""
    Path(output_dir).mkdir(exist_ok=True)

    oil_df = load_oil_prices()
    conflicts_df = load_conflicts()
    fuel_df = load_sa_fuel_prices()
    levies_df = load_sa_levies()
    merged = merge_oil_and_fuel(oil_df, fuel_df)

    # --- 1. Oil Price with Conflict Overlays ---
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(oil_df["date"], oil_df["brent_usd"], color="#e67e22", linewidth=1.5)

    conflict_colors = {
        "gulf_war": "#e74c3c", "iraq_war": "#c0392b", "libya_conflict": "#9b59b6",
        "isis_syria": "#8e44ad", "russia_ukraine_war": "#2980b9",
        "israel_hamas_war": "#e67e22", "middle_east_escalation": "#d35400",
        "saudi_russia_price_war": "#27ae60", "saudi_aramco_attack": "#f39c12",
        "us_iran_sanctions": "#1abc9c", "war_on_terror": "#34495e",
    }

    for _, c in conflicts_df.iterrows():
        color = conflict_colors.get(c["event_tag"], "#95a5a6")
        ax.axvspan(c["start_date"], c["end_date"], alpha=0.2, color=color, label=c["event_name"])

    ax.set_title("Brent Crude Oil Price & Global Conflicts", fontsize=14, fontweight="bold")
    ax.set_ylabel("USD per Barrel")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=7, ncol=2)
    plt.tight_layout()
    fig.savefig(f"{output_dir}/oil_with_conflicts.png", dpi=150)
    plt.close()

    # --- 2. SA Pump Price Over Time ---
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(fuel_df["date"], fuel_df["petrol_95_inland"], "o-", color="#e74c3c",
            linewidth=1.5, markersize=3, label="95 Inland")
    ax.plot(fuel_df["date"], fuel_df["petrol_95_coastal"], "o-", color="#3498db",
            linewidth=1.5, markersize=3, label="95 Coastal")
    ax.fill_between(fuel_df["date"], fuel_df["petrol_95_coastal"],
                     fuel_df["petrol_95_inland"], alpha=0.1, color="#e74c3c")
    ax.set_title("SA Petrol Price — Coastal vs Inland (95 ULP)", fontsize=14, fontweight="bold")
    ax.set_ylabel("Rands per Litre")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(f"{output_dir}/sa_pump_prices.png", dpi=150)
    plt.close()

    # --- 3. Levy Breakdown Stack ---
    fig, ax = plt.subplots(figsize=(14, 6))
    levy_cols = ["general_fuel_levy", "raf_levy", "customs_excise", "pipeline_levy", "slate_levy", "dsml_levy"]
    levy_labels = ["General Fuel Levy", "RAF Levy", "Customs & Excise", "Pipeline Levy", "Slate Levy", "DSML"]
    levy_colors = ["#e74c3c", "#e67e22", "#f1c40f", "#2ecc71", "#3498db", "#9b59b6"]

    bottom = np.zeros(len(levies_df))
    for col, label, color in zip(levy_cols, levy_labels, levy_colors):
        vals = levies_df[col].values
        ax.bar(levies_df["effective_date"], vals, bottom=bottom,
               label=label, color=color, width=200)
        bottom += vals

    ax.set_title("SA Fuel Levy Breakdown Over Time", fontsize=14, fontweight="bold")
    ax.set_ylabel("Rands per Litre")
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    fig.savefig(f"{output_dir}/levy_breakdown.png", dpi=150)
    plt.close()

    # --- 4. Barrel vs Pump Price ---
    fig, ax1 = plt.subplots(figsize=(14, 6))
    ax2 = ax1.twinx()

    ax1.plot(merged["date"], merged["brent_usd"], color="#e67e22", linewidth=1.5, label="Brent (USD/barrel)")
    ax2.plot(merged["date"], merged["petrol_95_inland"], color="#e74c3c", linewidth=1.5, label="95 Inland (R/litre)")

    ax1.set_ylabel("USD per Barrel", color="#e67e22")
    ax2.set_ylabel("Rands per Litre", color="#e74c3c")
    ax1.set_title("Brent Crude vs SA Pump Price", fontsize=14, fontweight="bold")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    ax1.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(f"{output_dir}/barrel_vs_pump.png", dpi=150)
    plt.close()

    print(f"  Charts saved to {output_dir}/")


def print_full_report():
    """Print a complete analytics report to the console."""
    oil_df = load_oil_prices()
    conflicts_df = load_conflicts()
    fuel_df = load_sa_fuel_prices()
    levies_df = load_sa_levies()
    merged = merge_oil_and_fuel(oil_df, fuel_df)

    impact = conflict_impact_analysis(oil_df, conflicts_df)
    sa_impact = sa_impact_during_conflicts(merged, conflicts_df)
    levy_info = levy_analysis(levies_df)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║           FUEL PRICE ANALYTICS REPORT                    ║
║     Global Conflicts & SA Pump Price Impact               ║
╚══════════════════════════════════════════════════════════╝

  CONFLICT IMPACT ON OIL PRICES
  ────────────────────────────────""")

    for _, row in impact.iterrows():
        print(f"\n  {row['event_name']}")
        print(f"    Pre-conflict avg:  ${row['pre_avg_usd']}/barrel")
        print(f"    Peak during:       ${row['during_peak_usd']}/barrel")
        print(f"    Price spike:       {row['price_change_pct']:+.1f}%")

    print(f"""
  SA PUMP PRICE IMPACT
  ────────────────────────────────""")

    for _, row in sa_impact.iterrows():
        if row["pre_pump_price"] and row["peak_pump_price"]:
            print(f"\n  {row['event_name']}")
            print(f"    Pre-conflict:  R{row['pre_pump_price']:.2f}/L")
            print(f"    Peak:          R{row['peak_pump_price']:.2f}/L  ({row['pump_change_pct']:+.1f}%)")
            if row["rand_change_pct"]:
                print(f"    Rand moved:    {row['rand_change_pct']:+.1f}%")

    print(f"""
  LEVY BREAKDOWN (Current)
  ────────────────────────────────
  Total levies:        R{levy_info['current_total_levy']:.3f}/L
  As % of pump price:  {levy_info['current_levy_pct']:.1f}%

  General Fuel Levy:   R{levy_info['general_fuel_levy']:.3f}
  RAF Levy:            R{levy_info['raf_levy']:.3f}
  Customs & Excise:    R{levy_info['customs_excise']:.3f}
  Pipeline Levy:       R{levy_info['pipeline_levy']:.3f}
  Slate Levy:          R{levy_info['slate_levy']:.3f}
  DSML Levy:           R{levy_info['dsml_levy']:.3f}

  Since {levies_df['year'].min()}:
  Levy increase:       R{levy_info['levy_increase_rands']:.3f}  ({levy_info['levy_increase_pct']:+.0f}%)
""")

    generate_all_charts()


if __name__ == "__main__":
    print_full_report()
