from data.yfinance_client import yf_client


def score_fundamentals(ticker: str) -> dict:
    """
    Scores a stock's fundamentals from 0 to 10.

    Checks four things:
    1. Revenue growth  — is the company growing?
    2. Earnings growth — is it becoming more profitable?
    3. PE ratio        — is it reasonably priced?
    4. Profit margin   — is the business healthy?

    Returns a dict with the score and plain English notes.
    """
    info  = yf_client.get_info(ticker)
    score = 5.0   # start neutral
    notes = []

    # ── 1. Revenue Growth ─────────────────────────────
    # How fast is the company's revenue growing year over year?
    # >20% = strong, 0-10% = slow, negative = shrinking
    rev_growth = info.get("revenueGrowth")
    if rev_growth is not None:
        if rev_growth >= 0.20:
            score += 2.0
            notes.append(f"Revenue growing {rev_growth*100:.0f}% YoY — strong")
        elif rev_growth >= 0.10:
            score += 1.0
            notes.append(f"Revenue growing {rev_growth*100:.0f}% YoY — solid")
        elif rev_growth >= 0:
            score += 0.0
            notes.append(f"Revenue growing {rev_growth*100:.0f}% YoY — slow")
        elif rev_growth >= -0.10:
            score -= 1.0
            notes.append(f"Revenue declining {abs(rev_growth)*100:.0f}% — concerning")
        else:
            score -= 2.0
            notes.append(f"Revenue declining {abs(rev_growth)*100:.0f}% — red flag")

    # ── 2. Earnings Growth ────────────────────────────
    # Is the company becoming more profitable over time?
    earn_growth = info.get("earningsGrowth")
    if earn_growth is not None:
        if earn_growth >= 0.20:
            score += 1.5
            notes.append(f"Earnings growing {earn_growth*100:.0f}% — excellent")
        elif earn_growth >= 0.05:
            score += 0.5
            notes.append(f"Earnings growing {earn_growth*100:.0f}% — good")
        elif earn_growth < 0:
            score -= 1.5
            notes.append(f"Earnings declining {abs(earn_growth)*100:.0f}% — weak")

    # ── 3. PE Ratio ───────────────────────────────────
    # Price-to-Earnings: how much you pay for $1 of profit.
    # Lower = cheaper. But growth companies deserve higher PE.
    # We use a simple benchmark: <15 cheap, 15-30 fair, >50 expensive
    pe = info.get("trailingPE") or info.get("forwardPE")
    if pe is not None and pe > 0:
        if pe < 15:
            score += 1.0
            notes.append(f"PE {pe:.0f} — undervalued")
        elif pe < 30:
            score += 0.5
            notes.append(f"PE {pe:.0f} — fairly valued")
        elif pe < 50:
            score += 0.0
            notes.append(f"PE {pe:.0f} — priced for growth")
        elif pe < 80:
            score -= 0.5
            notes.append(f"PE {pe:.0f} — expensive")
        else:
            score -= 1.0
            notes.append(f"PE {pe:.0f} — very expensive")

    # ── 4. Profit Margin ──────────────────────────────
    # What % of revenue is actual profit?
    # >20% = great business, negative = losing money
    margin = info.get("profitMargins")
    if margin is not None:
        if margin >= 0.20:
            score += 0.5
            notes.append(f"Profit margin {margin*100:.0f}% — very healthy")
        elif margin >= 0.10:
            score += 0.0
            notes.append(f"Profit margin {margin*100:.0f}% — acceptable")
        elif margin < 0:
            score -= 1.0
            notes.append(f"Negative profit margin — losing money")

    # ── Clamp score between 0 and 10 ──────────────────
    final_score = round(max(0.0, min(10.0, score)), 2)

    return {
        "score":          final_score,
        "revenue_growth": rev_growth,
        "earnings_growth": earn_growth,
        "pe_ratio":       pe,
        "profit_margin":  margin,
        "sector":         info.get("sector", "Unknown"),
        "company_name":   info.get("longName", ticker),
        "notes":          notes,
    }
