"""
lambda_handler.py

AWS Lambda entry point.
Called by EventBridge on two schedules:
  - 7am ET daily  → morning brief
  - 4pm ET daily  → stop loss scan + score refresh
"""

import json
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def load_secrets():
    """
    Load all secrets from SSM Parameter Store.
    Sets them as environment variables so the rest of the app works unchanged.
    """
    import boto3
    ssm    = boto3.client("ssm", region_name="us-east-1")
    prefix = "/robinhood-ai/"

    params = {
        "finnhub_api_key":    "FINNHUB_API_KEY",
        "gemini_api_key":     "GEMINI_API_KEY",
        "telegram_bot_token": "TELEGRAM_BOT_TOKEN",
        "telegram_chat_id":   "TELEGRAM_CHAT_ID",
        "robinhood_username": "ROBINHOOD_USERNAME",
        "robinhood_password": "ROBINHOOD_PASSWORD",
    }

    for ssm_key, env_key in params.items():
        try:
            response = ssm.get_parameter(
                Name=f"{prefix}{ssm_key}",
                WithDecryption=True
            )
            os.environ[env_key] = response["Parameter"]["Value"]
        except Exception as e:
            logger.error(f"Could not load {ssm_key}: {e}")


def run_morning_brief():
    """Run the 7am morning brief and save snapshot to DynamoDB."""
    from notifications.morning_brief import send_morning_brief
    from infra.dynamo_store          import save_portfolio_snapshot
    from scoring.engine              import score_portfolio
    from data.robinhood_client       import robinhood_client

    logger.info("Running morning brief...")

    # Score portfolio and save to DynamoDB
    holdings    = robinhood_client.get_holdings()
    total       = robinhood_client.get_total_value()
    tickers     = [h["ticker"] for h in holdings]
    results     = score_portfolio(tickers)

    save_portfolio_snapshot(results, total)
    logger.info(f"Saved {len(results)} scores to DynamoDB")

    # Send morning brief
    send_morning_brief()
    logger.info("Morning brief sent")


def run_afternoon_scan():
    """
    Run the 4pm stop-loss scan and score refresh.
    Sends alerts for any positions that dropped 15%+ from buy price.
    """
    import requests
    from data.robinhood_client      import robinhood_client
    from data.yfinance_client       import yf_client
    from portfolio.cost_basis_store import get as get_cost
    import config

    logger.info("Running afternoon stop-loss scan...")

    holdings = robinhood_client.get_holdings()
    alerts   = []

    for h in holdings:
        ticker    = h["ticker"]
        avg_cost  = get_cost(ticker)

        if not avg_cost:
            continue

        current_price = yf_client.get_current_price(ticker)
        if not current_price:
            continue

        pct_change = ((current_price - avg_cost) / avg_cost) * 100

        if pct_change <= -15:
            alerts.append({
                "ticker":        ticker,
                "avg_cost":      avg_cost,
                "current_price": current_price,
                "pct_change":    round(pct_change, 1),
            })

    if alerts:
        msg = "⚠️ STOP-LOSS ALERTS\n\n"
        for a in alerts:
            msg += (
                f"{a['ticker']}: down {abs(a['pct_change'])}%\n"
                f"  You paid:  ${a['avg_cost']}\n"
                f"  Now:       ${a['current_price']}\n"
                f"  Run /rotate for suggestions\n\n"
            )

        url  = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text":    msg,
        }, timeout=10)

        logger.info(f"Sent {len(alerts)} stop-loss alerts")
    else:
        logger.info("No stop-loss alerts triggered")


