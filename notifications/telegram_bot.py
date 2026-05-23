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
    ConversationHandler,
    ContextTypes,
    filters,
)
from scoring.engine            import score_stock, score_portfolio
from data.robinhood_client     import robinhood_client
from portfolio.rotation_engine import run_rotation_analysis
from portfolio.cost_basis_store import get as get_cost, save as save_cost, calculate_tax

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_COST = 1


def is_me(update: Update) -> bool:
    return str(update.effective_chat.id) == str(config.TELEGRAM_CHAT_ID)


async def send(update: Update, text: str):
    await update.message.reply_text(text)


# ── /help ─────────────────────────────────────────────────────────
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_me(update): return
    await send(update,
        "🤖 Robinhood AI Advisor\n\n"
        "Commands:\n"
        "/score NVDA   — score a stock\n"
        "/portfolio    — score all holdings\n"
        "/rotate       — rotation suggestions\n"
        "/tax SHOP     — tax impact if you sell\n"
        "/status       — quick summary\n"
        "/help         — this message\n\n"
        "Or just ask:\n"
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
        await send(update,
            f"💰 Portfolio: ${total:,.0f}\n\n"
            f"/portfolio — full breakdown\n"
            f"/rotate    — what to sell\n"
            f"/score NVDA — score one stock"
        )
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

        hold   = [r for r in results if r["category"] == "HOLD"]
        watch  = [r for r in results if r["category"] == "WATCH"]
        rotate = [r for r in results if r["category"] == "ROTATE"]
        avg    = sum(r["final_score"] for r in results) / len(results)

        msg  = f"📈 Portfolio Summary\n\n"
        msg += f"Total:    ${total:,.0f}\n"
        msg += f"Score:    {avg:.1f}/10\n"
        msg += f"Stocks:   {len(results)}\n\n"
        msg += f"✅ HOLD:   {len(hold)}\n"
        msg += f"👀 WATCH:  {len(watch)}\n"
        msg += f"🔄 ROTATE: {len(rotate)}\n"

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

    ticker = context.args[0].upper()

    # Check if cost basis is saved
    avg_cost = get_cost(ticker)
    if avg_cost is None:
        # Ask user to enter it
        context.user_data["tax_ticker"] = ticker
        await send(update,
            f"I don't have your avg cost for {ticker} yet.\n\n"
            f"Open Robinhood → {ticker} → Average Cost\n"
            f"Reply with the number (e.g. 55.22)"
        )
        return ConversationHandler.END  # handled by message handler

    # Calculate tax using saved cost
    holdings = robinhood_client.get_holdings()
    holding  = next((h for h in holdings if h["ticker"] == ticker), None)

    if not holding:
        await send(update, f"{ticker} not found in your portfolio.")
        return

    from data.yfinance_client import yf_client
    current_price = yf_client.get_current_price(ticker)
    tax = calculate_tax(ticker, holding["shares"], current_price)

    if not tax["available"]:
        await send(update, tax["message"])
        return

    msg  = f"💰 Tax impact: {ticker}\n\n"
    msg += f"Your avg cost:    ${tax['avg_cost']}\n"
    msg += f"Current price:    ${tax['current_price']}\n"
    msg += f"Shares:           {tax['shares']}\n"
    msg += f"Gain per share:   ${tax['gain_per_share']}\n"
    msg += f"Total gain:       ${tax['total_gain']:,.2f}\n\n"
    msg += f"Short term (22%): ${tax['short_term_tax']:,.2f}\n"
    msg += f"Long term  (15%): ${tax['long_term_tax']:,.2f}\n\n"
    msg += f"Proceeds:         ${tax['proceeds']:,.2f}\n"
    msg += f"Net (short term): ${tax['net_short_term']:,.2f}\n"
    msg += f"Net (long term):  ${tax['net_long_term']:,.2f}\n\n"
    msg += f"⚠️ Verify in Robinhood Tax Center before trading"

    await send(update, msg)


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
            sell_ticker = s["sell"]["ticker"]
            tickers     = [t.strip() for t in sell_ticker.split("+")]

            msg = f"🔄 ROTATION SUGGESTION\n\n"

            if s.get("combined"):
                msg += f"SELL (combined): {sell_ticker}\n"
                msg += f"Value: ${s['sell']['equity']:,.2f}\n"
            else:
                msg += f"SELL: {sell_ticker}\n"
                msg += f"Score:  {s['sell']['score']}/10\n"
                msg += f"Shares: {s['sell']['shares']}\n"
                msg += f"Value:  ${s['sell']['equity']:,.2f}\n"
                for note in s["sell"].get("notes", [])[:3]:
                    msg += f"  → {note}\n"

            # Show tax if available
            for t in tickers:
                t = t.strip()
                avg_cost = get_cost(t)
                if avg_cost:
                    from data.yfinance_client import yf_client
                    price = yf_client.get_current_price(t)
                    holdings = robinhood_client.get_holdings()
                    h = next((x for x in holdings if x["ticker"] == t), None)
                    if h:
                        tax = calculate_tax(t, h["shares"], price)
                        if tax["available"]:
                            msg += f"\nTax impact {t}:\n"
                            msg += f"  Gain: ${tax['total_gain']:,.2f}\n"
                            msg += f"  Short term: ${tax['short_term_tax']:,.2f}\n"
                            msg += f"  Long term:  ${tax['long_term_tax']:,.2f}\n"
                else:
                    msg += f"\n💡 Run /tax {t} for tax impact"

            if s.get("buy"):
                buy = s["buy"]
                msg += f"\nBUY: {buy['ticker']} — {buy['company_name']}\n"
                msg += f"Score:  {buy['score']}/10\n"
                msg += f"Price:  ${buy['price']}\n"
                msg += f"Shares: {buy['shares']}\n"
                msg += f"Cost:   ${buy['cost']:,.2f}\n"
                for note in buy.get("notes", [])[:2]:
                    msg += f"  → {note}\n"
            else:
                msg += f"\n{s.get('message', 'Hold cash')}\n"

            await send(update, msg)

    except Exception as e:
        await send(update, f"Rotation analysis failed: {e}")


# ── Handle cost basis replies ─────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_me(update): return

    text = update.message.text.strip()

    # Check if we are waiting for a cost basis entry
    if "tax_ticker" in context.user_data:
        ticker = context.user_data.pop("tax_ticker")
        try:
            cost = float(text.replace("$", "").replace(",", ""))
            save_cost(ticker, cost)
            await send(update,
                f"✅ Saved: {ticker} avg cost = ${cost}\n\n"
                f"Run /tax {ticker} to see full tax impact."
            )
        except ValueError:
            await send(update, "Please enter a number e.g. 55.22")
        return

    # Simple keyword routing
    lower = text.lower()
    if any(w in lower for w in ["worth", "value", "total"]):
        await cmd_status(update, context)
    elif any(w in lower for w in ["sell", "rotate", "rotation"]):
        await cmd_rotate(update, context)
    elif any(w in lower for w in ["portfolio", "holdings", "positions"]):
        await cmd_portfolio(update, context)
    elif any(w in lower for w in ["score", "how is", "how's"]):
        words = text.upper().split()
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
            "/tax SHOP   — tax impact\n"
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
    app.add_handler(CommandHandler("tax",       cmd_tax))
    app.add_handler(CommandHandler("status",    cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot started. Open Telegram and send a message.")
    app.run_polling()


if __name__ == "__main__":
    main()
