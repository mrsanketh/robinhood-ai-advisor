"""
screener_agent.py

Finds new stocks to buy from a universe of quality companies.
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
    Filter by sector: technology, healthcare, finance, consumer, industrial, energy, or all.
    """
    from scoring.engine        import score_stock
    from data.robinhood_client import robinhood_client

    holdings        = robinhood_client.get_holdings()
    current_tickers = [h["ticker"] for h in holdings]

    universe = {
        "technology":  ["MSFT", "GOOGL", "AAPL", "NVDA", "META", "AMZN", "AMD"],
        "healthcare":  ["LLY", "UNH", "JNJ", "ABT", "TMO", "PFE", "ABBV"],
        "finance":     ["JPM", "GS", "V", "MA", "BRK-B", "BAC"],
        "consumer":    ["PG", "KO", "PEP", "WMT", "COST", "HD"],
        "industrial":  ["CAT", "DE", "HON", "GE", "UPS"],
        "energy":      ["XOM", "CVX", "COP", "EOG"],
    }

    if sector.lower() == "all":
        candidates = [t for s in universe.values() for t in s]
    else:
        candidates = universe.get(sector.lower(), [t for s in universe.values() for t in s])

    candidates = [t for t in candidates if t not in current_tickers]

    results = []
    for ticker in candidates[:8]:
        try:
            r = score_stock(ticker)
            if r["final_score"] >= 7.0:
                results.append(r)
        except Exception:
            continue

    if not results:
        return f"No strong opportunities found in {sector} sector right now."

    results.sort(key=lambda x: x["final_score"], reverse=True)
    output = f"Top opportunities ({sector}):\n\n"
    for r in results[:5]:
        output += f"{r['ticker']} — {r['company_name']}\n"
        output += f"  Score: {r['final_score']}/10 | Price: ${r['current_price']}\n"
        if r["fundamental_notes"]:
            output += f"  {r['fundamental_notes'][0]}\n\n"
    return output


@tool
def compare_two_stocks(ticker1: str, ticker2: str) -> str:
    """Compare two stocks side by side on all metrics."""
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
    winner  = ticker1.upper() if r1["final_score"] > r2["final_score"] else ticker2.upper()
    result += f"\nWinner: {winner}"
    return result


def run_screener_agent(question: str) -> str:
    """Run the screener agent with a question."""
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=config.GEMINI_API_KEY,
            temperature=0.1,
        )

        tools = [scan_for_opportunities, compare_two_stocks]

        system_prompt = (
            "You are a stock screener finding new investment opportunities. "
            "Scan for stocks scoring 7.0+ that the investor does not already own. "
            "Consider sector diversification. "
            "Be specific about why a stock looks good. "
            "No markdown. Keep it concise for Telegram."
        )

        agent    = create_react_agent(llm, tools, prompt=system_prompt)
        result   = agent.invoke({"messages": [("user", question)]})
        content  = result["messages"][-1].content

        # Handle cases where Gemini returns a list with metadata
        if isinstance(content, list):
            text_parts = [c["text"] for c in content if isinstance(c, dict) and "text" in c]
            return " ".join(text_parts)

        return content

    except Exception as e:
        logger.error(f"Screener agent error: {e}")
        return "Sorry, screener failed. Try again in a moment."
