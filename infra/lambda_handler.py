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


def handler(event, context):
    """
    Main Lambda handler.
    EventBridge passes a 'task' field to tell us which job to run.
    """
    logger.info(f"Lambda triggered: {json.dumps(event)}")

    # Load secrets from SSM
    load_secrets()

    task = event.get("task", "morning_brief")

    if task == "morning_brief":
        run_morning_brief()
    elif task == "afternoon_scan":
        run_afternoon_scan()
    else:
        logger.error(f"Unknown task: {task}")

    return {"statusCode": 200, "body": f"Task {task} completed"}
