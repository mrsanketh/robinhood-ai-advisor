"""
screener_agent.py

Finds new stocks to buy from a 550-stock universe.
Uses LangGraph create_react_agent.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent
import config
import logging

logger = logging.getLogger(__name__)


@tool
def scan_for_opportunities(sector: str = "all") -> str:
    """
    Scan quality stocks for buying opportunities.
    Filter by sector: technology, healthcare, finance, consumer,
    industrial, energy, real_estate, materials, communication, or all.
    Returns top scoring stocks you do not already own.
    """
    from scoring.engine            import score_stock
    from data.robinhood_client     import robinhood_client
    from portfolio.stock_universe  import get_all_tickers, get_tickers_by_sector

    holdings        = robinhood_client.get_holdings()
    current_tickers = [h["ticker"] for h in holdings]

    if sector.lower() == "all":
        candidates = get_all_tickers()
    else:
        candidates = get_tickers_by_sector(sector)

    # Remove stocks already owned
    candidates = [t for t in candidates if t not in current_tickers]

    if not candidates:
        return f"No candidates found for sector: {sector}"

    # Score in batches — limit to avoid Finnhub rate limits
    # Score top 30 candidates per sector to keep response fast
    import random
    random.shuffle(candidates)
    candidates = candidates[:30]

    results = []
    for ticker in candidates:
        try:
            r = score_stock(ticker)
            if r["final_score"] >= 7.5:
                results.append(r)
        except Exception:
            continue

    if not results:
        return f"No strong opportunities found in {sector} sector right now. Try a different sector."

    results.sort(key=lambda x: x["final_score"], reverse=True)
    output = f"Top opportunities ({sector}) — stocks you don't own scoring 7.5+:\n\n"
    for r in results[:5]:
        output += f"{r['ticker']} — {r['company_name']}\n"
        output += f"  Score: {r['final_score']}/10 | Sector: {r['sector']} | Price: ${r['current_price']}\n"
        if r["fundamental_notes"]:
            output += f"  {r['fundamental_notes'][0]}\n"
        if r["momentum_notes"]:
            output += f"  {r['momentum_notes'][0]}\n\n"
    return output


@tool
def compare_two_stocks(ticker1: str, ticker2: str) -> str:
    """Compare two stocks side by side on all scoring metrics."""
    from scoring.engine import score_stock

    r1 = score_stock(ticker1.upper())
    r2 = score_stock(ticker2.upper())

    result  = f"Comparison: {ticker1.upper()} vs {ticker2.upper()}\n\n"
    result += f"{'Metric':<20} {ticker1.upper():<12} {ticker2.upper()}\n"
    result += f"{'─'*44}\n"
    result += f"{'Final score':<20} {r1['final_score']:<12} {r2['final_score']}\n"
    result += f"{'Fundamental':<20} {r1['fundamental_score']:<12} {r2['fundamental_score']}\n"
    result += f"{'Momentum':<20} {r1['momentum_score']:<12} {r2['momentum_score']}\n"
    result += f"{'Sentiment':<20} {r1['sentiment_score']:<12} {r2['sentiment_score']}\n"
    result += f"{'Category':<20} {r1['category']:<12} {r2['category']}\n"
    result += f"{'Price':<20} ${r1['current_price']:<11} ${r2['current_price']}\n"
    result += f"{'Sector':<20} {r1['sector']:<12} {r2['sector']}\n"

    winner = ticker1.upper() if r1["final_score"] > r2["final_score"] else ticker2.upper()
    result += f"\nWinner: {winner} (by {abs(r1['final_score'] - r2['final_score']):.2f} points)"
    return result


@tool
def get_available_sectors() -> str:
    """Get list of available sectors to scan."""
    from portfolio.stock_universe import get_sectors
    sectors = get_sectors()
    return "Available sectors:\n" + "\n".join(f"  → {s}" for s in sectors) + "\n\nUse: scan_for_opportunities(sector='healthcare')"


def run_screener_agent(question: str) -> str:
    """Run the screener agent with a question."""
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=config.GEMINI_API_KEY,
            temperature=0.1,
        )

        tools = [scan_for_opportunities, compare_two_stocks, get_available_sectors]

        system_prompt = (
            "You are a stock screener finding new investment opportunities from a 550-stock universe. "
            "Scan for stocks scoring 7.5+ that the investor does not already own. "
            "Consider sector diversification — if they own many tech stocks suggest other sectors. "
            "Be specific about why each stock looks good. "
            "No markdown. Keep it concise for Telegram."
        )

        agent    = create_react_agent(llm, tools, prompt=system_prompt)
        result   = agent.invoke({"messages": [("user", question)]})
        content  = result["messages"][-1].content

        if isinstance(content, list):
            text_parts = [c["text"] for c in content if isinstance(c, dict) and "text" in c]
            return " ".join(text_parts)

        return content

    except Exception as e:
        logger.error(f"Screener agent error: {e}")
        return "Sorry, screener failed. Try again in a moment."
