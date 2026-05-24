"""
supervisor.py

Routes questions to the right agent using Gemini Flash.
Entry point for all conversational AI in the Telegram bot.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
import config
import logging

logger = logging.getLogger(__name__)


ROUTING_PROMPT = """Classify this question into exactly one category:

PORTFOLIO  - questions about current holdings, scores, values, allocation, tax
ROTATION   - questions about selling, rotating, trimming positions
SCREENER   - questions about buying new stocks, finding opportunities, comparing stocks
OTHER      - greetings, unclear questions

Question: {question}

Reply with only one word: PORTFOLIO, ROTATION, SCREENER, or OTHER"""


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

        if route not in ["PORTFOLIO", "ROTATION", "SCREENER", "OTHER"]:
            route = "PORTFOLIO"

        logger.info(f"Routed '{question[:50]}' → {route}")
        return route

    except Exception as e:
        logger.error(f"Routing failed: {e}")
        return "PORTFOLIO"


def run_supervisor(question: str) -> str:
    """Route question to right agent and return response."""
    route = route_question(question)

    if route == "ROTATION":
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
            "\"What is my portfolio worth?\""
        )

    else:
        from agents.portfolio_agent import run_portfolio_agent
        return run_portfolio_agent(question)
