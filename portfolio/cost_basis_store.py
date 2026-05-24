"""
cost_basis_store.py

Stores your real average cost per stock.
Uses DynamoDB in production, falls back to local JSON for development.
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

# Local fallback file for development
LOCAL_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "cost_basis.json"
)


def _use_dynamo() -> bool:
    """Use DynamoDB if AWS is configured, otherwise use local JSON."""
    try:
        import boto3
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:
        return False


def get(ticker: str) -> float | None:
    """Get saved avg cost for a ticker."""
    if _use_dynamo():
        try:
            from infra.dynamo_store import get_cost_basis
            return get_cost_basis(ticker)
        except Exception as e:
            logger.warning(f"DynamoDB read failed, falling back to local: {e}")

    # Local fallback
    if not os.path.exists(LOCAL_FILE):
        return None
    try:
        with open(LOCAL_FILE, "r") as f:
            data = json.load(f)
        return data.get(ticker.upper())
    except Exception:
        return None


def save(ticker: str, avg_cost: float):
    """Save avg cost for a ticker."""
    if _use_dynamo():
        try:
            from infra.dynamo_store import save_cost_basis
            save_cost_basis(ticker, avg_cost)
            return
        except Exception as e:
            logger.warning(f"DynamoDB write failed, falling back to local: {e}")

    # Local fallback
    data = {}
    if os.path.exists(LOCAL_FILE):
        try:
            with open(LOCAL_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            pass
    data[ticker.upper()] = round(float(avg_cost), 2)
    with open(LOCAL_FILE, "w") as f:
        json.dump(data, f, indent=2)


def calculate_tax(ticker: str, shares: float, current_price: float) -> dict:
    """Calculate tax impact of selling a position."""
    avg_cost = get(ticker)
    if avg_cost is None:
        return {
            "available": False,
            "message":   f"Avg cost not saved. Run /tax {ticker} to enter it."
        }

    gain_per_share  = current_price - avg_cost
    total_gain      = round(gain_per_share * shares, 2)
    short_term_tax  = round(total_gain * 0.22, 2) if total_gain > 0 else 0
    long_term_tax   = round(total_gain * 0.15, 2) if total_gain > 0 else 0
    proceeds        = round(current_price * shares, 2)

    return {
        "available":      True,
        "avg_cost":       avg_cost,
        "current_price":  current_price,
        "shares":         shares,
        "gain_per_share": round(gain_per_share, 2),
        "total_gain":     total_gain,
        "short_term_tax": short_term_tax,
        "long_term_tax":  long_term_tax,
        "proceeds":       proceeds,
        "net_short_term": round(proceeds - short_term_tax, 2),
        "net_long_term":  round(proceeds - long_term_tax, 2),
    }
