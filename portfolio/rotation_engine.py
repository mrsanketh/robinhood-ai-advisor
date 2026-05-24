from scoring.engine        import score_stock, score_portfolio
from data.robinhood_client import robinhood_client
from data.yfinance_client  import yf_client
import config
import math


# ── Position sizing rules ─────────────────────────────────────────
# Based on score → max allowed % of total portfolio
# This is how professional portfolio managers size positions
POSITION_LIMITS = [
    (8.0, 10.1, 0.12),   # score 8-10  → max 12%
    (7.0,  8.0, 0.08),   # score 7-8   → max 8%
    (6.0,  7.0, 0.05),   # score 6-7   → max 5%
    (5.0,  6.0, 0.03),   # score 5-6   → max 3%
    (4.0,  5.0, 0.01),   # score 4-5   → max 1%
    (0.0,  4.0, 0.00),   # score 0-4   → exit completely
]


def get_max_position(score: float, total_portfolio: float) -> float:
    """
    Returns the maximum dollar amount allowed for a stock at this score.
    """
    for low, high, pct in POSITION_LIMITS:
        if low <= score < high:
            return round(total_portfolio * pct, 2)
    return 0.0


def get_rotation_candidates(holdings: list, results: list, total_value: float) -> list:
    """
    Find stocks where current position exceeds the allowed maximum.
    Calculate exactly how many shares to sell to get back to the limit.
    """
    results_map = {r["ticker"]: r for r in results}
    candidates  = []

    for holding in holdings:
        ticker = holding["ticker"]
        result = results_map.get(ticker)
        if not result:
            continue

        score         = result["final_score"]
        shares        = holding["shares"]
        price         = yf_client.get_current_price(ticker)
        current_equity = round(shares * price, 2)
        max_allowed   = get_max_position(score, total_value)

        # No action needed if within limit
        if current_equity <= max_allowed:
            continue

        # Calculate how much to sell
        equity_to_sell   = round(current_equity - max_allowed, 2)
        equity_to_keep   = max_allowed
        shares_to_sell   = math.floor(equity_to_sell / price)
        shares_to_keep   = math.floor(shares - shares_to_sell)

        if shares_to_sell == 0:
            continue

        # Determine action label
        if max_allowed == 0:
            action = "Exit completely — score below 4.0"
        else:
            pct_label = int((1 - (equity_to_keep / current_equity)) * 100)
            action = f"Trim {pct_label}% — reduce to max allowed ${max_allowed:,.0f}"

        candidates.append({
            "ticker":           ticker,
            "score":            score,
            "category":         result["category"],
            "price":            price,
            "total_shares":     shares,
            "shares_to_sell":   shares_to_sell,
            "shares_to_keep":   shares_to_keep,
            "current_equity":   current_equity,
            "equity_to_sell":   round(shares_to_sell * price, 2),
            "equity_to_keep":   round(shares_to_keep * price, 2),
            "max_allowed":      max_allowed,
            "action":           action,
            "notes":            result["fundamental_notes"] + result["momentum_notes"],
        })

    # Only flag if capital freed justifies the trade
    MIN_CAPITAL = 1000
    candidates = [c for c in candidates if c["equity_to_sell"] >= MIN_CAPITAL]

    candidates.sort(key=lambda x: x["score"])
    return candidates


