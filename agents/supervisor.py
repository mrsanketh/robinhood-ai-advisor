"""
supervisor.py

Routes questions to the right agent using Gemini Flash.
Entry point for all conversational AI in the Telegram bot.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
import config
import logging
import re

logger = logging.getLogger(__name__)


ROUTING_PROMPT = """Classify this message into exactly one category:

PORTFOLIO  - questions about current holdings, scores, values, allocation, tax, performance
ROTATION   - questions about selling, rotating, trimming positions, what to sell
SCREENER   - questions about buying new stocks, finding opportunities, comparing stocks
TRADE      - recording a trade already executed: "I sold X shares", "I bought X shares"
OTHER      - greetings, unclear questions

Message: {question}

Reply with only one word: PORTFOLIO, ROTATION, SCREENER, TRADE, or OTHER"""


def route_question(question: str) -> str:
    """Use Gemini to classify the question."""
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=config.GEMINI_API_KEY,
            temperature=0,
        )
        response = llm.invoke(ROUTING_PROMPT.format(question=question))
        route    = response.content.strip().upper().split()[0]

        if route not in ["PORTFOLIO", "ROTATION", "SCREENER", "TRADE", "OTHER"]:
            route = "PORTFOLIO"

        logger.info(f"Routed '{question[:50]}' → {route}")
        return route

    except Exception as e:
        logger.error(f"Routing failed: {e}")
        return "PORTFOLIO"


def handle_trade_recording(message: str) -> str:
    """
    Parse and record a trade from natural language.
    Examples:
      "I sold 23 shares of SHOP at $103"
      "I bought 2 shares of CAT at $879"
    """
    try:
        from portfolio.trade_history import record_trade

        message_upper = message.upper()

        # Determine action
        if "SOLD" in message_upper or "SELL" in message_upper:
            action = "SELL"
        elif "BOUGHT" in message_upper or "BUY" in message_upper or "PURCHASED" in message_upper:
            action = "BUY"
        else:
            return "I could not determine if this was a buy or sell. Try: \"I sold 23 shares of SHOP at $103\""

        # Extract shares
        shares_match = re.search(r'(\d+\.?\d*)\s+share', message, re.IGNORECASE)
        shares = float(shares_match.group(1)) if shares_match else None

        # Extract ticker — look for all-caps 2-5 letter word
        ticker_match = re.search(r'\b([A-Z]{2,5})\b', message_upper)
        # Skip common words
        skip_words = {"SOLD", "BOUGHT", "SHARES", "SHARE", "AT", "OF", "THE", "BUY", "SELL", "ALL", "MY"}
        ticker = None
        for match in re.finditer(r'\b([A-Z]{2,5})\b', message_upper):
            candidate = match.group(1)
            if candidate not in skip_words:
                ticker = candidate
                break

        # Extract price
        price_match = re.search(r'\$(\d+\.?\d*)', message)
        price = float(price_match.group(1)) if price_match else None

        if not all([ticker, shares, price]):
            missing = []
            if not ticker: missing.append("ticker")
            if not shares: missing.append("number of shares")
            if not price:  missing.append("price")
            return (
                f"Could not parse: missing {', '.join(missing)}.\n\n"
                f"Try: \"I sold 23 shares of SHOP at $103\""
            )

        success = record_trade(action, ticker, shares, price, reason="via natural language")

        if success:
            total = round(shares * price, 2)
            return (
                f"✅ Trade recorded:\n\n"
                f"{action} {shares} shares of {ticker} at ${price}\n"
                f"Total: ${total:,.2f}\n\n"
                f"Your portfolio history is updated."
            )
        else:
            return "Failed to record trade. Please try again."

    except Exception as e:
        logger.error(f"Trade recording error: {e}")
        return f"Could not record trade: {e}\n\nTry: \"I sold 23 shares of SHOP at $103\""


def run_supervisor(question: str) -> str:
    """Route question to right agent and return response."""
    route = route_question(question)

    if route == "TRADE":
        return handle_trade_recording(question)

    elif route == "ROTATION":
        from agents.rotation_agent import run_rotation_agent
        return run_rotation_agent(question)

    elif route == "SCREENER":
        from agents.screener_agent import run_screener_agent
        return run_screener_agent(question)

    elif route == "OTHER":
        return (
            "I can help with your portfolio. Try asking:\n"
            "\"How is NVDA doing?\"\n"
            "\"Should I sell SHOP?\"\n"
            "\"Find me a healthcare stock\"\n"
            "\"What is my portfolio worth?\"\n"
            "\"I sold 23 shares of SHOP at $103\""
        )

    else:
        from agents.portfolio_agent import run_portfolio_agent
        return run_portfolio_agent(question)
