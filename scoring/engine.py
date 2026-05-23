from scoring.fundamental_scorer import score_fundamentals
from scoring.momentum_scorer    import score_momentum
import config


def score_stock(ticker: str) -> dict:
    """
    Combines fundamental + momentum into one final score.

    Weights (from config.py):
        Fundamental : 40%
        Momentum    : 35%
        Sentiment   : 25% (added in Phase 2 with Finnhub)

    For now sentiment defaults to neutral (5.0) until Phase 2.

    Final score 0-10:
        7+ = strong, hold or buy
        5-6 = neutral, watch
        below 4 = weak, rotation candidate
    """
    fundamental = score_fundamentals(ticker)
    momentum    = score_momentum(ticker)

    # Sentiment is neutral until Phase 2
    sentiment_score = 5.0

    # Weighted average
    # Phase 1: distribute sentiment weight between fundamental and momentum
    # so the total still adds up to 10
    f_weight = config.FUNDAMENTAL_WEIGHT + (config.SENTIMENT_WEIGHT * 0.5)
    m_weight = config.MOMENTUM_WEIGHT    + (config.SENTIMENT_WEIGHT * 0.5)

    final_score = round(
        (fundamental["score"] * f_weight) +
        (momentum["score"]    * m_weight),
        2
    )

    # Determine category
    if final_score >= 7.0:
        category = "HOLD"
        action   = "Strong — keep holding"
    elif final_score >= 5.0:
        category = "WATCH"
        action   = "Monitor closely"
    else:
        category = "ROTATE"
        action   = "Consider rotating out"

    return {
        "ticker":            ticker,
        "final_score":       final_score,
        "category":          category,
        "action":            action,
        "fundamental_score": fundamental["score"],
        "momentum_score":    momentum["score"],
        "sentiment_score":   sentiment_score,
        "fundamental_notes": fundamental["notes"],
        "momentum_notes":    momentum["notes"],
        "company_name":      fundamental.get("company_name", ticker),
        "sector":            fundamental.get("sector", "Unknown"),
        "current_price":     momentum.get("current_price"),
    }


def score_portfolio(tickers: list) -> list:
    """
    Scores a list of stocks and sorts by final score descending.
    Returns list of result dicts.
    """
    results = []
    for ticker in tickers:
        try:
            result = score_stock(ticker)
            results.append(result)
            print(f"  Scored {ticker}: {result['final_score']}/10 — {result['category']}")
        except Exception as e:
            print(f"  Could not score {ticker}: {e}")

    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results