def find_replacements(candidates: list, current_tickers: list) -> list:
    """For each candidate, find best replacement for freed capital."""
    suggestions  = []
    used_tickers = []

    meaningful = [c for c in candidates if c["equity_to_sell"] >= 500]
    small      = [c for c in candidates if c["equity_to_sell"] < 500]

    for candidate in meaningful:
        replacement = _find_best_replacement(
            exclude_tickers=current_tickers + used_tickers,
            min_score=config.BUY_SCORE_THRESHOLD
        )

        if not replacement:
            suggestions.append({
                "sell":     candidate,
                "buy":      None,
                "message":  f"No strong replacement found. Hold ${candidate['equity_to_sell']:,.0f} cash.",
                "combined": False,
            })
            continue

        buy_ticker    = replacement["ticker"]
        buy_price     = yf_client.get_current_price(buy_ticker)
        shares_to_buy = int(candidate["equity_to_sell"] / buy_price) if buy_price > 0 else 0
        used_tickers.append(buy_ticker)

        suggestions.append({
            "sell": candidate,
            "buy": {
                "ticker":       buy_ticker,
                "score":        replacement["final_score"],
                "price":        buy_price,
                "shares":       shares_to_buy,
                "cost":         round(shares_to_buy * buy_price, 2),
                "company_name": replacement["company_name"],
                "notes":        replacement["fundamental_notes"][:3],
            } if shares_to_buy > 0 else None,
            "message": f"Not enough capital (${candidate['equity_to_sell']:,.0f}) for 1 share of {buy_ticker} (${buy_price:.0f}). Hold cash." if shares_to_buy == 0 else "",
            "combined": False,
        })

    # Combine small positions
    if small:
        total_small   = sum(s["equity_to_sell"] for s in small)
        small_tickers = [s["ticker"] for s in small]

        replacement = _find_best_replacement(
            exclude_tickers=current_tickers + used_tickers,
            min_score=config.BUY_SCORE_THRESHOLD
        )

        buy = None
        if replacement:
            buy_ticker    = replacement["ticker"]
            buy_price     = yf_client.get_current_price(buy_ticker)
            shares_to_buy = int(total_small / buy_price) if buy_price > 0 else 0
            if shares_to_buy > 0:
                buy = {
                    "ticker":       buy_ticker,
                    "score":        replacement["final_score"],
                    "price":        buy_price,
                    "shares":       shares_to_buy,
                    "cost":         round(shares_to_buy * buy_price, 2),
                    "company_name": replacement["company_name"],
                    "notes":        replacement["fundamental_notes"][:3],
                }

        suggestions.append({
            "sell": {
                "ticker":         " + ".join(small_tickers),
                "score":          min(s["score"] for s in small),
                "total_shares":   None,
                "shares_to_sell": None,
                "shares_to_keep": None,
                "current_equity": sum(s["current_equity"] for s in small),
                "equity_to_sell": total_small,
                "equity_to_keep": sum(s["equity_to_keep"] for s in small),
                "max_allowed":    None,
                "action":         "Combined small positions",
                "notes":          [],
            },
            "buy":      buy,
            "message":  f"Combined ${total_small:.0f}. Hold as cash." if not buy else "",
            "combined": True,
        })

    return suggestions


def _find_best_replacement(exclude_tickers: list, min_score: float) -> dict:
    """Scan replacement candidates and return highest scoring stock."""
    candidates = [
        "LLY", "UNH", "JNJ", "ABT", "TMO",
        "JPM", "GS", "V", "MA", "BRK-B",
        "NEE", "DUK",
        "PG", "KO", "PEP", "WMT",
        "CAT", "DE", "HON", "GE",
    ]
    candidates = [t for t in candidates if t not in exclude_tickers]
    if not candidates:
        return None

    best       = None
    best_score = 0.0
    print(f"  Scanning {len(candidates)} replacement candidates...")

    for ticker in candidates:
        try:
            result = score_stock(ticker)
            if result["final_score"] > best_score and result["final_score"] >= min_score:
                best       = result
                best_score = result["final_score"]
        except Exception:
            continue

    return best


def get_recommendation(sell: dict, buy: dict) -> tuple:
    """
    Returns (recommendation, reasons, wait_reason) based on three rules:

    YES if:
      1. Buy score is 1.5+ points higher than sell score
      2. No earnings warning on either stock
      (tax is checked separately via /tax command)

    WAIT if:
      1. Score difference < 1.5 — not worth the friction
      2. Earnings within 7 days for sell stock — wait for results first

    Returns: ("YES"/"WAIT"/"NO_BUY", reasons_list, wait_reason_str)
    """
    if not buy:
        return "NO_BUY", [], "No replacement found — hold cash after selling"

    score_diff     = round(buy["score"] - sell["score"], 2)
    earnings_warn  = sell.get("earnings_warning", "")
    has_earnings   = bool(earnings_warn)

    reasons  = []
    wait_reasons = []

    # Check score difference
    if score_diff >= 1.5:
        reasons.append(f"{buy['ticker']} scores {score_diff} points higher than {sell['ticker']}")
    else:
        wait_reasons.append(f"Score difference only {score_diff} pts — marginal improvement")

    # Check earnings risk
    if has_earnings:
        wait_reasons.append(f"{sell['ticker']} has {earnings_warn} — wait for results first")
    else:
        reasons.append(f"No earnings risk for {sell['ticker']}")

    # Final decision
    if wait_reasons:
        return "WAIT", reasons, " | ".join(wait_reasons)
    else:
        return "YES", reasons, ""


