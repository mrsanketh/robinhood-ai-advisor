from data.yfinance_client import yf_client


def score_momentum(ticker: str) -> dict:
    """
    Scores a stock's price momentum from 0 to 10.

    Checks three things:
    1. Price vs moving averages — is the trend up or down?
    2. RSI                     — is it overbought or oversold?
    3. 52-week performance     — how has it done over the past year?

    Returns a dict with the score and plain English notes.
    """
    mas   = yf_client.get_moving_averages(ticker)
    rsi   = yf_client.get_rsi(ticker)
    perf  = yf_client.get_52_week_performance(ticker)

    score = 5.0
    notes = []

    current = mas.get("current")
    ma50    = mas.get("ma50")
    ma200   = mas.get("ma200")

    # ── 1. Price vs 50-day Moving Average ────────────
    # Is the stock above or below its short-term trend?
    # Above = bullish, below = bearish
    if current and ma50:
        pct = ((current - ma50) / ma50) * 100
        if pct > 5:
            score += 1.5
            notes.append(f"Price {pct:.1f}% above 50-day MA — bullish trend")
        elif pct > 0:
            score += 0.5
            notes.append(f"Price slightly above 50-day MA — mild bullish")
        elif pct > -5:
            score -= 0.5
            notes.append(f"Price slightly below 50-day MA — mild bearish")
        else:
            score -= 1.5
            notes.append(f"Price {abs(pct):.1f}% below 50-day MA — bearish")

    # ── 2. Price vs 200-day Moving Average ───────────
    # Is the long-term trend up or down?
    # This is the most important trend indicator
    if current and ma200:
        pct = ((current - ma200) / ma200) * 100
        if pct > 10:
            score += 1.5
            notes.append(f"Price {pct:.1f}% above 200-day MA — strong long-term trend")
        elif pct > 0:
            score += 0.5
            notes.append(f"Price above 200-day MA — long-term bullish")
        elif pct > -10:
            score -= 0.5
            notes.append(f"Price below 200-day MA — long-term bearish")
        else:
            score -= 1.5
            notes.append(f"Price {abs(pct):.1f}% below 200-day MA — avoid")

    # ── 3. RSI ────────────────────────────────────────
    # 30-65 = healthy range
    # Above 70 = overbought, risky to buy
    # Below 30 = oversold, potential opportunity
    if rsi:
        if 30 <= rsi <= 65:
            score += 1.0
            notes.append(f"RSI {rsi:.0f} — healthy range")
        elif 65 < rsi <= 70:
            score -= 0.5
            notes.append(f"RSI {rsi:.0f} — getting overbought, be careful")
        elif rsi > 70:
            score -= 1.5
            notes.append(f"RSI {rsi:.0f} — overbought, high pullback risk")
        elif rsi < 30:
            score -= 1.0
            notes.append(f"RSI {rsi:.0f} — oversold, possible opportunity but risky")

    # ── 4. 52-week Performance ────────────────────────
    # How has the stock performed over the past year?
    if perf is not None:
        if perf >= 30:
            score += 1.0
            notes.append(f"Up {perf:.0f}% in past year — strong momentum")
        elif perf >= 10:
            score += 0.5
            notes.append(f"Up {perf:.0f}% in past year — solid")
        elif perf >= 0:
            score += 0.0
            notes.append(f"Up {perf:.0f}% in past year — flat")
        elif perf >= -20:
            score -= 0.5
            notes.append(f"Down {abs(perf):.0f}% in past year — underperforming")
        else:
            score -= 1.0
            notes.append(f"Down {abs(perf):.0f}% in past year — significant decline")

    final_score = round(max(0.0, min(10.0, score)), 2)

    return {
        "score":         final_score,
        "current_price": current,
        "ma50":          ma50,
        "ma200":         ma200,
        "rsi":           rsi,
        "yearly_perf":   perf,
        "notes":         notes,
    }
