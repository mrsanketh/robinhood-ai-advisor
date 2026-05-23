import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scoring.engine           import score_portfolio
from data.robinhood_client    import robinhood_client
from portfolio.rotation_engine import run_rotation_analysis, format_suggestion

# ── Page config ───────────────────────────────────────
st.set_page_config(
    page_title="Robinhood AI Advisor",
    page_icon="🤖",
    layout="wide"
)

# ── Header ────────────────────────────────────────────
st.title("🤖 Robinhood AI Advisor")
st.caption("AI-powered portfolio scoring and rotation suggestions")

# ── Load data ─────────────────────────────────────────
@st.cache_data(ttl=3600)   # cache for 1 hour — avoids re-scoring on every page refresh
def load_portfolio():
    holdings        = robinhood_client.get_holdings()
    total_value     = robinhood_client.get_total_value()
    tickers         = [h["ticker"] for h in holdings]
    results         = score_portfolio(tickers)
    holdings_map    = {h["ticker"]: h for h in holdings}

    rows = []
    for r in results:
        holding = holdings_map.get(r["ticker"], {})
        rows.append({
            "Ticker":      r["ticker"],
            "Company":     r["company_name"],
            "Score":       r["final_score"],
            "Category":    r["category"],
            "F":           r["fundamental_score"],
            "M":           r["momentum_score"],
            "S":           r["sentiment_score"],
            "Sector":      r["sector"],
            "Price":       r.get("current_price"),
            "Shares":      holding.get("shares", 0),
            "Equity":      holding.get("equity", 0),
            "Earnings":    r.get("earnings_warning", ""),
        })

    return pd.DataFrame(rows), total_value


# ── Sidebar ───────────────────────────────────────────
with st.sidebar:
    st.header("Controls")
    if st.button("🔄 Refresh Data", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.caption("Data refreshes automatically every hour.")
    st.divider()
    st.header("Filters")
    show_category = st.multiselect(
        "Show categories",
        ["HOLD", "WATCH", "ROTATE"],
        default=["HOLD", "WATCH", "ROTATE"]
    )

# ── Load with spinner ─────────────────────────────────
with st.spinner("Loading portfolio... this takes ~2 minutes on first load"):
    df, total_value = load_portfolio()

# ── Portfolio summary ─────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Value", f"${total_value:,.0f}")
with col2:
    avg_score = df["Score"].mean()
    st.metric("Portfolio Score", f"{avg_score:.1f}/10")
with col3:
    rotate_count = len(df[df["Category"] == "ROTATE"])
    st.metric("Rotate Candidates", rotate_count, delta=f"-{rotate_count} needed" if rotate_count > 0 else "None")
with col4:
    earnings_count = len(df[df["Earnings"] != ""])
    st.metric("Earnings This Week", earnings_count)

st.divider()

# ── Score chart ───────────────────────────────────────
st.subheader("Portfolio Scores")

filtered_df = df[df["Category"].isin(show_category)].copy()

color_map = {"HOLD": "#22c55e", "WATCH": "#f59e0b", "ROTATE": "#ef4444"}

fig = px.bar(
    filtered_df.sort_values("Score", ascending=True),
    x="Score",
    y="Ticker",
    color="Category",
    color_discrete_map=color_map,
    orientation="h",
    height=max(400, len(filtered_df) * 22),
    hover_data=["Company", "F", "M", "S", "Equity"],
)
fig.update_layout(
    xaxis_range=[0, 10],
    xaxis_title="Score (0-10)",
    yaxis_title="",
    showlegend=True,
    margin=dict(l=0, r=20, t=20, b=20),
)
fig.add_vline(x=7.0, line_dash="dash", line_color="gray", annotation_text="HOLD threshold")
fig.add_vline(x=5.0, line_dash="dash", line_color="red",  annotation_text="ROTATE threshold")
st.plotly_chart(fig, width="stretch")

st.divider()

# ── Detailed table ────────────────────────────────────
st.subheader("All Positions")

display_df = filtered_df[[
    "Ticker", "Company", "Score", "Category", "F", "M", "S", "Equity", "Earnings"
]].copy()

display_df["Equity"] = display_df["Equity"].apply(lambda x: f"${x:,.0f}")
display_df["Score"]  = display_df["Score"].apply(lambda x: f"{x:.2f}")

def color_category(val):
    if val == "ROTATE": return "background-color: #fef2f2; color: #dc2626"
    if val == "WATCH":  return "background-color: #fffbeb; color: #d97706"
    if val == "HOLD":   return "background-color: #f0fdf4; color: #16a34a"
    return ""

styled = display_df.style.map(color_category, subset=["Category"])
st.dataframe(styled, width="stretch", hide_index=True)

st.divider()

# ── Rotation suggestions ──────────────────────────────
st.subheader("🔄 Rotation Suggestions")

if rotate_count == 0:
    st.success("No rotation needed. Your portfolio looks healthy.")
else:
    if st.button("Generate Rotation Suggestions", type="primary"):
        with st.spinner("Analysing rotation opportunities... ~3 minutes"):
            suggestions = run_rotation_analysis()
            for s in suggestions:
                with st.expander(
                    f"{'Combined: ' if s.get('combined') else ''}{s['sell']['ticker']} → {s['buy']['ticker'] if s.get('buy') else 'Hold Cash'}",
                    expanded=True
                ):
                    st.text(format_suggestion(s))

# ── Earnings warnings ─────────────────────────────────
if earnings_count > 0:
    st.divider()
    st.subheader("⚠️ Earnings This Week")
    earnings_df = df[df["Earnings"] != ""][["Ticker", "Company", "Score", "Category", "Earnings"]]
    st.dataframe(earnings_df, width="stretch", hide_index=True)

# ── Footer ────────────────────────────────────────────
st.divider()
st.caption("Not financial advice. Always verify before trading. Check Robinhood Tax Center for cost basis.")