def handle_telegram_webhook(event: dict):
    """
    Handle incoming Telegram webhook message.
    Called when user sends a message to the bot.
    """
    import json
    import requests

    body = json.loads(event.get("body", "{}"))
    message = body.get("message", {})

    if not message:
        return {"statusCode": 200, "body": "ok"}

    chat_id = str(message.get("chat", {}).get("id", ""))
    text    = message.get("text", "").strip()

    # Security — only respond to your personal chat ID
    if chat_id != os.environ.get("TELEGRAM_CHAT_ID", ""):
        logger.warning(f"Unauthorized chat_id: {chat_id}")
        return {"statusCode": 200, "body": "ok"}

    if not text:
        return {"statusCode": 200, "body": "ok"}

    logger.info(f"Webhook message: {text[:50]}")

    def send(msg: str):
        requests.post(
            f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
            json={"chat_id": chat_id, "text": msg},
            timeout=10
        )

    try:
        # Handle commands
        if text.startswith("/start") or text.startswith("/help"):
            send(
                "🤖 Robinhood AI Advisor\n\n"
                "Just ask me anything:\n"
                "\"How is NVDA doing?\"\n"
                "\"Should I sell SHOP?\"\n"
                "\"Find me a healthcare stock\"\n\n"
                "Commands:\n"
                "/score NVDA — quick score\n"
                "/portfolio  — full breakdown\n"
                "/rotate     — rotation suggestions\n"
                "/tax SHOP   — tax impact\n"
                "/status     — quick summary"
            )

        elif text.startswith("/score"):
            parts  = text.split()
            ticker = parts[1].upper() if len(parts) > 1 else ""
            if not ticker:
                send("Usage: /score NVDA")
            else:
                send(f"Scoring {ticker}...")
                from scoring.engine import score_stock
                r   = score_stock(ticker)
                msg = (
                    f"📊 {ticker} — {r['company_name']}\n\n"
                    f"Score: {r['final_score']}/10 {r['category']}\n"
                    f"F: {r['fundamental_score']}  M: {r['momentum_score']}  S: {r['sentiment_score']}\n"
                    f"Price: ${r['current_price']}\n"
                )
                if r.get("earnings_warning"):
                    msg += f"\n{r['earnings_warning']}"
                send(msg)

        elif text.startswith("/status"):
            from data.robinhood_client import robinhood_client
            total = robinhood_client.get_total_value()
            send(f"💰 Portfolio: ${total:,.0f}\n\n/portfolio — full breakdown\n/rotate — what to sell")

        elif text.startswith("/portfolio"):
            send("Reading portfolio...")
            try:
                from infra.dynamo_store import get_portfolio_snapshot
                from datetime import datetime
                today = datetime.now().strftime("%Y-%m-%d")
                items = get_portfolio_snapshot(today)
                if not items:
                    send("No data for today yet. Run morning brief first or wait until 7am.")
                else:
                    real = [i for i in items if not str(i.get("ticker","")).startswith("__")]
                    hold   = [i for i in real if i.get("category") == "HOLD"]
                    watch  = [i for i in real if i.get("category") == "WATCH"]
                    rotate = [i for i in real if i.get("category") == "ROTATE"]
                    total  = float(items[0].get("total_value", 0)) if items else 0
                    scores = [float(i["score"]) for i in real]
                    avg    = sum(scores) / len(scores) if scores else 0
                    msg    = f"📈 Portfolio (today's brief)\n\nTotal: ${total:,.0f}\nScore: {avg:.1f}/10\n\n"
                    msg   += f"✅ HOLD: {len(hold)}  👀 WATCH: {len(watch)}  🔄 ROTATE: {len(rotate)}\n"
                    if rotate:
                        msg += "\nRotate candidates:\n"
                        for r in sorted(rotate, key=lambda x: float(x["score"]))[:5]:
                            msg += f"  {r['ticker']} {float(r['score']):.1f}/10\n"
                    send(msg)
            except Exception as e:
                send(f"Could not read portfolio: {e}")
        elif text.startswith("/rotate"):
            send("Analysing... ~3 minutes")
            from portfolio.rotation_engine import run_rotation_analysis, format_suggestion
            suggestions = run_rotation_analysis()
            if not suggestions:
                send("✅ All positions within limits.")
            else:
                for s in suggestions:
                    send(format_suggestion(s))

        elif text.startswith("/tax"):
            parts  = text.split()
            ticker = parts[1].upper() if len(parts) > 1 else ""
            if not ticker:
                send("Usage: /tax SHOP")
            else:
                from portfolio.cost_basis_store import get as get_cost, calculate_tax
                from data.robinhood_client      import robinhood_client
                from data.yfinance_client       import yf_client
                avg_cost = get_cost(ticker)
                if avg_cost is None:
                    send(f"No avg cost saved for {ticker}.\nOpen Robinhood → {ticker} → Average Cost\nReply with the number (e.g. 55.22)")
                else:
                    holdings = robinhood_client.get_holdings()
                    holding  = next((h for h in holdings if h["ticker"] == ticker), None)
                    if holding:
                        price = yf_client.get_current_price(ticker)
                        tax   = calculate_tax(ticker, holding["shares"], price)
                        if tax["available"]:
                            msg  = f"💰 Tax: {ticker}\n\n"
                            msg += f"Avg cost: ${tax['avg_cost']} | Now: ${tax['current_price']}\n"
                            msg += f"Gain: ${tax['total_gain']:,.2f}\n"
                            msg += f"Short term (22%): ${tax['short_term_tax']:,.2f}\n"
                            msg += f"Long term  (15%): ${tax['long_term_tax']:,.2f}\n"
                            msg += f"Net (long term): ${tax['net_long_term']:,.2f}"
                            send(msg)

        else:
            # Natural language → supervisor agent
            send("Thinking...")
            from agents.supervisor import run_supervisor
            response = run_supervisor(text)
            send(response)

    except Exception as e:
        logger.error(f"Webhook handler error: {e}")
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            send("Gemini quota reached for today.\n\nUse commands instead:\n/portfolio\n/rotate\n/score TICKER\n/tax TICKER\n\nAI chat resumes tomorrow.")
        else:
            send("Sorry, something went wrong. Try again or use /help")

    return {"statusCode": 200, "body": "ok"}


def handler(event, context):
    """
    Main Lambda handler.

    Three trigger types:
    1. EventBridge scheduled → {"task": "morning_brief"} or {"task": "afternoon_scan"}
    2. Telegram webhook → {"body": "{...telegram message...}", "requestContext": {...}}
    3. Manual test → {"task": "morning_brief"}
    """
    logger.info(f"Lambda triggered")

    # Load secrets from SSM
    load_secrets()

    # Telegram webhook — has "body" and "requestContext" fields
    if "body" in event and "requestContext" in event:
        return handle_telegram_webhook(event)

    # EventBridge scheduled task
    task = event.get("task", "morning_brief")

    if task == "morning_brief":
        run_morning_brief()
    elif task == "afternoon_scan":
        run_afternoon_scan()
    else:
        logger.error(f"Unknown task: {task}")

    return {"statusCode": 200, "body": f"Task {task} completed"}
