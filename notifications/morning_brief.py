import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import logging
from datetime import datetime, timedelta
import config
from scoring.engine            import score_portfolio
from data.robinhood_client     import robinhood_client
from portfolio.rotation_engine import get_rotation_candidates

logger = logging.getLogger(__name__)


def send_telegram(text: str):
    url  = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        print(f"Telegram send failed: {e}")


def build_brief() -> str:
    today = datetime.now().strftime("%B %d %Y")

    # Try DynamoDB cache first (saved at 11pm) — avoids Robinhood auth at 7am
    holdings = None
    total    = 0
    try:
        from infra.dynamo_store import get_holdings_snapshot
        from datetime import timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        holdings, total = get_holdings_snapshot(yesterday)
        if holdings:
            logger.info(f"Using cached holdings from DynamoDB ({len(holdings)} positions)")
    except Exception as e:
        logger.warning(f"Could not read cached holdings: {e}")

    # Fall back to live Robinhood if no cache
    if not holdings:
        logger.info("No cached holdings — reading live from Robinhood")
        holdings = robinhood_client.get_holdings()
        total    = robinhood_client.get_total_value()

    tickers  = [h["ticker"] for h in holdings]
    results  = score_portfolio(tickers)

    hold   = [r for r in results if r["category"] == "HOLD"]
    watch  = [r for r in results if r["category"] == "WATCH"]
    rotate = [r for r in results if r["category"] == "ROTATE"]

    avg_score     = sum(r["final_score"] for r in results) / len(results) if results else 0
    top3          = sorted(results, key=lambda x: x["final_score"], reverse=True)[:3]
    earnings_soon = [r for r in results if r.get("earnings_warning")]

    # Save snapshot and get trends
    score_trend  = ""
    value_change = ""
    try:
        from portfolio.benchmarking import save_benchmark_snapshot, get_benchmark_snapshot
        from infra.dynamo_store     import save_portfolio_snapshot, get_portfolio_trend
        from data.yfinance_client   import yf_client

        spy_price = yf_client.get_current_price("SPY")
        save_benchmark_snapshot(total, spy_price)
        save_portfolio_snapshot(results, total)

        # 7-day score trend
        trend = get_portfolio_trend(days=7)
        if trend.get("trend") and trend.get("today_avg") and trend.get("prev_avg"):
            diff = round(trend["today_avg"] - trend["prev_avg"], 1)
            if diff > 0:
                score_trend = f"  ▲ +{diff} from last week"
            elif diff < 0:
                score_trend = f"  ▼ {diff} from last week"

        # Yesterday's value change
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        prev      = get_benchmark_snapshot(yesterday)
        if prev:
            change     = total - prev["portfolio_value"]
            arrow      = "▲" if change >= 0 else "▼"
            value_change = f"  {arrow} {'+' if change >= 0 else ''}{change:,.0f} from yesterday"

    except Exception as e:
        logger.warning(f"Could not get trend data: {e}")

    sized_candidates = get_rotation_candidates(holdings, results, total)

    lines = []
    lines.append(f"🌅 <b>Good morning — {today}</b>")
    lines.append("")
    lines.append(f"💰 Portfolio value: <b>${total:,.0f}</b>")
    if value_change:
        lines.append(value_change)
    lines.append(f"📊 Portfolio score: <b>{avg_score:.1f}/10</b>")
    if score_trend:
        lines.append(score_trend)
    lines.append("")
    lines.append(f"✅ HOLD:   {len(hold)}")
    lines.append(f"👀 WATCH:  {len(watch)}")
    lines.append(f"🔄 ROTATE: {len(rotate)}")

    if sized_candidates:
        lines.append("")
        lines.append("⚡ <b>Action needed:</b>")
        for c in sized_candidates:
            lines.append(f"  → {c['ticker']} {c['score']}/10 — {c['action']}")
        lines.append("")
        lines.append("  👉 Ask me: \"Should I sell TICKER?\"")
    elif rotate:
        lines.append("")
        lines.append("⚡ <b>Flagged for review:</b>")
        for r in rotate:
            lines.append(f"  → {r['ticker']} {r['final_score']}/10")
        lines.append("")
        lines.append("  👉 Ask me: \"Should I sell TICKER?\"")

    if earnings_soon:
        lines.append("")
        lines.append("⚠️ <b>Earnings this week:</b>")
        for r in earnings_soon:
            lines.append(f"  → {r['ticker']} — {r['earnings_warning']}")
        lines.append("  Hold these positions until after earnings")

    lines.append("")
    lines.append("🏆 <b>Top performers:</b>")
    for r in top3:
        lines.append(f"  → {r['ticker']} {r['final_score']}/10")

    # Weekly cost summary — Mondays only
    try:
        from monitoring.cost_monitor import build_cost_section, is_monday
        if is_monday():
            lines.append(build_cost_section())
    except Exception as e:
        logger.warning(f"Cost monitor failed: {e}")

    lines.append("")
    lines.append("─────────────────────")
    lines.append("Just ask me anything in natural language")
    lines.append("\"Should I sell SHOP?\"  \"Find me a healthcare stock\"")

    return "\n".join(lines)


def check_and_send_cost_alerts():
    """Check cost thresholds daily. Send alert if exceeded."""
    try:
        from monitoring.cost_monitor import check_thresholds
        alerts = check_thresholds()
        for alert in alerts:
            msg  = f"{alert['message']}\n\n"
            msg += alert['next_steps']
            send_telegram(msg)
            logger.info(f"Sent cost alert: {alert['type']}")
    except Exception as e:
        logger.warning(f"Cost threshold check failed: {e}")


def send_morning_brief():
    """Build and send the morning brief to Telegram."""
    print("Building morning brief...")
    try:
        check_and_send_cost_alerts()
        brief = build_brief()
        send_telegram(brief)
        print("Morning brief sent.")
        print()
        print(brief)
    except Exception as e:
        print(f"Morning brief failed: {e}")
        send_telegram(f"⚠️ Morning brief failed: {e}")


if __name__ == "__main__":
    send_morning_brief()
