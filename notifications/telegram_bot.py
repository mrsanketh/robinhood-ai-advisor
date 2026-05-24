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
from scoring.engine             import score_stock, score_portfolio
from data.robinhood_client      import robinhood_client
from data.yfinance_client       import yf_client
from portfolio.rotation_engine  import run_rotation_analysis, format_suggestion
from portfolio.cost_basis_store import get as get_cost, save as save_cost, calculate_tax

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def is_me(update: Update) -> bool:
    return str(update.effective_chat.id) == str(config.TELEGRAM_CHAT_ID)


async def send(update: Update, text: str):
    await update.message.reply_text(text)


# ── /help ─────────────────────────────────────────────────────────
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_me(update): return
    await send(update,
        "🤖 Robinhood AI Advisor\n\n"
        "Just ask me anything naturally:\n"
        "\"How is NVDA doing?\"\n"
        "\"Should I sell SHOP?\"\n"
        "\"Find me a healthcare stock\"\n"
        "\"What is my portfolio worth?\"\n"
        "\"How much tax if I sell NFLX?\"\n\n"
        "Commands:\n"
        "/score NVDA   — quick score\n"
        "/portfolio    — full breakdown\n"
        "/rotate       — rotation suggestions\n"
        "/tax SHOP     — tax impact\n"
        "/status       — quick summary\n"
        "/help         — this message"
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
            f"Final score:  {result['final_score']}/10  {result['category']}\n"
            f"Fundamental:  {result['fundamental_score']}/10\n"
            f"Momentum:     {result['momentum_score']}/10\n"
            f"Sentiment:    {result['sentiment_score']}/10\n\n"
            f"Sector: {result['sector']}\n"
            f"Price:  ${result['current_price']}\n"
        )
        if result.get("earnings_warning"):
            msg += f"\n{result['earnings_warning']}\n"
        msg += "\nFundamentals:\n"
        for note in result["fundamental_notes"][:3]:
            msg += f"  → {note}\n"
        msg += "\nMomentum:\n"
        for note in result["momentum_notes"][:3]:
            msg += f"  → {note}\n"
        await send(update, msg)
    except Exception as e:
        await send(update, f"Could not score {ticker}: {e}")


# ── /status ───────────────────────────────────────────────────────
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_me(update): return
    try:
        total = robinhood_client.get_total_value()
        await send(update, f"💰 Portfolio: ${total:,.0f}\n\n/portfolio — full breakdown\n/rotate — what to sell\n/score NVDA — score one stock")
    except Exception as e:
        await send(update, f"Error: {e}")


# ── /portfolio ────────────────────────────────────────────────────
async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_me(update): return
    await send(update, "Reading portfolio... ~2 minutes")
    try:
        holdings = robinhood_client.get_holdings()
        total    = robinhood_client.get_total_value()
        tickers  = [h["ticker"] for h in holdings]
        results  = score_portfolio(tickers)
        hold     = [r for r in results if r["category"] == "HOLD"]
        watch    = [r for r in results if r["category"] == "WATCH"]
        rotate   = [r for r in results if r["category"] == "ROTATE"]
        avg      = sum(r["final_score"] for r in results) / len(results)
        msg  = f"📈 Portfolio Summary\n\nTotal:    ${total:,.0f}\nScore:    {avg:.1f}/10\nStocks:   {len(results)}\n\n✅ HOLD:   {len(hold)}\n👀 WATCH:  {len(watch)}\n🔄 ROTATE: {len(rotate)}\n"
        if rotate:
            msg += "\nRotate candidates:\n"
            for r in rotate:
                msg += f"  {r['ticker']} {r['final_score']}/10\n"
        earnings = [r for r in results if r.get("earnings_warning")]
        if earnings:
            msg += "\n⚠️ Earnings soon:\n"
            for r in earnings:
                msg += f"  {r['ticker']} — {r['earnings_warning']}\n"
        await send(update, msg)
    except Exception as e:
        await send(update, f"Error: {e}")


