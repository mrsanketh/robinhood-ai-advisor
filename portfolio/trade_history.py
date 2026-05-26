"""
trade_history.py

Tracks trades you execute based on app recommendations.
Stored in DynamoDB — never in local files.

You tell the app when you make a trade:
  "I sold 23 shares of SHOP at $103"
  "I bought 2 shares of CAT at $879"

App records it and uses it for performance tracking.
"""

import boto3
import logging
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

TABLE_NAME = "robinhood-ai-costbasis"  # reuse existing table with different keys


def record_trade(
    action: str,       # "BUY" or "SELL"
    ticker: str,
    shares: float,
    price: float,
    reason: str = "",  # e.g. "rotation: SHOP → CAT"
):
    """
    Record a trade in DynamoDB.
    Call this after you execute a trade in Robinhood.
    Deduplicates — ignores same trade within 5 minutes.
    """
    try:
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table    = dynamodb.Table("robinhood-ai-portfolio")

        # Dedup check — same action+ticker+price within last 5 minutes
        from datetime import timedelta
        five_min_ago = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d")
        today_str    = datetime.now().strftime("%Y-%m-%d")

        existing = table.scan(
            FilterExpression="#d = :d AND contains(ticker, :key)",
            ExpressionAttributeNames={"#d": "date"},
            ExpressionAttributeValues={
                ":d":   today_str,
                ":key": f"__trade_{action}_{ticker}__"
            }
        )
        if existing.get("Items"):
            logger.info(f"Duplicate trade ignored: {action} {ticker}")
            return True  # return True so user still sees success message

        today    = datetime.now().strftime("%Y-%m-%d %H:%M")
        key      = f"__trade_{action}_{ticker}_{today}__"

        table.put_item(Item={
            "date":     datetime.now().strftime("%Y-%m-%d"),
            "ticker":   key,
            "score":    Decimal(str(round(price, 2))),
            "category": f"TRADE_{action}",
            "total_value": Decimal(str(round(shares * price, 2))),
            "reason":   reason,
        })

        logger.info(f"Recorded trade: {action} {shares} {ticker} @ ${price}")
        return True

    except Exception as e:
        logger.error(f"Could not record trade: {e}")
        return False


def get_recent_trades(days: int = 30) -> list:
    """Get trades from the last N days."""
    try:
        from datetime import timedelta
        dynamodb  = boto3.resource("dynamodb", region_name="us-east-1")
        table     = dynamodb.Table("robinhood-ai-portfolio")

        today     = datetime.now()
        start     = (today - timedelta(days=days)).strftime("%Y-%m-%d")

        response  = table.scan(
            FilterExpression="contains(ticker, :prefix) AND #dt >= :start",
            ExpressionAttributeNames={"#dt": "date"},
            ExpressionAttributeValues={
                ":prefix": "__trade_",
                ":start":  start,
            }
        )

        trades = []
        for item in response.get("Items", []):
            key    = item["ticker"]
            parts  = key.split("_")
            if len(parts) >= 4:
                trades.append({
                    "date":     item["date"],
                    "action":   parts[2],
                    "ticker":   parts[3],
                    "price":    float(item["score"]),
                    "value":    float(item["total_value"]),
                    "reason":   item.get("reason", ""),
                })

        trades.sort(key=lambda x: x["date"], reverse=True)
        return trades

    except Exception as e:
        logger.warning(f"Could not get trade history: {e}")
        return []


def format_trade_history(trades: list) -> str:
    """Format trade history for Telegram."""
    if not trades:
        return "No trades recorded yet.\n\nAfter executing a trade tell me:\n\"I sold 23 shares of SHOP at $103\""

    result = f"📋 Recent trades ({len(trades)}):\n\n"
    for t in trades[:10]:
        arrow = "🔴 SELL" if t["action"] == "SELL" else "🟢 BUY"
        result += f"{arrow} {t['ticker']} — ${t['value']:,.0f}\n"
        result += f"  {t['date']} at ${t['price']}\n"
        if t["reason"]:
            result += f"  Reason: {t['reason']}\n"
        result += "\n"
    return result
