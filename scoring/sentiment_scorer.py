from data.finnhub_client import finnhub_client


def score_sentiment(ticker: str) -> dict:
    """
    Scores sentiment using analyst recommendations from Finnhub.

    We tried headline keyword scoring but found it unreliable:
    - Headlines from yfinance include unrelated market news
    - Keywords like 'buy' and 'bullish' appear without context
    - Analyst recommendations are more accurate and trustworthy

    Analyst score breakdown:
        strong buy  = 10 points
        buy         = 7.5 points
        hold        = 5 points
        sell        = 2.5 points
        strong sell = 0 points

    Returns a weighted average as the final score 0-10.
    """
    analysts = finnhub_client.get_analyst_recommendations(ticker)
    earnings = finnhub_client.get_earnings_calendar(ticker)

    return {
        "score":      analysts["score"],
        "strong_buy": analysts["strong_buy"],
        "buy":        analysts["buy"],
        "hold":       analysts["hold"],
        "sell":       analysts["sell"],
        "earnings":   earnings,
    }