# ── /tax <TICKER> ─────────────────────────────────────────────────
async def cmd_tax(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_me(update): return
    if not context.args:
        await send(update, "Usage: /tax SHOP")
        return
    ticker   = context.args[0].upper()
    avg_cost = get_cost(ticker)
    if avg_cost is None:
        context.user_data["tax_ticker"] = ticker
        await send(update, f"I don't have your avg cost for {ticker} yet.\n\nOpen Robinhood → {ticker} → Average Cost\nReply with the number (e.g. 55.22)")
        return
    holdings = robinhood_client.get_holdings()
    holding  = next((h for h in holdings if h["ticker"] == ticker), None)
    if not holding:
        await send(update, f"{ticker} not found in your portfolio.")
        return
    current_price = yf_client.get_current_price(ticker)
    tax = calculate_tax(ticker, holding["shares"], current_price)
    if not tax["available"]:
        await send(update, tax["message"])
        return
    gain_label = "GAIN" if tax["total_gain"] >= 0 else "LOSS"
    msg  = f"💰 Tax impact: {ticker}\n\nYour avg cost:    ${tax['avg_cost']}\nCurrent price:    ${tax['current_price']}\nShares:           {tax['shares']}\nGain per share:   ${tax['gain_per_share']}\nTotal {gain_label}:      ${abs(tax['total_gain']):,.2f}\n\n"
    if tax["total_gain"] >= 0:
        msg += f"Short term (22%): ${tax['short_term_tax']:,.2f}\nLong term  (15%): ${tax['long_term_tax']:,.2f}\n\nProceeds:         ${tax['proceeds']:,.2f}\nNet (short term): ${tax['net_short_term']:,.2f}\nNet (long term):  ${tax['net_long_term']:,.2f}\n"
    else:
        msg += f"Tax loss harvest: saves ${abs(tax['short_term_tax']):,.2f}\n(offsets other gains this year)\n\nProceeds: ${tax['proceeds']:,.2f}\n"
    msg += f"\n⚠️ Verify in Robinhood Tax Center before trading"
    await send(update, msg)


# ── /rotate ───────────────────────────────────────────────────────
async def cmd_rotate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_me(update): return
    await send(update, "Analysing portfolio... ~3 minutes")
    try:
        suggestions = run_rotation_analysis()
        if not suggestions:
            await send(update, "✅ All positions within limits. Portfolio looks healthy.")
            return
        await send(update,
            "📐 Position sizing limits:\n"
            "Score 8-10 → max 12%\nScore 7-8  → max 8%\n"
            "Score 6-7  → max 5%\nScore 5-6  → max 3%\n"
            "Score 4-5  → max 1%\nScore 0-4  → exit\n\n"
            "Only showing trades freeing $1,000+"
        )
        for s in suggestions:
            await send(update, format_suggestion(s))
    except Exception as e:
        await send(update, f"Rotation analysis failed: {e}")


# ── Natural language — routes through supervisor agent ────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_me(update): return

    text = update.message.text.strip()

    # Cost basis reply
    if "tax_ticker" in context.user_data:
        ticker = context.user_data.pop("tax_ticker")
        try:
            cost = float(text.replace("$", "").replace(",", ""))
            save_cost(ticker, cost)
            await send(update, f"✅ Saved: {ticker} avg cost = ${cost}\n\nRun /tax {ticker} to see full tax impact.")
        except ValueError:
            await send(update, "Please enter a number e.g. 55.22")
        return

    # Route through AI supervisor agent
    await send(update, "Thinking...")
    try:
        from agents.supervisor import run_supervisor
        response = run_supervisor(text)
        await send(update, response)
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        await send(update,
            "Sorry, I had trouble with that. Try:\n"
            "/score NVDA\n/portfolio\n/rotate\n/status"
        )


# ── Main ──────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",     cmd_help))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("score",     cmd_score))
    app.add_handler(CommandHandler("portfolio", cmd_portfolio))
    app.add_handler(CommandHandler("rotate",    cmd_rotate))
    app.add_handler(CommandHandler("tax",       cmd_tax))
    app.add_handler(CommandHandler("status",    cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Bot started. Send a message to your bot.")
    app.run_polling()


if __name__ == "__main__":
    main()
