from scoring.fundamental_scorer import score_fundamentals
from scoring.momentum_scorer    import score_momentum
from scoring.sentiment_scorer   import score_sentiment
import config


def score_stock(ticker: str) -> dict:
    """
    Combines all three scorers into one final score 0-10.

    Weights from config.py:
        Fundamental : 40%  (revenue, earnings, PE, margin)
        Momentum    : 35%  (moving averages, RSI, 52-week)
        Sentiment   : 25%  (analyst recommendations)

    Categories:
        7.0+        → HOLD   — strong, keep it
        5.0 - 6.9   → WATCH  — monitor closely
        below 5.0   → ROTATE — consider selling
    """
    fundamental = score_fundamentals(ticker)
    momentum    = score_momentum(ticker)
    sentiment   = score_sentiment(ticker)

    final_score = round(
        (fundamental["score"] * config.FUNDAMENTAL_WEIGHT) +
        (momentum["score"]    * config.MOMENTUM_WEIGHT)    +
        (sentiment["score"]   * config.SENTIMENT_WEIGHT),
        2
    )

    if final_score >= 7.0:
        category = "HOLD"
        action   = "Strong — keep holding"
    elif final_score >= 5.0:
        category = "WATCH"
        action   = "Monitor closely"
    else:
        category = "ROTATE"
        action   = "Consider rotating out"

    # Earnings warning — flag if earnings within 14 days
    earnings       = sentiment.get("earnings", {})
    earnings_warn  = ""
    if earnings.get("upcoming") and earnings.get("days_away") is not None:
        days = earnings["days_away"]
        if days <= 14:
            earnings_warn = f"⚠️  Earnings in {days} days"

    return {
        "ticker":            ticker,
        "final_score":       final_score,
        "category":          category,
        "action":            action,
        "fundamental_score": fundamental["score"],
        "momentum_score":    momentum["score"],
        "sentiment_score":   sentiment["score"],
        "fundamental_notes": fundamental["notes"],
        "momentum_notes":    momentum["notes"],
        "company_name":      fundamental.get("company_name", ticker),
        "sector":            fundamental.get("sector", "Unknown"),
        "current_price":     momentum.get("current_price"),
        "earnings_warning":  earnings_warn,
    }


def score_portfolio(tickers: list) -> list:
    """
    Scores a list of stocks and sorts by final score descending.
    """
    results = []
    for ticker in tickers:
        try:
            result = score_stock(ticker)
            results.append(result)
            warn = f"  {result['earnings_warning']}" if result["earnings_warning"] else ""
            print(f"  {ticker}: {result['final_score']}/10 — {result['category']}{warn}")
        except Exception as e:
            print(f"  Could not score {ticker}: {e}")

    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results
