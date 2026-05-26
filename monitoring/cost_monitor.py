"""
cost_monitor.py

Two modes:
1. Weekly summary (Mondays) — full cost breakdown
2. Daily threshold check — immediate alert if anything exceeds limit

Gemini usage is tracked via DynamoDB call counter since
Google does not expose a usage API on free tier.
"""

import boto3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Alert thresholds
AWS_COST_ALERT_USD      = 1.00    # alert if AWS charges exceed $1
GEMINI_CALLS_ALERT_PCT  = 0.80    # alert if Gemini usage exceeds 80% of daily limit
GEMINI_DAILY_LIMIT      = 1500    # free tier requests/day
LAMBDA_ALERT_PCT        = 0.80    # alert if Lambda exceeds 80% of free tier


def get_aws_cost() -> dict:
    """Get AWS cost — daily and monthly using Cost Explorer."""
    try:
        client = boto3.client("ce", region_name="us-east-1")
        today  = datetime.now()

        # Monthly cost
        month_start = today.replace(day=1).strftime("%Y-%m-%d")
        end         = today.strftime("%Y-%m-%d")

        # Daily cost (yesterday — today may not be complete yet)
        from datetime import timedelta
        yesterday    = (today - timedelta(days=1)).strftime("%Y-%m-%d")

        monthly = client.get_cost_and_usage(
            TimePeriod={"Start": month_start, "End": end},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
        )
        daily = client.get_cost_and_usage(
            TimePeriod={"Start": yesterday, "End": end},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
        )

        monthly_amount = float(monthly["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"])
        daily_amount   = float(daily["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"]) if daily["ResultsByTime"] else 0

        return {
            "available":      True,
            "monthly":        round(monthly_amount, 4),
            "daily":          round(daily_amount, 4),
        }
    except Exception as e:
        logger.warning(f"Could not get AWS cost: {e}")
        return {"available": False, "monthly": 0, "daily": 0}


def get_lambda_invocations() -> dict:
    """Get Lambda invocation count for this month from CloudWatch."""
    try:
        client = boto3.client("cloudwatch", region_name="us-east-1")
        today  = datetime.now()
        start  = today.replace(day=1)
        response = client.get_metric_statistics(
            Namespace="AWS/Lambda",
            MetricName="Invocations",
            Dimensions=[{"Name": "FunctionName", "Value": "robinhood-ai-morning-brief"}],
            StartTime=start,
            EndTime=today,
            Period=2592000,
            Statistics=["Sum"],
        )
        count = int(response["Datapoints"][0]["Sum"]) if response["Datapoints"] else 0
        return {"count": count, "limit": 1000000, "pct": round(count / 1000000 * 100, 3)}
    except Exception as e:
        logger.warning(f"Could not get Lambda invocations: {e}")
        return {"count": 0, "limit": 1000000, "pct": 0}


def get_gemini_usage() -> dict:
    """
    Get Gemini API call count from DynamoDB counter.
    We track this ourselves since Google has no usage API on free tier.
    """
    try:
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table    = dynamodb.Table("robinhood-ai-portfolio")

        today    = datetime.now().strftime("%Y-%m-%d")
        response = table.get_item(Key={"date": today, "ticker": "__gemini_calls__"})

        calls_today = int(response["Item"]["score"]) if "Item" in response else 0
        pct         = round(calls_today / GEMINI_DAILY_LIMIT * 100, 1)

        return {
            "calls_today": calls_today,
            "daily_limit": GEMINI_DAILY_LIMIT,
            "pct":         pct,
        }
    except Exception as e:
        logger.warning(f"Could not get Gemini usage: {e}")
        return {"calls_today": 0, "daily_limit": GEMINI_DAILY_LIMIT, "pct": 0}


def increment_gemini_counter():
    """
    Call this every time we make a Gemini API call.
    Increments the daily counter in DynamoDB.
    """
    try:
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table    = dynamodb.Table("robinhood-ai-portfolio")
        today    = datetime.now().strftime("%Y-%m-%d")

        table.update_item(
            Key={"date": today, "ticker": "__gemini_calls__"},
            UpdateExpression="ADD score :inc",
            ExpressionAttributeValues={":inc": 1},
        )
    except Exception as e:
        logger.warning(f"Could not increment Gemini counter: {e}")


