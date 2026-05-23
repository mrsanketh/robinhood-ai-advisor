"""
cost_basis_store.py

Stores your real average cost per stock in a local JSON file.
In Phase 4 this moves to DynamoDB.

The Telegram bot asks you once per stock when you run /rotate.
You check Robinhood app, reply with the number, it saves it forever.
"""

import json
import os

# Store in project root — never committed to GitHub (.gitignore)
STORE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "cost_basis.json"
)


def load_all() -> dict:
    """Load all saved cost basis values."""
    if not os.path.exists(STORE_FILE):
        return {}
    try:
        with open(STORE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def get(ticker: str) -> float | None:
    """Get saved avg cost for a ticker. Returns None if not saved yet."""
    data = load_all()
    return data.get(ticker.upper())


def save(ticker: str, avg_cost: float):
    """Save avg cost for a ticker."""
    data = load_all()
    data[ticker.upper()] = round(float(avg_cost), 2)
    with open(STORE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def calculate_tax(ticker: str, shares: float, current_price: float) -> dict:
    """
    Calculate tax impact of selling a position.
    Returns both short term and long term estimates.
    """
    avg_cost = get(ticker)
    if avg_cost is None:
        return {
            "available": False,
            "message":   "Avg cost not saved. Run /rotate to enter it."
        }

    gain_per_share   = current_price - avg_cost
    total_gain       = round(gain_per_share * shares, 2)
    short_term_tax   = round(total_gain * 0.22, 2) if total_gain > 0 else 0
    long_term_tax    = round(total_gain * 0.15, 2) if total_gain > 0 else 0
    proceeds         = round(current_price * shares, 2)

    return {
        "available":       True,
        "avg_cost":        avg_cost,
        "current_price":   current_price,
        "shares":          shares,
        "gain_per_share":  round(gain_per_share, 2),
        "total_gain":      total_gain,
        "short_term_tax":  short_term_tax,
        "long_term_tax":   long_term_tax,
        "proceeds":        proceeds,
        "net_short_term":  round(proceeds - short_term_tax, 2),
        "net_long_term":   round(proceeds - long_term_tax, 2),
    }
