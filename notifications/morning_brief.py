import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from datetime import datetime
import config
from scoring.engine        import score_portfolio
from data.robinhood_client import robinhood_client


def send_telegram(text: str):
    """Send a message to your Telegram."""
    url  = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id":    config.TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    }
    try:
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        print(f"Telegram send failed: {e}")


def build_brief() -> str:
    """
    Build the 7am morning brief.
    Reads your portfolio, scores it, and returns a formatted message.
    """
    today = datetime.now().strftime("%B %d %Y")

    # Read portfolio
    holdings = robinhood_client.get_holdings()
    total    = robinhood_client.get_total_value()
    tickers  = [h["ticker"] for h in holdings]

    # Score all holdings
    results = score_portfolio(tickers)

    # Categorise
    hold   = [r for r in results if r["category"] == "HOLD"]
    watch  = [r for r in results if r["category"] == "WATCH"]
    rotate = [r for r in results if r["category"] == "ROTATE"]

    avg_score = sum(r["final_score"] for r in results) / len(results)

    # Top 3 performers
    top3 = sorted(results, key=lambda x: x["final_score"], reverse=True)[:3]

    # Earnings warnings
    earnings_soon = [r for r in results if r.get("earnings_warning")]

    # Build message
    lines = []
    lines.append(f"🌅 <b>Good morning — {today}</b>")
    lines.append("")
    lines.append(f"💰 Portfolio value: <b>${total:,.0f}</b>")
    lines.append(f"📊 Portfolio score: <b>{avg_score:.1f}/10</b>")
    lines.append("")
    lines.append(f"✅ HOLD:   {len(hold)}")
    lines.append(f"👀 WATCH:  {len(watch)}")
    lines.append(f"🔄 ROTATE: {len(rotate)}")

    # Rotation candidates
    if rotate:
        lines.append("")
        lines.append("⚡ <b>Action needed:</b>")
        for r in rotate:
            lines.append(f"  → {r['ticker']} {r['final_score']}/10 — consider rotating")
        lines.append("  Type /rotate for suggestions")

    # Earnings warnings
    if earnings_soon:
        lines.append("")
        lines.append("⚠️ <b>Earnings this week:</b>")
        for r in earnings_soon:
            lines.append(f"  → {r['ticker']} — {r['earnings_warning']}")

    # Top performers
    lines.append("")
    lines.append("🏆 <b>Top performers:</b>")
    for r in top3:
        lines.append(f"  → {r['ticker']} {r['final_score']}/10")

    lines.append("")
    lines.append("Type /portfolio for full breakdown")
    lines.append("Type /score TICKER to dig into any stock")

    return "\n".join(lines)


def send_morning_brief():
    """Build and send the morning brief to Telegram."""
    print("Building morning brief...")
    try:
        brief = build_brief()
        send_telegram(brief)
        print("Morning brief sent.")
    except Exception as e:
        print(f"Morning brief failed: {e}")
        send_telegram(f"⚠️ Morning brief failed: {e}")


if __name__ == "__main__":
    send_morning_brief()
