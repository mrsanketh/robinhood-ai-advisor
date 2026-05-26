"""
supervisor.py

Routes questions to the right agent using keyword matching first,
Gemini only when needed. Conserves free tier quota (20 req/day).
"""

import config
import logging
import re

logger = logging.getLogger(__name__)


def route_question(question: str) -> str:
    """
    Route question using keyword matching first — no Gemini needed.
    Falls back to Gemini only for ambiguous questions.
    """
    q = question.lower()

    # Trade recording — very specific patterns
    if any(w in q for w in ["i sold", "i bought", "i purchased", "i sell", "i buy"]):
        return "TRADE"

    # Rotation — sell/trim related
    if any(w in q for w in ["should i sell", "should i trim", "rotate", "trim", "exit", "reduce position", "sell my"]):
        return "ROTATION"

    # Screener — find/buy related
    if any(w in q for w in ["find me", "screen", "what should i buy", "recommend", "suggest", "looking for", "sector", "new stock", "which stock to buy"]):
        return "SCREENER"

    # Portfolio — holdings/status related
    if any(w in q for w in ["portfolio", "worth", "value", "score", "tax", "performance", "how is", "how am i", "top holding", "benchmark", "history"]):
        return "PORTFOLIO"

    # Ambiguous — use Gemini only here
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=config.GEMINI_API_KEY,
            temperature=0,
            max_retries=0,  # no retries — fail fast to preserve quota
        )
        prompt = (
            "Classify this message into one word: PORTFOLIO, ROTATION, SCREENER, TRADE, or OTHER\n\n"
            f"Message: {question}\n\nReply with one word only."
        )
        response = llm.invoke(prompt)
        route    = response.content.strip().upper().split()[0]
        if route not in ["PORTFOLIO", "ROTATION", "SCREENER", "TRADE", "OTHER"]:
            route = "PORTFOLIO"
        logger.info(f"Gemini routed '{question[:40]}' → {route}")
        return route

    except Exception as e:
        logger.warning(f"Gemini routing failed: {e}")
        return "PORTFOLIO"


def handle_trade_recording(message: str) -> str:
    """Parse and record a trade from natural language."""
    try:
        from portfolio.trade_history import record_trade

        message_upper = message.upper()

        if "SOLD" in message_upper or "SELL" in message_upper:
            action = "SELL"
        elif "BOUGHT" in message_upper or "BUY" in message_upper or "PURCHASED" in message_upper:
            action = "BUY"
        else:
            return "Could not determine buy or sell. Try: \"I sold 23 shares of SHOP at $103\""

        shares_match = re.search(r'(\d+\.?\d*)\s+share', message, re.IGNORECASE)
        shares = float(shares_match.group(1)) if shares_match else None

        skip_words = {"SOLD", "BOUGHT", "SHARES", "SHARE", "AT", "OF", "THE",
                      "BUY", "SELL", "ALL", "MY", "PURCHASED"}
        ticker = None
        for match in re.finditer(r'\b([A-Z]{2,5})\b', message_upper):
            candidate = match.group(1)
            if candidate not in skip_words:
                ticker = candidate
                break

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
                f"Portfolio history updated."
            )
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
            "I can help with your portfolio. Try:\n"
            "\"Should I sell SHOP?\"\n"
            "\"Find me a healthcare stock\"\n"
            "\"How is my portfolio doing?\"\n"
            "\"I sold 23 shares of SHOP at $103\""
        )

    else:
        from agents.portfolio_agent import run_portfolio_agent
        return run_portfolio_agent(question)