def format_suggestion(suggestion: dict) -> str:
    """Format suggestion as readable text with clear recommendation."""
    sell  = suggestion["sell"]
    buy   = suggestion.get("buy")
    lines = []

    if suggestion.get("combined"):
        lines.append("🔄 COMBINED — Small positions")
        lines.append(f"SELL: {sell['ticker']}")
        lines.append(f"  Action:         {sell['action']}")
        lines.append(f"  Capital freed:  ${sell['equity_to_sell']:,.2f}")
    else:
        lines.append(f"🔄 ROTATION")
        lines.append(f"")
        lines.append(f"SELL: {sell['ticker']}")
        lines.append(f"  Score:          {sell['score']}/10")
        lines.append(f"  Action:         {sell['action']}")
        lines.append(f"  Current value:  ${sell['current_equity']:,.2f}")
        lines.append(f"  Max allowed:    ${sell['max_allowed']:,.2f}")
        lines.append(f"  Shares to sell: {sell['shares_to_sell']}")
        lines.append(f"  Shares to keep: {sell['shares_to_keep']}")
        lines.append(f"  Capital freed:  ${sell['equity_to_sell']:,.2f}")
        if sell['shares_to_keep'] > 0:
            lines.append(f"  Keeping:        ${sell['equity_to_keep']:,.2f} exposure")
        for note in sell.get("notes", [])[:3]:
            lines.append(f"  → {note}")

    if buy:
        lines.append(f"")
        lines.append(f"BUY: {buy['ticker']} — {buy['company_name']}")
        lines.append(f"  Score:      {buy['score']}/10")
        lines.append(f"  Price:      ${buy['price']}")
        lines.append(f"  Shares:     {buy['shares']}")
        lines.append(f"  Total cost: ${buy['cost']:,.2f}")
        for note in buy.get("notes", [])[:3]:
            lines.append(f"  → {note}")

        # Get recommendation
        rec, reasons, wait_reason = get_recommendation(sell, buy)
        sell_ticker_clean = sell['ticker'].split('+')[0].strip()

        lines.append(f"")
        if rec == "YES":
            lines.append(f"✅ RECOMMENDATION: DO THE ROTATION")
            lines.append(f"")
            lines.append(f"Why:")
            for r in reasons:
                lines.append(f"  → {r}")
            lines.append(f"")
            lines.append(f"📋 Next steps:")
            lines.append(f"  1️⃣  /tax {sell_ticker_clean} — confirm tax impact")
            lines.append(f"  2️⃣  Sell {sell['shares_to_sell']} shares of {sell_ticker_clean} at 9:30am")
            lines.append(f"  3️⃣  Buy {buy['shares']} shares of {buy['ticker']} with proceeds")
        else:
            lines.append(f"⏳ RECOMMENDATION: WAIT")
            lines.append(f"")
            lines.append(f"Why:")
            lines.append(f"  → {wait_reason}")
            lines.append(f"")
            lines.append(f"📋 What to do:")
            lines.append(f"  → Monitor {sell_ticker_clean} — run /score {sell_ticker_clean} next week")
            lines.append(f"  → Re-run /rotate after any earnings pass")
    else:
        if suggestion.get("message"):
            lines.append(f"  {suggestion['message']}")

    return "\n".join(lines)


def run_rotation_analysis() -> list:
    """Full rotation analysis pipeline."""
    print("Reading portfolio...")
    holdings        = robinhood_client.get_holdings()
    current_tickers = [h["ticker"] for h in holdings]
    total_value     = robinhood_client.get_total_value()

    print(f"Total portfolio: ${total_value:,.0f}")
    print(f"Scoring {len(holdings)} holdings...")
    results    = score_portfolio(current_tickers)

    print("Checking position limits...")
    candidates = get_rotation_candidates(holdings, results, total_value)

    if not candidates:
        print("All positions within limits. Portfolio looks healthy.")
        return []

    print(f"Found {len(candidates)} positions over limit. Finding replacements...")
    suggestions = find_replacements(candidates, current_tickers)
    return suggestions
