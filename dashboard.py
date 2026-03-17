"""
Fuel Price Tracker Dashboard
================================
Interactive Streamlit dashboard showing how global conflicts
impact oil prices and South African fuel costs.

Run with:  streamlit run dashboard.py
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

sys.path.insert(0, str(Path(__file__).parent))
from analytics import (
    load_oil_prices, load_conflicts, load_sa_fuel_prices, load_sa_levies,
    merge_oil_and_fuel, conflict_impact_analysis, sa_impact_during_conflicts,
    levy_analysis, project_fuel_price, scenario_calculator,
)

APP_DIR = Path(__file__).parent
LOGO_PATH = APP_DIR / "assets" / "oriontech-logo.png"
ORIONTECH_URL = "https://www.oriontech.co.za"
ORIONTECH_LINKEDIN = "https://www.linkedin.com/company/oriontechsa/"

# --- OrionTech Brand Palette ---
OT_PRIMARY = "#336dff"
OT_PRIMARY_DARK = "#1439e1"
OT_CYAN = "#06b6d4"
OT_CYAN_DARK = "#0891b2"
OT_BG_DARK = "#0a0f1a"
OT_BG_CARD = "#111827"
OT_TEXT = "#f0f4f8"
OT_TEXT_MUTED = "#94a3b8"
OT_RED = "#ef4444"
OT_EMERALD = "#10b981"
OT_AMBER = "#f59e0b"
OT_VIOLET = "#8b5cf6"
OT_ORANGE = "#f97316"

# Chart style matching OrionTech dark theme
CHART_BG = "#0a0f1a"
CHART_FACE = "#111827"
CHART_GRID = "#1e293b"
CHART_TEXT = "#cbd5e1"

st.set_page_config(page_title="Fuel Price Tracker | OrionTech", page_icon="⛽", layout="wide")

# --- Google Analytics ---
st.markdown("""
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-2K2D3YHPRV"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-2K2D3YHPRV');
</script>
""", unsafe_allow_html=True)

# --- Inject OrionTech CSS ---
st.markdown(f"""
<style>
    /* Hide Streamlit Cloud toolbar (Deploy/GitHub buttons) */
    [data-testid="stToolbar"] {{
        display: none !important;
    }}
    .stDeployButton {{
        display: none !important;
    }}
    #MainMenu {{
        visibility: hidden;
    }}
    header {{
        visibility: hidden;
    }}
    footer {{
        visibility: hidden;
    }}
    [data-testid="manage-app-button"] {{
        display: none !important;
    }}

    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@600;700;800&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
    }}
    h1, h2, h3 {{
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
    }}
    h1 {{
        background: linear-gradient(135deg, {OT_PRIMARY} 0%, {OT_CYAN} 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }}
    .stMetric > div {{
        background: {OT_BG_CARD};
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 1rem;
    }}
    .stMetric label {{
        color: {OT_TEXT_MUTED} !important;
    }}
    [data-testid="stMetricValue"] {{
        color: {OT_TEXT} !important;
        font-family: 'Outfit', sans-serif !important;
    }}
    div[data-testid="stExpander"] {{
        background: {OT_BG_CARD};
        border: 1px solid #1e293b;
        border-radius: 12px;
    }}
    .oriontech-banner {{
        background: linear-gradient(135deg, {OT_PRIMARY_DARK} 0%, {OT_CYAN_DARK} 100%);
        border-radius: 16px;
        padding: 1.5rem 2rem;
        text-align: center;
        margin-top: 2rem;
    }}
    .oriontech-banner a {{
        color: white !important;
        text-decoration: none;
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        font-size: 1.4em;
    }}
    .oriontech-banner a:hover {{
        opacity: 0.9;
    }}
    .oriontech-banner .tagline {{
        color: rgba(255,255,255,0.75);
        font-size: 0.85em;
        margin-top: 0.3rem;
    }}
    .oriontech-banner .powered {{
        color: rgba(255,255,255,0.6);
        font-size: 0.8em;
        margin-bottom: 0.3rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }}
    section[data-testid="stSidebar"] {{
        background: {OT_BG_CARD};
        border-right: 1px solid #1e293b;
    }}
    .highlight-stat {{
        background: linear-gradient(135deg, rgba(51,109,255,0.1), rgba(6,182,212,0.1));
        border: 1px solid rgba(51,109,255,0.3);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }}
</style>
""", unsafe_allow_html=True)

CONFLICT_COLORS = {
    "gulf_war": OT_RED, "iraq_war": "#dc2626", "libya_conflict": OT_VIOLET,
    "isis_syria": "#7c3aed", "russia_ukraine_war": OT_PRIMARY,
    "israel_hamas_war": OT_AMBER, "middle_east_escalation": OT_ORANGE,
    "saudi_russia_price_war": OT_EMERALD, "saudi_aramco_attack": "#eab308",
    "us_iran_sanctions": OT_CYAN, "war_on_terror": "#64748b",
}


def _style_chart(fig, ax):
    """Apply OrionTech dark styling to matplotlib charts."""
    fig.patch.set_facecolor(CHART_BG)
    ax.set_facecolor(CHART_FACE)
    ax.tick_params(colors=CHART_TEXT, which="both", labelcolor=CHART_TEXT)
    ax.xaxis.label.set_color(CHART_TEXT)
    ax.yaxis.label.set_color(CHART_TEXT)
    ax.title.set_color(OT_TEXT)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_color(CHART_TEXT)
    for spine in ax.spines.values():
        spine.set_color(CHART_GRID)
    ax.grid(True, alpha=0.2, color=CHART_GRID)


def _style_dual_axis(fig, ax1, ax2):
    """Apply OrionTech dark styling to dual-axis charts."""
    fig.patch.set_facecolor(CHART_BG)
    ax1.set_facecolor(CHART_FACE)
    for a in (ax1, ax2):
        a.tick_params(which="both", colors=CHART_TEXT, labelcolor=CHART_TEXT)
        a.title.set_color(OT_TEXT)
        a.xaxis.label.set_color(CHART_TEXT)
        a.yaxis.label.set_color(CHART_TEXT)
        for label in a.get_xticklabels() + a.get_yticklabels():
            label.set_color(CHART_TEXT)
        for spine in a.spines.values():
            spine.set_color(CHART_GRID)
    ax1.grid(True, alpha=0.2, color=CHART_GRID)


@st.cache_data
def get_all_data():
    oil_df = load_oil_prices()
    conflicts_df = load_conflicts()
    fuel_df = load_sa_fuel_prices()
    levies_df = load_sa_levies()
    merged = merge_oil_and_fuel(oil_df, fuel_df)
    return oil_df, conflicts_df, fuel_df, levies_df, merged


def main():
    # --- Sidebar branding ---
    if LOGO_PATH.exists():
        import base64
        logo_b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode()
        st.sidebar.markdown(
            f'<a href="{ORIONTECH_URL}" target="_blank">'
            f'<img src="data:image/png;base64,{logo_b64}" style="width:100%;cursor:pointer;" />'
            f'</a>',
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown(
            f'<h2 style="text-align:center;">'
            f'<a href="{ORIONTECH_URL}" target="_blank" '
            f'style="background:linear-gradient(135deg,{OT_PRIMARY},{OT_CYAN});'
            f'-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
            f'text-decoration:none;">OrionTech</a></h2>',
            unsafe_allow_html=True,
        )
    st.sidebar.markdown(
        f'<p style="text-align:center;color:{OT_TEXT_MUTED};font-size:0.85em;">'
        'If You Can\'t Measure It, You Can\'t Manage It</p>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        f'<div style="text-align:center;margin:0.5rem 0;">'
        f'<a href="{ORIONTECH_LINKEDIN}" target="_blank" title="Follow us on LinkedIn" '
        f'style="color:{OT_CYAN};text-decoration:none;font-size:0.9em;">'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
        f'fill="{OT_CYAN}" style="vertical-align:middle;margin-right:4px;">'
        f'<path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>'
        f'</svg>'
        f' Follow on LinkedIn</a></div>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("---")

    st.title("Fuel Price Tracker")
    st.markdown(
        f'<p style="font-size:1.15em;color:{OT_TEXT_MUTED};">'
        f'How wars move oil prices — and what South Africans pay at the pump.</p>',
        unsafe_allow_html=True,
    )

    # Load all data
    oil_df, conflicts_df, fuel_df, levies_df, merged = get_all_data()

    # --- Top-level metrics ---
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)

    latest_brent = oil_df["brent_usd"].iloc[-1]
    latest_pump = fuel_df["petrol_95_inland"].iloc[-1]
    latest_zar = fuel_df["zar_usd"].iloc[-1]
    latest_levy = levies_df["total_levies"].iloc[-1]

    col1.metric("Brent Crude", f"${latest_brent:.2f}/bbl",
                help="Latest Brent crude oil price in USD per barrel")
    col2.metric("95 ULP Inland", f"R{latest_pump:.2f}/L",
                help="Latest petrol 95 price inland (Gauteng)")
    col3.metric("ZAR/USD", f"R{latest_zar:.2f}",
                help="Rand to US Dollar exchange rate")
    col4.metric("Total Levies", f"R{latest_levy:.2f}/L",
                help="Total government levies per litre of fuel")

    # Levy as percentage
    levy_pct = (latest_levy / latest_pump) * 100
    st.markdown(
        f'<div class="highlight-stat">'
        f'<span style="color:{OT_CYAN};font-size:1.1em;">'
        f'<b>R{latest_levy:.2f}</b> of every litre is government levies & taxes '
        f'(<b>{levy_pct:.1f}%</b> of the pump price)</span></div>',
        unsafe_allow_html=True,
    )

    # ============================================================
    # SECTION 1: Oil Price & Conflicts Timeline
    # ============================================================
    st.markdown("---")
    st.subheader("Brent Crude Oil & Global Conflicts")
    st.markdown(f'<p style="color:{OT_TEXT_MUTED};">Shaded regions show active conflict periods.</p>',
                unsafe_allow_html=True)

    fig, ax = plt.subplots(figsize=(14, 5))
    _style_chart(fig, ax)
    ax.plot(oil_df["date"], oil_df["brent_usd"], color=OT_CYAN, linewidth=1.8, zorder=5)
    ax.fill_between(oil_df["date"], oil_df["brent_usd"], alpha=0.08, color=OT_CYAN)

    for _, c in conflicts_df.iterrows():
        color = CONFLICT_COLORS.get(c["event_tag"], "#475569")
        ax.axvspan(c["start_date"], c["end_date"], alpha=0.2, color=color, label=c["event_name"])

    ax.set_ylabel("USD per Barrel")
    leg = ax.legend(loc="upper left", fontsize=7, ncol=2, framealpha=0.9,
                    facecolor=CHART_FACE, edgecolor=CHART_GRID, labelcolor=CHART_TEXT)
    ax.set_xlim(oil_df["date"].min(), oil_df["date"].max())
    st.pyplot(fig)
    plt.close()

    # ============================================================
    # SECTION 2: Conflict Impact Scoreboard
    # ============================================================
    st.markdown("---")
    st.subheader("Conflict Impact Scoreboard")
    st.markdown(f'<p style="color:{OT_TEXT_MUTED};">How much did each conflict spike oil prices?</p>',
                unsafe_allow_html=True)

    impact_df = conflict_impact_analysis(oil_df, conflicts_df)
    impact_sorted = impact_df.dropna(subset=["price_change_pct"]).sort_values("price_change_pct", ascending=False)

    fig, ax = plt.subplots(figsize=(12, 5))
    _style_chart(fig, ax)
    colors = [OT_RED if x > 0 else OT_EMERALD for x in impact_sorted["price_change_pct"]]
    bars = ax.barh(impact_sorted["event_name"], impact_sorted["price_change_pct"],
                   color=colors, edgecolor="none", height=0.6)

    for bar, val in zip(bars, impact_sorted["price_change_pct"]):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{val:+.1f}%", va="center", fontsize=9, color=CHART_TEXT)

    ax.set_xlabel("Oil Price Change (%)")
    ax.set_title("Peak Oil Price Change During Each Conflict", fontweight="bold")
    ax.invert_yaxis()
    ax.tick_params(axis="y", labelsize=9)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

    with st.expander("View Detailed Conflict Impact Data"):
        display_df = impact_df.copy()
        display_df["start_date"] = display_df["start_date"].dt.strftime("%b %Y")
        display_df["end_date"] = display_df["end_date"].dt.strftime("%b %Y")
        st.dataframe(
            display_df[["event_name", "region", "start_date", "end_date",
                        "pre_avg_usd", "during_peak_usd", "price_change_pct"]],
            use_container_width=True, hide_index=True,
        )

    # ============================================================
    # SECTION 3: SA Pump Price Impact
    # ============================================================
    st.markdown("---")
    st.subheader("Impact on SA Pump Prices")
    st.markdown(f'<p style="color:{OT_TEXT_MUTED};">What South Africans actually felt at the pump during each conflict.</p>',
                unsafe_allow_html=True)

    sa_impact = sa_impact_during_conflicts(merged, conflicts_df)

    col_left, col_right = st.columns(2)

    with col_left:
        sa_valid = sa_impact.dropna(subset=["pump_change_pct"]).sort_values("pump_change_pct", ascending=False)
        if not sa_valid.empty:
            fig, ax = plt.subplots(figsize=(7, 4))
            _style_chart(fig, ax)
            colors = [OT_RED if x > 0 else OT_EMERALD for x in sa_valid["pump_change_pct"]]
            ax.barh(sa_valid["event_name"], sa_valid["pump_change_pct"],
                    color=colors, edgecolor="none", height=0.6)
            ax.set_xlabel("Pump Price Change (%)")
            ax.set_title("SA Pump Price Impact by Conflict", fontweight="bold")
            ax.invert_yaxis()
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()

    with col_right:
        rand_valid = sa_impact.dropna(subset=["rand_change_pct"]).sort_values("rand_change_pct", ascending=False)
        if not rand_valid.empty:
            fig, ax = plt.subplots(figsize=(7, 4))
            _style_chart(fig, ax)
            colors = [OT_RED if x > 0 else OT_EMERALD for x in rand_valid["rand_change_pct"]]
            ax.barh(rand_valid["event_name"], rand_valid["rand_change_pct"],
                    color=colors, edgecolor="none", height=0.6)
            ax.set_xlabel("ZAR/USD Change (%)")
            ax.set_title("Rand Movement During Conflicts", fontweight="bold")
            ax.invert_yaxis()
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()

    # ============================================================
    # SECTION 4: Barrel vs Pump — The SA Markup
    # ============================================================
    st.markdown("---")
    st.subheader("Brent Crude vs SA Pump Price")
    st.markdown(f'<p style="color:{OT_TEXT_MUTED};">Dual-axis: oil price in USD (left) vs pump price in Rands (right)</p>',
                unsafe_allow_html=True)

    fig, ax1 = plt.subplots(figsize=(14, 5))
    ax2 = ax1.twinx()
    _style_dual_axis(fig, ax1, ax2)

    line1 = ax1.plot(merged["date"], merged["brent_usd"], color=OT_CYAN,
                     linewidth=1.5, label="Brent (USD/barrel)")
    line2 = ax2.plot(merged["date"], merged["petrol_95_inland"], color=OT_PRIMARY,
                     linewidth=1.5, label="95 Inland (R/litre)")

    ax1.set_ylabel("USD per Barrel", color=OT_CYAN)
    ax2.set_ylabel("Rands per Litre", color=OT_PRIMARY)
    ax1.tick_params(axis="y", labelcolor=OT_CYAN)
    ax2.tick_params(axis="y", labelcolor=OT_PRIMARY)

    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper left",
               facecolor=CHART_FACE, edgecolor=CHART_GRID, labelcolor=CHART_TEXT)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

    # ============================================================
    # SECTION 5: Exchange Rate Overlay
    # ============================================================
    st.markdown("---")
    st.subheader("The Rand Factor")
    st.markdown(f'<p style="color:{OT_TEXT_MUTED};">Oil is priced in USD. A weak Rand amplifies every oil spike.</p>',
                unsafe_allow_html=True)

    fig, ax1 = plt.subplots(figsize=(14, 5))
    ax2 = ax1.twinx()
    _style_dual_axis(fig, ax1, ax2)

    ax1.plot(fuel_df["date"], fuel_df["petrol_95_inland"], color=OT_PRIMARY,
             linewidth=1.5, label="95 Inland (R/L)")
    ax2.plot(fuel_df["date"], fuel_df["zar_usd"], color=OT_AMBER,
             linewidth=1.5, label="ZAR/USD", linestyle="--")

    ax1.set_ylabel("Pump Price (R/L)", color=OT_PRIMARY)
    ax2.set_ylabel("ZAR per USD", color=OT_AMBER)
    ax2.invert_yaxis()
    ax1.tick_params(axis="y", labelcolor=OT_PRIMARY)
    ax2.tick_params(axis="y", labelcolor=OT_AMBER)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left",
               facecolor=CHART_FACE, edgecolor=CHART_GRID, labelcolor=CHART_TEXT)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

    # ============================================================
    # SECTION 6: Coastal vs Inland
    # ============================================================
    st.markdown("---")
    st.subheader("Coastal vs Inland Pricing")

    fig, ax = plt.subplots(figsize=(14, 4))
    _style_chart(fig, ax)
    ax.plot(fuel_df["date"], fuel_df["petrol_95_coastal"], linewidth=1.5,
            color=OT_CYAN, label="95 Coastal")
    ax.plot(fuel_df["date"], fuel_df["petrol_95_inland"], linewidth=1.5,
            color=OT_PRIMARY, label="95 Inland")
    ax.fill_between(fuel_df["date"], fuel_df["petrol_95_coastal"],
                     fuel_df["petrol_95_inland"], alpha=0.12, color=OT_PRIMARY)

    latest_spread = latest_pump - fuel_df["petrol_95_coastal"].iloc[-1]
    ax.set_ylabel("R/Litre")
    ax.set_title(f"Coastal vs Inland — Current Spread: R{latest_spread:.2f}/L", fontweight="bold")
    ax.legend(facecolor=CHART_FACE, edgecolor=CHART_GRID, labelcolor=CHART_TEXT)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

    # ============================================================
    # SECTION 7: Fuel Levy Breakdown
    # ============================================================
    st.markdown("---")
    st.subheader("SA Fuel Levy Breakdown Over Time")
    st.markdown(f'<p style="color:{OT_TEXT_MUTED};">What government takes from every litre you buy.</p>',
                unsafe_allow_html=True)

    levy_info = levy_analysis(levies_df)

    lev_cols = st.columns(4)
    lev_cols[0].metric("Total Levies", f"R{levy_info['current_total_levy']:.2f}/L")
    lev_cols[1].metric("General Fuel Levy", f"R{levy_info['general_fuel_levy']:.2f}/L")
    lev_cols[2].metric("RAF Levy", f"R{levy_info['raf_levy']:.2f}/L")
    lev_cols[3].metric("Levy % of Pump", f"{levy_info['current_levy_pct']:.1f}%")

    fig, ax = plt.subplots(figsize=(14, 5))
    _style_chart(fig, ax)
    levy_cols_data = ["general_fuel_levy", "raf_levy", "customs_excise", "pipeline_levy", "slate_levy", "dsml_levy"]
    levy_labels = ["General Fuel Levy", "RAF Levy", "Customs & Excise", "Pipeline", "Slate", "DSML"]
    levy_colors = [OT_RED, OT_ORANGE, OT_AMBER, OT_EMERALD, OT_CYAN, OT_VIOLET]

    bottom = np.zeros(len(levies_df))
    for col, label, color in zip(levy_cols_data, levy_labels, levy_colors):
        vals = levies_df[col].values
        ax.bar(levies_df["effective_date"], vals, bottom=bottom,
               label=label, color=color, width=200, edgecolor="none")
        bottom += vals

    ax.set_ylabel("Rands per Litre")
    ax.set_title(f"Levies grew from R{levy_info['earliest_total_levy']:.2f} to R{levy_info['current_total_levy']:.2f} ({levy_info['levy_increase_pct']:+.0f}%)",
                 fontweight="bold")
    ax.legend(loc="upper left", fontsize=8,
              facecolor=CHART_FACE, edgecolor=CHART_GRID, labelcolor=CHART_TEXT)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

    # Levy as % of pump price over time
    fig, ax = plt.subplots(figsize=(14, 4))
    _style_chart(fig, ax)
    ax.plot(levies_df["effective_date"], levies_df["levy_pct_of_pump"],
            "o-", color=OT_VIOLET, linewidth=2, markersize=5)
    ax.fill_between(levies_df["effective_date"], levies_df["levy_pct_of_pump"],
                     alpha=0.12, color=OT_VIOLET)
    ax.set_ylabel("Levy as % of Pump Price")
    ax.set_title("Government Take as Percentage of What You Pay", fontweight="bold")
    ax.set_ylim(0, 60)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

    # ============================================================
    # SECTION 8: "What If" Scenario Calculator
    # ============================================================
    st.markdown("---")
    st.subheader("\"What If\" Scenario Calculator")
    st.markdown(f'<p style="color:{OT_TEXT_MUTED};">Drag the sliders to see how oil price and exchange rate affect your pump price.</p>',
                unsafe_allow_html=True)

    calc_cols = st.columns(3)
    with calc_cols[0]:
        brent_input = st.slider("Brent Crude (USD/barrel)", 30.0, 180.0,
                                float(latest_brent), 1.0)
    with calc_cols[1]:
        zar_input = st.slider("ZAR/USD Exchange Rate", 10.0, 25.0,
                              float(latest_zar), 0.1)
    with calc_cols[2]:
        levy_input = st.slider("Total Levies (R/L)", 4.0, 10.0,
                               float(latest_levy), 0.1)

    scenario = scenario_calculator(brent_input, zar_input, levy_input)

    sc_cols = st.columns(4)
    sc_cols[0].metric("Barrel in Rands", f"R{scenario['barrel_zar']:,.0f}")
    sc_cols[1].metric("Crude per Litre", f"R{scenario['barrel_per_litre']:.2f}")
    sc_cols[2].metric("Levies & Margins", f"R{scenario['total_levies'] + scenario['margins_delivery']:.2f}")
    sc_cols[3].metric("Estimated Pump Price", f"R{scenario['estimated_pump_price']:.2f}",
                      delta=f"R{scenario['estimated_pump_price'] - latest_pump:+.2f} vs current",
                      delta_color="inverse")

    # Pump price breakdown pie
    fig, ax = plt.subplots(figsize=(6, 4))
    fig.patch.set_facecolor(CHART_BG)
    ax.set_facecolor(CHART_FACE)
    breakdown_vals = [scenario["barrel_per_litre"], scenario["total_levies"],
                      scenario["margins_delivery"], 0.45]
    breakdown_labels = [
        f"Crude Oil\nR{scenario['barrel_per_litre']:.2f}",
        f"Govt Levies\nR{scenario['total_levies']:.2f}",
        f"Margins\nR{scenario['margins_delivery']:.2f}",
        f"Shipping\nR0.45",
    ]
    breakdown_colors = [OT_CYAN, OT_RED, OT_PRIMARY, OT_EMERALD]
    wedges, texts, autotexts = ax.pie(
        breakdown_vals, labels=breakdown_labels, colors=breakdown_colors,
        autopct="%1.0f%%", startangle=90,
        textprops={"fontsize": 9, "color": CHART_TEXT},
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontweight("bold")
    ax.set_title(f"What Makes Up R{scenario['estimated_pump_price']:.2f}/L",
                 fontweight="bold", color=OT_TEXT)
    st.pyplot(fig)
    plt.close()

    # ============================================================
    # SECTION 9: Future Projection
    # ============================================================
    st.markdown("---")
    st.subheader("12-Month Price Projection")
    st.markdown(f'<p style="color:{OT_TEXT_MUTED};">Based on current trends, exchange rate, and oil price trajectory.</p>',
                unsafe_allow_html=True)

    np.random.seed(42)
    projections = project_fuel_price(merged, months_ahead=12,
                                      brent_scenario=brent_input,
                                      zar_scenario=zar_input)

    fig, ax = plt.subplots(figsize=(14, 5))
    _style_chart(fig, ax)

    recent = merged.tail(24)
    ax.plot(recent["date"], recent["petrol_95_inland"], "o-", color=OT_PRIMARY,
            linewidth=1.5, markersize=4, label="Actual")
    ax.plot(projections["date"], projections["projected_pump_price"], "o--",
            color=OT_CYAN, linewidth=1.5, markersize=4, label="Projected")

    proj_values = projections["projected_pump_price"]
    ax.fill_between(projections["date"],
                     proj_values * 0.92, proj_values * 1.08,
                     alpha=0.12, color=OT_CYAN, label="Uncertainty Range")

    ax.axvline(x=merged["date"].iloc[-1], color=OT_TEXT_MUTED, linestyle=":", alpha=0.5)
    ax.set_ylabel("R/Litre")
    ax.set_title("Projected 95 ULP Inland Price", fontweight="bold")
    ax.legend(facecolor=CHART_FACE, edgecolor=CHART_GRID, labelcolor=CHART_TEXT)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

    proj_avg = projections["projected_pump_price"].mean()
    proj_max = projections["projected_pump_price"].max()
    proj_min = projections["projected_pump_price"].min()

    proj_cols = st.columns(3)
    proj_cols[0].metric("Projected Average", f"R{proj_avg:.2f}/L")
    proj_cols[1].metric("Projected High", f"R{proj_max:.2f}/L")
    proj_cols[2].metric("Projected Low", f"R{proj_min:.2f}/L")

    # ============================================================
    # SECTION 10: Key Insights
    # ============================================================
    st.markdown("---")
    st.subheader("Key Insights")

    fuel_1990 = fuel_df["petrol_95_inland"].iloc[0]
    fuel_now = fuel_df["petrol_95_inland"].iloc[-1]
    fuel_increase = ((fuel_now / fuel_1990) - 1) * 100

    oil_1990 = oil_df["brent_usd"].iloc[0]
    oil_now = oil_df["brent_usd"].iloc[-1]
    oil_increase = ((oil_now / oil_1990) - 1) * 100

    zar_1990 = fuel_df["zar_usd"].iloc[0]
    zar_now = fuel_df["zar_usd"].iloc[-1]
    zar_decline = ((zar_now / zar_1990) - 1) * 100

    levy_1990 = levies_df["total_levies"].iloc[0]
    levy_now = levies_df["total_levies"].iloc[-1]
    levy_increase = ((levy_now / levy_1990) - 1) * 100

    insight_cols = st.columns(2)

    with insight_cols[0]:
        st.markdown(f"""
        **Price Journey Since 1990:**
        - Petrol: R{fuel_1990:.2f} → R{fuel_now:.2f} (**{fuel_increase:+,.0f}%**)
        - Brent: ${oil_1990:.2f} → ${oil_now:.2f} (**{oil_increase:+,.0f}%**)
        - Rand: R{zar_1990:.2f}/$ → R{zar_now:.2f}/$ (**{zar_decline:+,.0f}%** weaker)
        - Levies: R{levy_1990:.2f} → R{levy_now:.2f} (**{levy_increase:+,.0f}%**)
        """)

    with insight_cols[1]:
        st.markdown(f"""
        **The Ugly Truth:**
        - Oil went up **{oil_increase:.0f}%** but fuel went up **{fuel_increase:.0f}%**
        - The difference? Rand weakness and levy increases
        - Government levies alone are now **R{levy_now:.2f}/L**
        - That's **R{levy_now * 50:.0f}** in tax on a 50L fill-up
        - The RAF levy funds road accident claims — **R{levy_info['raf_levy']:.2f}/L**
        """)

    # --- Raw data ---
    st.markdown("---")
    with st.expander("View Raw Oil Price Data"):
        st.dataframe(oil_df, use_container_width=True, hide_index=True)
    with st.expander("View Raw SA Fuel Price Data"):
        st.dataframe(fuel_df, use_container_width=True, hide_index=True)
    with st.expander("View Levy History"):
        st.dataframe(levies_df, use_container_width=True, hide_index=True)

    # --- Sidebar stats ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Current Prices")
    st.sidebar.markdown(f"**Brent Crude:** ${latest_brent:.2f}/bbl")
    st.sidebar.markdown(f"**95 Inland:** R{latest_pump:.2f}/L")
    st.sidebar.markdown(f"**ZAR/USD:** R{latest_zar:.2f}")
    st.sidebar.markdown(f"**Levies:** R{latest_levy:.2f}/L ({levy_pct:.0f}%)")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Conflicts Tracked")
    st.sidebar.markdown(f"**Total events:** {len(conflicts_df)}")
    active = conflicts_df[conflicts_df["end_date"] >= pd.Timestamp.now()]
    if not active.empty:
        st.sidebar.markdown("**Active:**")
        for _, c in active.iterrows():
            st.sidebar.markdown(f"- {c['event_name']}")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Data Sources")
    st.sidebar.markdown(
        "- Brent crude historical prices\n"
        "- SA DMRE fuel price data\n"
        "- SARB exchange rates\n"
        "- Conflict timelines"
    )

    # ============================================================
    # POWERED BY ORIONTECH — Footer Banner
    # ============================================================
    st.markdown("---")

    # Logo in footer
    if LOGO_PATH.exists():
        import base64
        logo_b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode()
        st.markdown(
            f'<div style="text-align:center;">'
            f'<a href="{ORIONTECH_URL}" target="_blank">'
            f'<img src="data:image/png;base64,{logo_b64}" style="width:180px;cursor:pointer;" />'
            f'</a></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div class="oriontech-banner">'
        f'<div class="powered">Powered by</div>'
        f'<a href="{ORIONTECH_URL}" target="_blank">OrionTech</a>'
        f'<div class="tagline">If You Can\'t Measure It, You Can\'t Manage It</div>'
        f'<div style="margin-top:0.8rem;display:flex;justify-content:center;gap:1.5rem;align-items:center;">'
        f'<a href="{ORIONTECH_URL}" target="_blank" '
        f'style="color:rgba(255,255,255,0.8);text-decoration:none;font-size:0.85em;">'
        f'oriontech.co.za</a>'
        f'<span style="color:rgba(255,255,255,0.3);">|</span>'
        f'<a href="{ORIONTECH_LINKEDIN}" target="_blank" '
        f'style="color:rgba(255,255,255,0.8);text-decoration:none;font-size:0.85em;display:inline-flex;align-items:center;gap:4px;">'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" '
        f'fill="rgba(255,255,255,0.8)">'
        f'<path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>'
        f'</svg>'
        f' LinkedIn</a>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
