"""
cost_monitor.py

Checks AWS costs and API usage weekly.
Appended to Monday morning brief only.
"""

import boto3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_aws_cost() -> dict:
    """Get AWS cost for current month using Cost Explorer."""
    try:
        client = boto3.client("ce", region_name="us-east-1")
        today  = datetime.now()
        start  = today.replace(day=1).strftime("%Y-%m-%d")
        end    = today.strftime("%Y-%m-%d")

        response = client.get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
        )
        amount = float(
            response["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"]
        )
        return {"available": True, "amount": round(amount, 4), "period": f"{start} to {end}"}
    except Exception as e:
        logger.warning(f"Could not get AWS cost: {e}")
        return {"available": False, "amount": 0, "period": "unavailable"}


def get_lambda_invocations() -> dict:
    """Get Lambda invocation count for this month."""
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
        return {"count": count, "limit": 1000000}
    except Exception as e:
        logger.warning(f"Could not get Lambda invocations: {e}")
        return {"count": 0, "limit": 1000000}


def get_dynamo_usage() -> dict:
    """Get DynamoDB table item counts."""
    try:
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        portfolio_count = dynamodb.Table("robinhood-ai-portfolio").item_count
        costbasis_count = dynamodb.Table("robinhood-ai-costbasis").item_count
        return {"portfolio_rows": portfolio_count, "costbasis_rows": costbasis_count}
    except Exception as e:
        logger.warning(f"Could not get DynamoDB usage: {e}")
        return {"portfolio_rows": 0, "costbasis_rows": 0}


def build_cost_section() -> str:
    """Build cost summary section for Monday morning brief."""
    aws_cost   = get_aws_cost()
    lambda_inv = get_lambda_invocations()
    dynamo     = get_dynamo_usage()

    lines = []
    lines.append("")
    lines.append("💸 <b>Weekly Cost Check</b>")

    if aws_cost["available"]:
        if aws_cost["amount"] == 0:
            lines.append(f"  AWS this month:    $0.00  ✅")
        elif aws_cost["amount"] < 1.0:
            lines.append(f"  AWS this month:    ${aws_cost['amount']:.4f}  ✅ negligible")
        else:
            lines.append(f"  AWS this month:    ${aws_cost['amount']:.2f}  ⚠️ check console")
    else:
        lines.append(f"  AWS cost:          unavailable")

    pct = round((lambda_inv["count"] / lambda_inv["limit"]) * 100, 3)
    lines.append(f"  Lambda calls:      {lambda_inv['count']:,} / 1,000,000  ({pct}% of free tier)")
    lines.append(f"  DynamoDB rows:     {dynamo['portfolio_rows']} portfolio + {dynamo['costbasis_rows']} cost basis")
    lines.append(f"  yfinance:          free ✅")
    lines.append(f"  Finnhub:           free ✅")
    lines.append(f"  Telegram:          free ✅")

    return "\n".join(lines)


def is_monday() -> bool:
    return datetime.now().weekday() == 0
