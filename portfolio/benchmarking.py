"""
benchmarking.py

Tracks your portfolio performance vs S&P 500 (SPY).
Saves daily snapshots to DynamoDB and calculates alpha.

Alpha = your return minus S&P 500 return
Positive alpha = you are beating the market
Negative alpha = market is beating you
"""

import boto3
import logging
from datetime import datetime, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)

BENCHMARK_TICKER = "SPY"
TABLE_NAME       = "robinhood-ai-portfolio"


def save_benchmark_snapshot(portfolio_value: float, spy_price: float):
    """
    Save today's portfolio value and SPY price to DynamoDB.
    Called every morning after reading portfolio.
    """
    try:
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table    = dynamodb.Table(TABLE_NAME)
        today    = datetime.now().strftime("%Y-%m-%d")

        table.put_item(Item={
            "date":            today,
            "ticker":          "__benchmark__",
            "score":           Decimal(str(round(spy_price, 2))),
            "category":        "BENCHMARK",
            "total_value":     Decimal(str(round(portfolio_value, 2))),
        })
        logger.info(f"Saved benchmark: portfolio=${portfolio_value:,.0f}, SPY=${spy_price}")
    except Exception as e:
        logger.warning(f"Could not save benchmark: {e}")


def get_benchmark_snapshot(date: str) -> dict:
    """Get portfolio value and SPY price for a specific date."""
    try:
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table    = dynamodb.Table(TABLE_NAME)
        response = table.get_item(Key={"date": date, "ticker": "__benchmark__"})

        if "Item" not in response:
            return None

        item = response["Item"]
        return {
            "date":            date,
            "portfolio_value": float(item["total_value"]),
            "spy_price":       float(item["score"]),
        }
    except Exception as e:
        logger.warning(f"Could not get benchmark for {date}: {e}")
        return None


def calculate_performance(days: int = 30) -> dict:
    """
    Calculate portfolio performance vs SPY over the last N days.
    Returns your return, SPY return, and alpha.
    """
    from data.yfinance_client  import yf_client
    from data.robinhood_client import robinhood_client

    today      = datetime.now()
    start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    today_str  = today.strftime("%Y-%m-%d")

    # Get today's data
    current_value = robinhood_client.get_total_value()
    current_spy   = yf_client.get_current_price(BENCHMARK_TICKER)

    # Get historical data from DynamoDB
    historical    = get_benchmark_snapshot(start_date)

    if not historical:
        return {
            "available":       False,
            "message":         f"No historical data yet. Check back in {days} days.",
            "current_value":   current_value,
            "current_spy":     current_spy,
        }

    # Calculate returns
    portfolio_return = ((current_value - historical["portfolio_value"]) /
                        historical["portfolio_value"]) * 100

    spy_return = ((current_spy - historical["spy_price"]) /
                  historical["spy_price"]) * 100

    alpha = portfolio_return - spy_return

    return {
        "available":          True,
        "period_days":        days,
        "start_date":         start_date,
        "portfolio_start":    historical["portfolio_value"],
        "portfolio_current":  current_value,
        "portfolio_return":   round(portfolio_return, 2),
        "spy_start":          historical["spy_price"],
        "spy_current":        current_spy,
        "spy_return":         round(spy_return, 2),
        "alpha":              round(alpha, 2),
        "beating_market":     alpha > 0,
    }


def format_performance(perf: dict) -> str:
    """Format performance as readable text for Telegram."""
    if not perf.get("available"):
        return (
            f"📊 Benchmarking\n\n"
            f"Portfolio: ${perf['current_value']:,.0f}\n"
            f"SPY: ${perf['current_spy']}\n\n"
            f"{perf['message']}"
        )

    arrow_portfolio = "▲" if perf["portfolio_return"] >= 0 else "▼"
    arrow_spy       = "▲" if perf["spy_return"] >= 0 else "▼"
    arrow_alpha     = "▲" if perf["alpha"] >= 0 else "▼"
    beating         = "✅ Beating market" if perf["beating_market"] else "❌ Underperforming"

    return (
        f"📊 Performance vs S&P 500 ({perf['period_days']} days)\n\n"
        f"Your portfolio:  {arrow_portfolio} {perf['portfolio_return']:+.1f}%\n"
        f"  ${perf['portfolio_start']:,.0f} → ${perf['portfolio_current']:,.0f}\n\n"
        f"S&P 500 (SPY):   {arrow_spy} {perf['spy_return']:+.1f}%\n"
        f"  ${perf['spy_start']:.2f} → ${perf['spy_current']:.2f}\n\n"
        f"Alpha:           {arrow_alpha} {perf['alpha']:+.1f}%\n"
        f"{beating}"
    )
