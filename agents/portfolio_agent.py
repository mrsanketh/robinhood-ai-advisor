"""
portfolio_agent.py

Answers questions about your current portfolio.
Uses LangGraph create_react_agent (modern approach, no AgentExecutor).
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent
import config
import logging

logger = logging.getLogger(__name__)


@tool
def get_portfolio_summary() -> str:
    """Get current portfolio value, score, and category breakdown."""
    from data.robinhood_client import robinhood_client
    from scoring.engine        import score_portfolio

    holdings  = robinhood_client.get_holdings()
    total     = robinhood_client.get_total_value()
    tickers   = [h["ticker"] for h in holdings]
    results   = score_portfolio(tickers)

    hold   = [r for r in results if r["category"] == "HOLD"]
    watch  = [r for r in results if r["category"] == "WATCH"]
    rotate = [r for r in results if r["category"] == "ROTATE"]
    avg    = sum(r["final_score"] for r in results) / len(results)

    summary  = f"Portfolio: ${total:,.0f} | Score: {avg:.1f}/10\n"
    summary += f"HOLD: {len(hold)} | WATCH: {len(watch)} | ROTATE: {len(rotate)}\n\n"
    summary += "All positions:\n"
    for r in sorted(results, key=lambda x: x["final_score"], reverse=True):
        summary += f"  {r['ticker']}: {r['final_score']}/10 {r['category']}\n"
    return summary


@tool
def get_stock_score(ticker: str) -> str:
    """Get detailed score for a specific stock ticker."""
    from scoring.engine import score_stock
    r       = score_stock(ticker.upper())
    result  = f"{r['ticker']} — {r['company_name']}\n"
    result += f"Score: {r['final_score']}/10 {r['category']}\n"
    result += f"Fundamental: {r['fundamental_score']}/10\n"
    result += f"Momentum: {r['momentum_score']}/10\n"
    result += f"Sentiment: {r['sentiment_score']}/10\n"
    result += f"Price: ${r['current_price']}\n"
    if r.get("earnings_warning"):
        result += f"{r['earnings_warning']}\n"
    result += "\nFundamentals:\n"
    for note in r["fundamental_notes"][:3]:
        result += f"  → {note}\n"
    result += "\nMomentum:\n"
    for note in r["momentum_notes"][:3]:
        result += f"  → {note}\n"
    return result


@tool
def get_tax_impact(ticker: str) -> str:
    """Get tax impact if selling a position. Uses saved cost basis."""
    from data.robinhood_client      import robinhood_client
    from data.yfinance_client       import yf_client
    from portfolio.cost_basis_store import calculate_tax

    holdings = robinhood_client.get_holdings()
    holding  = next((h for h in holdings if h["ticker"] == ticker.upper()), None)
    if not holding:
        return f"{ticker} not found in your portfolio."

    price = yf_client.get_current_price(ticker.upper())
    tax   = calculate_tax(ticker.upper(), holding["shares"], price)

    if not tax["available"]:
        return f"No cost basis saved for {ticker}. Ask the user to provide their average cost via /tax {ticker}."

    result  = f"Tax impact for {ticker}:\n"
    result += f"  Avg cost: ${tax['avg_cost']} | Current: ${tax['current_price']}\n"
    result += f"  Shares: {tax['shares']}\n"
    result += f"  Total gain: ${tax['total_gain']:,.2f}\n"
    result += f"  Short term tax (22%): ${tax['short_term_tax']:,.2f}\n"
    result += f"  Long term tax (15%): ${tax['long_term_tax']:,.2f}\n"
    result += f"  Net proceeds (long term): ${tax['net_long_term']:,.2f}\n"
    return result


@tool
def get_position_details(ticker: str) -> str:
    """Get holding details for a specific stock — shares, value, allocation."""
    from data.robinhood_client import robinhood_client
    from data.yfinance_client  import yf_client

    holdings = robinhood_client.get_holdings()
    total    = robinhood_client.get_total_value()
    holding  = next((h for h in holdings if h["ticker"] == ticker.upper()), None)
    if not holding:
        return f"{ticker} not found in your portfolio."

    price      = yf_client.get_current_price(ticker.upper())
    value      = holding["shares"] * price
    allocation = (value / total) * 100

    result  = f"{ticker} position:\n"
    result += f"  Shares: {holding['shares']}\n"
    result += f"  Current price: ${price}\n"
    result += f"  Current value: ${value:,.2f}\n"
    result += f"  Portfolio allocation: {allocation:.1f}%\n"
    return result


def run_portfolio_agent(question: str) -> str:
    """Run the portfolio agent with a question."""
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=config.GEMINI_API_KEY,
            temperature=0.1,
        )

        tools = [get_portfolio_summary, get_stock_score, get_tax_impact, get_position_details]

        system_prompt = (
            "You are a personal portfolio advisor. "
            "Use tools to get real data before answering. "
            "Be concise — this is Telegram. No markdown formatting."
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
        logger.error(f"Portfolio agent error: {e}")
        return f"Sorry, I had trouble answering that. Try /portfolio for a summary."
