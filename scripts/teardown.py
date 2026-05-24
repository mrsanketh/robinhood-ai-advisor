"""
teardown.py

Cleanly removes all AWS resources created by this app.
Sends a backup of your cost basis to Telegram before deleting.

Run: python scripts/teardown.py
Requires confirmation before deleting anything.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import boto3
import json
import requests
import config


def send_telegram(msg: str):
    """Send a message to your Telegram."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": msg},
            timeout=10
        )
    except Exception as e:
        print(f"Telegram send failed: {e}")


def backup_cost_basis() -> str:
    """Export cost basis from DynamoDB as JSON string."""
    try:
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table    = dynamodb.Table("robinhood-ai-costbasis")
        response = table.scan()
        items    = response.get("Items", [])

        backup = {}
        for item in items:
            ticker   = item.get("ticker", "")
            avg_cost = float(item.get("avg_cost", 0))
            if ticker and avg_cost:
                backup[ticker] = avg_cost

        return json.dumps(backup, indent=2)
    except Exception as e:
        return f"Could not backup cost basis: {e}"


def delete_eventbridge_rules():
    """Delete EventBridge rules and targets."""
    client = boto3.client("events", region_name="us-east-1")
    rules  = ["robinhood-ai-morning-brief", "robinhood-ai-afternoon-scan"]

    for rule in rules:
        try:
            # Remove targets first
            targets = client.list_targets_by_rule(Rule=rule)
            ids     = [t["Id"] for t in targets.get("Targets", [])]
            if ids:
                client.remove_targets(Rule=rule, Ids=ids)
                print(f"  Removed targets from {rule}")

            # Delete rule
            client.delete_rule(Name=rule)
            print(f"  Deleted EventBridge rule: {rule}")
        except Exception as e:
            print(f"  Could not delete {rule}: {e}")


def delete_lambda():
    """Delete Lambda function and function URL."""
    client = boto3.client("lambda", region_name="us-east-1")
    try:
        client.delete_function_url_config(FunctionName="robinhood-ai-morning-brief")
        print("  Deleted Lambda function URL")
    except Exception as e:
        print(f"  Function URL not found: {e}")

    try:
        client.delete_function(FunctionName="robinhood-ai-morning-brief")
        print("  Deleted Lambda function: robinhood-ai-morning-brief")
    except Exception as e:
        print(f"  Could not delete Lambda: {e}")


def delete_lambda_layer():
    """Delete the pandas Lambda layer."""
    client = boto3.client("lambda", region_name="us-east-1")
    try:
        versions = client.list_layer_versions(LayerName="robinhood-ai-pandas")
        for v in versions.get("LayerVersions", []):
            client.delete_layer_version(
                LayerName="robinhood-ai-pandas",
                VersionNumber=v["Version"]
            )
            print(f"  Deleted Lambda layer: robinhood-ai-pandas v{v['Version']}")
    except Exception as e:
        print(f"  Could not delete Lambda layer: {e}")


def delete_dynamodb_tables():
    """Delete DynamoDB tables."""
    client = boto3.client("dynamodb", region_name="us-east-1")
    tables = ["robinhood-ai-portfolio", "robinhood-ai-costbasis"]

    for table in tables:
        try:
            client.delete_table(TableName=table)
            print(f"  Deleted DynamoDB table: {table}")
        except Exception as e:
            print(f"  Could not delete {table}: {e}")


def delete_ssm_parameters():
    """Delete all SSM parameters."""
    client = boto3.client("ssm", region_name="us-east-1")
    params = [
        "/robinhood-ai/finnhub_api_key",
        "/robinhood-ai/gemini_api_key",
        "/robinhood-ai/telegram_bot_token",
        "/robinhood-ai/telegram_chat_id",
        "/robinhood-ai/robinhood_username",
        "/robinhood-ai/robinhood_password",
        "/robinhood-ai/session_token",
        "/robinhood-ai/gemini_model",
    ]

    for param in params:
        try:
            client.delete_parameter(Name=param)
            print(f"  Deleted SSM parameter: {param}")
        except Exception as e:
            print(f"  Could not delete {param}: {e}")


def delete_iam_role():
    """Delete Lambda IAM role."""
    client   = boto3.client("iam", region_name="us-east-1")
    role     = "robinhood-ai-lambda-role"
    policies = [
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess",
        "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess",
        "arn:aws:iam::aws:policy/AWSBillingReadOnlyAccess",
    ]

    for policy in policies:
        try:
            client.detach_role_policy(RoleName=role, PolicyArn=policy)
        except Exception:
            pass

    try:
        client.delete_role(RoleName=role)
        print(f"  Deleted IAM role: {role}")
    except Exception as e:
        print(f"  Could not delete IAM role: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("Robinhood AI Advisor — Teardown")
    print("=" * 50)
    print()
    print("This will DELETE all AWS resources:")
    print("  - EventBridge rules (7am + 4pm schedules)")
    print("  - Lambda function")
    print("  - Lambda layer (pandas)")
    print("  - DynamoDB tables (portfolio history + cost basis)")
    print("  - SSM parameters (all API keys)")
    print("  - IAM role")
    print()
    print("Your cost basis will be backed up to Telegram first.")
    print()

    confirm = input("Type YES to confirm teardown: ").strip()
    if confirm != "YES":
        print("Cancelled.")
        sys.exit(0)

    print()
    print("Step 1 — Backing up cost basis to Telegram...")
    backup = backup_cost_basis()
    send_telegram(
        f"💾 Cost basis backup before teardown:\n\n{backup}\n\n"
        f"Save this — you will need it if you redeploy."
    )
    print("  Backup sent to Telegram.")

    print()
    print("Step 2 — Deleting EventBridge rules...")
    delete_eventbridge_rules()

    print()
    print("Step 3 — Deleting Lambda function...")
    delete_lambda()

    print()
    print("Step 4 — Deleting Lambda layer...")
    delete_lambda_layer()

    print()
    print("Step 5 — Deleting DynamoDB tables...")
    delete_dynamodb_tables()

    print()
    print("Step 6 — Deleting SSM parameters...")
    delete_ssm_parameters()

    print()
    print("Step 7 — Deleting IAM role...")
    delete_iam_role()

    print()
    print("=" * 50)
    print("Teardown complete.")
    print()
    print("All AWS resources deleted.")
    print("Your code is still on GitHub.")
    print("To redeploy: follow setup instructions in README.")
    print("=" * 50)

    send_telegram("✅ Teardown complete. All AWS resources deleted.")
