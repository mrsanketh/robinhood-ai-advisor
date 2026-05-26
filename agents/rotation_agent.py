"""
rotation_agent.py

Handles rotation and buy/sell decisions.
Uses LangGraph create_react_agent.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent
import config
import logging

logger = logging.getLogger(__name__)


@tool
def get_rotation_suggestions() -> str:
    """Get current rotation suggestions based on position sizing rules."""
    from portfolio.rotation_engine import run_rotation_analysis, format_suggestion
    suggestions = run_rotation_analysis()
    if not suggestions:
        return "No rotations needed. All positions are within their allowed limits."
    result = ""
    for s in suggestions:
        result += format_suggestion(s) + "\n\n"
    return result


@tool
def check_position_sizing(ticker: str) -> str:
    """Check if a specific position is within its allowed size limit."""
    from data.robinhood_client     import robinhood_client
    from data.yfinance_client      import yf_client
    from scoring.engine            import score_stock
    from portfolio.rotation_engine import get_max_position

    holdings = robinhood_client.get_holdings()
    total    = robinhood_client.get_total_value()
    holding  = next((h for h in holdings if h["ticker"] == ticker.upper()), None)
    if not holding:
        return f"{ticker} not found in your portfolio."

    result      = score_stock(ticker.upper())
    score       = result["final_score"]
    price       = yf_client.get_current_price(ticker.upper())
    value       = holding["shares"] * price
    max_allowed = get_max_position(score, total)
    status      = "✅ within limit" if value <= max_allowed else f"⚠️ over limit by ${value - max_allowed:,.0f}"

    return (
        f"{ticker} position sizing:\n"
        f"  Score: {score}/10\n"
        f"  Current value: ${value:,.2f}\n"
        f"  Max allowed: ${max_allowed:,.2f}\n"
        f"  Status: {status}"
    )


@tool
def find_replacement_for(ticker: str) -> str:
    """Find the best replacement stock if selling a specific holding."""
    from data.robinhood_client     import robinhood_client
    from portfolio.rotation_engine import _find_best_replacement
    from data.yfinance_client      import yf_client

    holdings        = robinhood_client.get_holdings()
    current_tickers = [h["ticker"] for h in holdings]
    replacement     = _find_best_replacement(exclude_tickers=current_tickers, min_score=7.0)

    if not replacement:
        return "No strong replacement found right now."

    price = yf_client.get_current_price(replacement["ticker"])
    return (
        f"Best replacement for {ticker}:\n"
        f"  {replacement['ticker']} — {replacement['company_name']}\n"
        f"  Score: {replacement['final_score']}/10\n"
        f"  Price: ${price}\n"
        f"  Sector: {replacement['sector']}"
    )


def run_rotation_agent(question: str) -> str:
    """Run the rotation agent with a question."""
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=config.GEMINI_API_KEY,
            temperature=0.1,
            max_retries=0,
        )

        tools = [get_rotation_suggestions, check_position_sizing, find_replacement_for]

        system_prompt = (
            "You are a portfolio rotation advisor. "
            "Use position sizing rules to decide what to sell. "
            "Always check tax impact before recommending a sale. "
            "Give clear YES/WAIT recommendations. "
            "Be concise — this is Telegram. No markdown."
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
        logger.error(f"Rotation agent error: {e}")
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            return "Gemini quota reached for today. Try again tomorrow or use /rotate command instead."
        return "Sorry, rotation analysis failed. Try /rotate for suggestions."
