"""
dynamo_store.py

Handles all DynamoDB operations:
1. Portfolio history — daily scores for all stocks
2. Cost basis — your avg cost per stock (replaces cost_basis.json)
"""

import boto3
import json
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# Table names
PORTFOLIO_TABLE  = "robinhood-ai-portfolio"
COST_BASIS_TABLE = "robinhood-ai-costbasis"

# DynamoDB client
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")


# ── Portfolio History ─────────────────────────────────────────────

def save_portfolio_snapshot(results: list, total_value: float):
    """
    Save today's portfolio scores to DynamoDB.
    Called every morning after scoring.
    """
    table = dynamodb.Table(PORTFOLIO_TABLE)
    today = datetime.now().strftime("%Y-%m-%d")

    for r in results:
        try:
            table.put_item(Item={
                "date":              today,
                "ticker":            r["ticker"],
                "score":             Decimal(str(r["final_score"])),
                "category":          r["category"],
                "fundamental_score": Decimal(str(r["fundamental_score"])),
                "momentum_score":    Decimal(str(r["momentum_score"])),
                "sentiment_score":   Decimal(str(r["sentiment_score"])),
                "price":             Decimal(str(r.get("current_price", 0) or 0)),
                "total_value":       Decimal(str(total_value)),
            })
        except Exception as e:
            logger.warning(f"Could not save {r['ticker']} to DynamoDB: {e}")

    logger.info(f"Saved {len(results)} scores to DynamoDB for {today}")


def get_portfolio_snapshot(date: str) -> list:
    """
    Get portfolio scores for a specific date.
    date format: "2026-05-24"
    """
    table = dynamodb.Table(PORTFOLIO_TABLE)
    try:
        response = table.query(
            KeyConditionExpression="#d = :d",
            ExpressionAttributeNames={"#d": "date"},
            ExpressionAttributeValues={":d": date}
        )
        return response.get("Items", [])
    except Exception as e:
        logger.warning(f"Could not read portfolio snapshot for {date}: {e}")
        return []


def get_score_trend(ticker: str, days: int = 7) -> dict:
    """
    Get score trend for a ticker over the last N days.
    Returns current score, previous score, and direction.
    """
    from datetime import timedelta
    today     = datetime.now()
    prev_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    table = dynamodb.Table(PORTFOLIO_TABLE)

    try:
        # Get today's score
        today_resp = table.get_item(Key={"date": today_str, "ticker": ticker})
        prev_resp  = table.get_item(Key={"date": prev_date,  "ticker": ticker})

        today_score = float(today_resp["Item"]["score"]) if "Item" in today_resp else None
        prev_score  = float(prev_resp["Item"]["score"])  if "Item" in prev_resp  else None

        if today_score and prev_score:
            diff = round(today_score - prev_score, 2)
            if diff > 0:
                trend = f"▲ +{diff} from {days}d ago"
            elif diff < 0:
                trend = f"▼ {diff} from {days}d ago"
            else:
                trend = "→ unchanged"
        else:
            trend = "no history yet"

        return {
            "ticker":      ticker,
            "today":       today_score,
            "previous":    prev_score,
            "trend":       trend,
        }
    except Exception as e:
        logger.warning(f"Could not get trend for {ticker}: {e}")
        return {"ticker": ticker, "today": None, "previous": None, "trend": "unavailable"}


def get_portfolio_trend(days: int = 7) -> dict:
    """
    Get overall portfolio score trend over last N days.
    Returns current avg score, previous avg score, direction.
    """
    from datetime import timedelta
    today     = datetime.now()
    prev_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    today_items = get_portfolio_snapshot(today_str)
    prev_items  = get_portfolio_snapshot(prev_date)

    if not today_items or not prev_items:
        return {"trend": "", "today_avg": None, "prev_avg": None}

    today_avg = sum(float(i["score"]) for i in today_items) / len(today_items)
    prev_avg  = sum(float(i["score"]) for i in prev_items)  / len(prev_items)

    diff = round(today_avg - prev_avg, 2)
    if diff > 0:
        trend = f"▲ +{diff} from last week"
    elif diff < 0:
        trend = f"▼ {diff} from last week"
    else:
        trend = "→ unchanged from last week"

    return {
        "trend":     trend,
        "today_avg": round(today_avg, 2),
        "prev_avg":  round(prev_avg, 2),
    }


# ── Cost Basis ────────────────────────────────────────────────────

def save_cost_basis(ticker: str, avg_cost: float):
    """Save avg cost for a ticker to DynamoDB."""
    table = dynamodb.Table(COST_BASIS_TABLE)
    try:
        table.put_item(Item={
            "ticker":   ticker.upper(),
            "avg_cost": Decimal(str(round(avg_cost, 2))),
            "updated":  datetime.now().strftime("%Y-%m-%d"),
        })
        logger.info(f"Saved cost basis: {ticker} = ${avg_cost}")
    except Exception as e:
        logger.error(f"Could not save cost basis for {ticker}: {e}")


def get_cost_basis(ticker: str) -> float | None:
    """Get saved avg cost for a ticker. Returns None if not saved."""
    table = dynamodb.Table(COST_BASIS_TABLE)
    try:
        response = table.get_item(Key={"ticker": ticker.upper()})
        if "Item" in response:
            return float(response["Item"]["avg_cost"])
        return None
    except Exception as e:
        logger.warning(f"Could not get cost basis for {ticker}: {e}")
        return None


def migrate_local_cost_basis(json_file: str = "cost_basis.json"):
    """
    One-time migration: copy local cost_basis.json to DynamoDB.
    Run this once after deployment.
    """
    import os
    if not os.path.exists(json_file):
        print("No local cost_basis.json found — nothing to migrate.")
        return

    with open(json_file, "r") as f:
        data = json.load(f)

    for ticker, avg_cost in data.items():
        save_cost_basis(ticker, avg_cost)
        print(f"Migrated: {ticker} = ${avg_cost}")

    print(f"Migration complete — {len(data)} stocks moved to DynamoDB.")
