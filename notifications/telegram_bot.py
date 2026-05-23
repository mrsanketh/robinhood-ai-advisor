import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import config
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from scoring.engine            import score_stock, score_portfolio
from data.robinhood_client     import robinhood_client
from portfolio.rotation_engine import run_rotation_analysis, format_suggestion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Security: only respond to your personal chat ID ───────────────
def is_me(update: Update) -> bool:
    return str(update.effective_chat.id) == str(config.TELEGRAM_CHAT_ID)


# ── Helper ────────────────────────────────────────────────────────
async def send(update: Update, text: str):
    await update.message.reply_text(text)


# ── /start and /help ──────────────────────────────────────────────
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_me(update): return
    await send(update,
        "🤖 Robinhood AI Advisor\n\n"
        "Commands:\n"
        "/score NVDA        — score a single stock\n"
        "/portfolio         — score all your holdings\n"
        "/rotate            — get rotation suggestions\n"
        "/status            — portfolio summary\n"
        "/help              — show this message\n\n"
        "Or just ask anything:\n"
        "\"How is NVDA doing?\"\n"
        "\"What should I sell?\"\n"
        "\"How much is my portfolio worth?\""
    )


# ── /score <TICKER> ───────────────────────────────────────────────
async def cmd_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_me(update): return

    if not context.args:
        await send(update, "Usage: /score NVDA")
        return

    ticker = context.args[0].upper()
    await send(update, f"Scoring {ticker}...")

    try:
        result = score_stock(ticker)
        msg = (
            f"📊 {ticker} — {result['company_name']}\n\n"
            f"Final score:   {result['final_score']}/10  {result['category']}\n"
            f"Fundamental:   {result['fundamental_score']}/10\n"
            f"Momentum:      {result['momentum_score']}/10\n"
            f"Sentiment:     {result['sentiment_score']}/10\n\n"
            f"Sector: {result['sector']}\n"
            f"Price:  ${result['current_price']}\n"
        )
        if result.get("earnings_warning"):
            msg += f"\n{result['earnings_warning']}"

        msg += "\n\nFundamentals:\n"
        for note in result["fundamental_notes"][:3]:
            msg += f"  → {note}\n"

        msg += "\nMomentum:\n"
        for note in result["momentum_notes"][:3]:
            msg += f"  → {note}\n"

        await send(update, msg)

    except Exception as e:
        await send(update, f"Could not score {ticker}: {e}")


# ── /portfolio ────────────────────────────────────────────────────
async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_me(update): return

    await send(update, "Reading your Robinhood portfolio... ~2 minutes")

    try:
        holdings        = robinhood_client.get_holdings()
        total           = robinhood_client.get_total_value()
        tickers         = [h["ticker"] for h in holdings]
        results         = score_portfolio(tickers)

        hold   = [r for r in results if r["category"] == "HOLD"]
        watch  = [r for r in results if r["category"] == "WATCH"]
        rotate = [r for r in results if r["category"] == "ROTATE"]

        avg_score = sum(r["final_score"] for r in results) / len(results)

        msg  = f"📈 Portfolio Summary\n\n"
        msg += f"Total value:   ${total:,.0f}\n"
        msg += f"Avg score:     {avg_score:.1f}/10\n"
        msg += f"Positions:     {len(results)}\n\n"
        msg += f"✅ HOLD:   {len(hold)}\n"
        msg += f"👀 WATCH:  {len(watch)}\n"
        msg += f"🔄 ROTATE: {len(rotate)}\n\n"

        if rotate:
            msg += "Rotate candidates:\n"
            for r in rotate:
                msg += f"  {r['ticker']} — {r['final_score']}/10\n"

        await send(update, msg)

    except Exception as e:
        await send(update, f"Error reading portfolio: {e}")


# ── /rotate ───────────────────────────────────────────────────────
async def cmd_rotate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_me(update): return

    await send(update, "Analysing rotation opportunities... ~3 minutes")

    try:
        suggestions = run_rotation_analysis()

        if not suggestions:
            await send(update, "✅ No rotations needed. Portfolio looks healthy.")
            return

        for s in suggestions:
            await send(update, format_suggestion(s))

    except Exception as e:
        await send(update, f"Rotation analysis failed: {e}")


# ── /status ───────────────────────────────────────────────────────
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_me(update): return
    try:
        total = robinhood_client.get_total_value()
        await send(update,
            f"💰 Portfolio value: ${total:,.0f}\n\n"
            f"Commands:\n"
            f"/portfolio — full score breakdown\n"
            f"/rotate    — rotation suggestions\n"
            f"/score NVDA — score one stock"
        )
    except Exception as e:
        await send(update, f"Could not get status: {e}")


# ── Plain text messages → simple responses ────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_me(update): return

    text = update.message.text.lower()

    # Simple keyword routing without LangGraph (Phase 4 adds full AI)
    if any(w in text for w in ["worth", "value", "total"]):
        await cmd_status(update, context)

    elif any(w in text for w in ["sell", "rotate", "rotation"]):
        await cmd_rotate(update, context)

    elif any(w in text for w in ["portfolio", "holdings", "positions"]):
        await cmd_portfolio(update, context)

    elif any(w in text for w in ["score", "how is", "how's"]):
        # Try to extract a ticker from the message
        words = update.message.text.upper().split()
        for word in words:
            if word.isalpha() and 2 <= len(word) <= 5 and word not in [
                "HOW", "IS", "ARE", "THE", "MY", "SCORE", "DOING", "STOCK"
            ]:
                context.args = [word]
                await cmd_score(update, context)
                return
        await send(update, "Which stock? Try: /score NVDA")

    else:
        await send(update,
            "I can help with:\n"
            "/score NVDA — score a stock\n"
            "/portfolio  — full portfolio\n"
            "/rotate     — what to sell\n"
            "/status     — quick summary"
        )


# ── Main ──────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",     cmd_help))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("score",     cmd_score))
    app.add_handler(CommandHandler("portfolio", cmd_portfolio))
    app.add_handler(CommandHandler("rotate",    cmd_rotate))
    app.add_handler(CommandHandler("status",    cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Telegram bot started. Send a message to your bot.")
    app.run_polling()


if __name__ == "__main__":
    main()
