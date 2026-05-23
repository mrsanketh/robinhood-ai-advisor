import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────
FINNHUB_API_KEY     = os.getenv("FINNHUB_API_KEY")
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY")
ROBINHOOD_USERNAME  = os.getenv("ROBINHOOD_USERNAME")
ROBINHOOD_PASSWORD  = os.getenv("ROBINHOOD_PASSWORD")
TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID")

# ── AWS ───────────────────────────────────────────────
AWS_REGION          = os.getenv("AWS_REGION", "us-east-1")
DYNAMODB_TABLE      = os.getenv("DYNAMODB_TABLE", "robinhood-ai-advisor")

# ── Scoring weights (must add up to 1.0) ─────────────
FUNDAMENTAL_WEIGHT  = 0.40
MOMENTUM_WEIGHT     = 0.35
SENTIMENT_WEIGHT    = 0.25

# ── Rotation rules ────────────────────────────────────
SELL_SCORE_THRESHOLD = 4.0   # suggest selling if score drops below this
BUY_SCORE_THRESHOLD  = 7.0   # only suggest buying if score is above this
STOP_LOSS_PCT        = 0.15  # alert if stock drops 15% from buy price

# ── Tax rates ─────────────────────────────────────────
SHORT_TERM_TAX_RATE  = 0.22  # held under 1 year
LONG_TERM_TAX_RATE   = 0.15  # held over 1 year
