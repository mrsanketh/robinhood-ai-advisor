from scoring.engine        import score_stock, score_portfolio
from data.robinhood_client import robinhood_client
from data.yfinance_client  import yf_client
import config


def get_rotation_candidates(holdings: list, results: list) -> list:
    """Return holdings that the scoring engine marked as ROTATE."""
    results_map = {r["ticker"]: r for r in results}
    rotate_out  = []

    for holding in holdings:
        ticker = holding["ticker"]
        result = results_map.get(ticker)
        if not result:
            continue
        if result["category"] == "ROTATE":
            rotate_out.append({
                "ticker":       ticker,
                "score":        result["final_score"],
                "shares":       holding["shares"],
                "avg_cost_api": holding["avg_cost"],
                "equity":       holding["equity"],
                "notes":        result["fundamental_notes"] + result["momentum_notes"],
            })

    rotate_out.sort(key=lambda x: x["score"])
    return rotate_out


def find_replacements(rotate_out: list, current_tickers: list) -> list:
    """
    For each rotation candidate, find the best replacement.
    Combines small positions (under $500) into one suggestion.
    """
    # Split into meaningful and small positions
    meaningful = [r for r in rotate_out if r["equity"] >= 500]
    small      = [r for r in rotate_out if r["equity"] < 500]

    suggestions = []
    used_tickers = []

    # Handle meaningful positions individually
    for candidate in meaningful:
        replacement = _find_best_replacement(
            exclude_tickers=current_tickers + used_tickers,
            min_score=config.BUY_SCORE_THRESHOLD
        )

        sell_equity = candidate["equity"]

        if not replacement:
            suggestions.append({
                "sell":    candidate,
                "buy":     None,
                "message": f"No strong replacement found. Hold cash from {candidate['ticker']} sale.",
                "combined": False,
            })
            continue

        buy_ticker    = replacement["ticker"]
        buy_price     = yf_client.get_current_price(buy_ticker)
        shares_to_buy = int(sell_equity / buy_price) if buy_price > 0 else 0
        used_tickers.append(buy_ticker)

        if shares_to_buy == 0:
            suggestions.append({
                "sell":    candidate,
                "buy":     None,
                "message": f"Not enough capital (${sell_equity:.0f}) to buy 1 share of {buy_ticker} (${buy_price:.0f}). Hold cash.",
                "combined": False,
            })
            continue

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
            },
            "tax_note": "⚠️  Check Robinhood app for your avg cost before trading",
            "combined": False,
        })

    # Handle small positions — combine them
    if small:
        total_small = sum(s["equity"] for s in small)
        small_tickers = [s["ticker"] for s in small]

        replacement = _find_best_replacement(
            exclude_tickers=current_tickers + used_tickers,
            min_score=config.BUY_SCORE_THRESHOLD
        )

        if replacement:
            buy_ticker    = replacement["ticker"]
            buy_price     = yf_client.get_current_price(buy_ticker)
            shares_to_buy = int(total_small / buy_price) if buy_price > 0 else 0

            suggestions.append({
                "sell": {
                    "ticker":  " + ".join(small_tickers),
                    "score":   min(s["score"] for s in small),
                    "shares":  None,
                    "equity":  total_small,
                    "notes":   [],
                },
                "buy": {
                    "ticker":       buy_ticker,
                    "score":        replacement["final_score"],
                    "price":        buy_price,
                    "shares":       shares_to_buy,
                    "cost":         round(shares_to_buy * buy_price, 2),
                    "company_name": replacement["company_name"],
                    "notes":        replacement["fundamental_notes"][:3],
                } if shares_to_buy > 0 else None,
                "message": f"Combined small positions. Hold ${total_small:.0f} cash if no shares can be bought." if shares_to_buy == 0 else "",
                "tax_note": "⚠️  Check Robinhood app for your avg cost before trading",
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
        except Exception as e:
            continue

    return best


def format_suggestion(suggestion: dict) -> str:
    """Format suggestion as readable text."""
    sell  = suggestion["sell"]
    buy   = suggestion.get("buy")
    lines = []

    if suggestion.get("combined"):
        lines.append(f"🔄 COMBINED ROTATION — Small positions")
        lines.append(f"SELL: {sell['ticker']} (combined)")
    else:
        lines.append(f"🔄 ROTATION SUGGESTION")
        lines.append(f"SELL: {sell['ticker']}")
        lines.append(f"  Score:  {sell['score']}/10")
        if sell.get("shares"):
            lines.append(f"  Shares: {sell['shares']}")
        lines.append(f"  Value:  ${sell['equity']:,.2f}")
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
        lines.append(f"")
        lines.append(f"  {suggestion.get('tax_note', '')}")
    else:
        lines.append(f"  {suggestion.get('message', '')}")

    return "\n".join(lines)


def run_rotation_analysis() -> list:
    """Full rotation analysis pipeline."""
    print("Reading portfolio...")
    holdings        = robinhood_client.get_holdings()
    current_tickers = [h["ticker"] for h in holdings]

    print(f"Scoring {len(holdings)} holdings...")
    results    = score_portfolio(current_tickers)

    print("Finding rotation candidates...")
    rotate_out = get_rotation_candidates(holdings, results)

    if not rotate_out:
        print("No rotation candidates. Portfolio looks healthy.")
        return []

    print(f"Found {len(rotate_out)} candidates. Finding replacements...")
    suggestions = find_replacements(rotate_out, current_tickers)
    return suggestions