def check_thresholds() -> list:
    """
    Check all cost thresholds.
    Returns list of alert messages if any threshold is exceeded.
    Call this daily from the morning brief.
    """
    alerts = []

    # AWS cost check
    aws = get_aws_cost()
    if aws["available"] and aws.get("daily", aws.get("amount", 0)) >= AWS_COST_ALERT_USD:
        alerts.append({
            "type":    "AWS_COST",
            "message": f"⚠️ AWS charges detected: ${aws.get('daily', 0):.4f} yesterday / ${aws.get('monthly', 0):.4f} this month",
            "next_steps": (
                "Next steps:\n"
                "  1. Go to AWS Console → Cost Explorer\n"
                "  2. Check which service is charging\n"
                "  3. Common cause: Lambda timeout or DynamoDB scan\n"
                "  4. Message /status to check if Lambda is stuck"
            )
        })

    # Gemini usage check
    gemini = get_gemini_usage()
    if gemini["pct"] >= GEMINI_CALLS_ALERT_PCT * 100:
        alerts.append({
            "type":    "GEMINI_QUOTA",
            "message": f"⚠️ Gemini API at {gemini['pct']}% of daily limit ({gemini['calls_today']}/{gemini['daily_limit']} calls)",
            "next_steps": (
                "Next steps:\n"
                "  1. Quota resets at midnight — avoid heavy use today\n"
                "  2. Avoid running /rotate or /portfolio multiple times\n"
                "  3. Morning brief will still run — it uses fewer calls\n"
                "  4. If this happens often → add billing to Google AI Studio\n"
                "     (first $10/month is covered by free credits)"
            )
        })

    # Lambda usage check
    lam = get_lambda_invocations()
    if lam["pct"] >= LAMBDA_ALERT_PCT * 100:
        alerts.append({
            "type":    "LAMBDA_QUOTA",
            "message": f"⚠️ Lambda at {lam['pct']}% of free tier ({lam['count']:,}/1,000,000 calls)",
            "next_steps": (
                "Next steps:\n"
                "  1. This is very unusual — Lambda limit is 1M calls/month\n"
                "  2. Check if something is triggering Lambda in a loop\n"
                "  3. Go to AWS Console → Lambda → Monitor tab\n"
                "  4. Check CloudWatch logs for errors"
            )
        })

    return alerts


def build_cost_section() -> str:
    """Build weekly cost summary for Monday morning brief."""
    aws    = get_aws_cost()
    lam    = get_lambda_invocations()
    gemini = get_gemini_usage()
    dynamo = _get_dynamo_usage()

    lines = []
    lines.append("")
    lines.append("💸 <b>Weekly Cost Check</b>")

    # AWS cost — daily and monthly
    if aws["available"]:
        daily_status   = "✅" if aws["daily"] < AWS_COST_ALERT_USD else "⚠️ check console"
        monthly_status = "✅" if aws["monthly"] < AWS_COST_ALERT_USD else "⚠️ check console"
        lines.append(f"  AWS yesterday:     ${aws['daily']:.4f}  {daily_status}")
        lines.append(f"  AWS this month:    ${aws['monthly']:.4f}  {monthly_status}")
    else:
        lines.append(f"  AWS cost:          unavailable (enable Cost Explorer)")

    # Lambda
    lambda_status = "✅" if lam["pct"] < 80 else "⚠️ high"
    lines.append(f"  Lambda:  {lam['count']:,} / 1,000,000 per month  ({lam['pct']}%) {lambda_status}")

    # Gemini
    gemini_status = "✅" if gemini["pct"] < 80 else "⚠️ approaching limit"
    lines.append(f"  Gemini:  {gemini['calls_today']} / {gemini['daily_limit']} per day  ({gemini['pct']}%) {gemini_status}")

    # DynamoDB
    lines.append(f"  DynamoDB: {dynamo['portfolio']} rows / 25,000,000,000 (25GB free) ✅")

    # External APIs
    lines.append(f"")
    lines.append(f"  Finnhub:   60 calls/min — free ✅")
    lines.append(f"  yfinance:  unlimited — free ✅")
    lines.append(f"  Telegram:  unlimited — free ✅")

    return "\n".join(lines)


def _get_dynamo_usage() -> dict:
    """Get DynamoDB row counts."""
    try:
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        return {
            "portfolio": dynamodb.Table("robinhood-ai-portfolio").item_count,
            "costbasis": dynamodb.Table("robinhood-ai-costbasis").item_count,
        }
    except Exception:
        return {"portfolio": 0, "costbasis": 0}


def is_monday() -> bool:
    return datetime.now().weekday() == 0
