"""
save_robinhood_token.py

Run this ONCE on your laptop (approved Robinhood device) to save
your session token to AWS SSM Parameter Store.

Lambda will use this token to read your portfolio without
needing device approval every time.

Run: python scripts/save_robinhood_token.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
import boto3
import json
import config
import robin_stocks.robinhood as rh


def find_token_file() -> str:
    """Find where robin_stocks saved the session token."""
    home      = os.path.expanduser("~")
    token_dir = os.path.join(home, ".tokens")

    candidates = [
        os.path.join(token_dir, "robinhood.pickle"),
        os.path.join(token_dir, f"{config.ROBINHOOD_USERNAME}.pickle"),
    ]

    for path in candidates:
        if os.path.exists(path):
            return path

    return None


def login_and_get_token() -> dict:
    """Login to Robinhood on this approved device and extract the token."""
    print("Logging into Robinhood...")
    print("Check your phone for device approval if prompted.")
    print()

    rh.login(
        username=config.ROBINHOOD_USERNAME,
        password=config.ROBINHOOD_PASSWORD,
        store_session=True,
    )

    print("Login successful.")

    # Find the saved token file
    token_file = find_token_file()
    if not token_file:
        # Search more broadly
        home = os.path.expanduser("~")
        for root, dirs, files in os.walk(os.path.join(home, ".tokens")):
            for f in files:
                if "robinhood" in f.lower() or config.ROBINHOOD_USERNAME in f:
                    token_file = os.path.join(root, f)
                    break

    if not token_file:
        raise FileNotFoundError(
            "Could not find robin_stocks token file. "
            "Check ~/.tokens/ directory."
        )

    print(f"Found token file: {token_file}")

    # Read the token
    with open(token_file, "rb") as f:
        token_data = pickle.load(f)

    return token_data


def save_token_to_ssm(token_data: dict):
    """Save the token to SSM Parameter Store as encrypted SecureString."""
    ssm    = boto3.client("ssm", region_name="us-east-1")
    value  = json.dumps(token_data)

    ssm.put_parameter(
        Name="/robinhood-ai/session_token",
        Value=value,
        Type="SecureString",
        Overwrite=True,
    )

    print("Token saved to SSM Parameter Store at /robinhood-ai/session_token")
    print("This token is encrypted and only accessible by your Lambda function.")


def verify_ssm_token():
    """Verify the token was saved correctly."""
    ssm = boto3.client("ssm", region_name="us-east-1")
    response = ssm.get_parameter(
        Name="/robinhood-ai/session_token",
        WithDecryption=True
    )
    token_data = json.loads(response["Parameter"]["Value"])
    print(f"Verified — token saved successfully.")
    print(f"Token keys: {list(token_data.keys())}")


if __name__ == "__main__":
    print("=" * 50)
    print("Robinhood Token Setup")
    print("=" * 50)
    print()
    print("This script will:")
    print("1. Log into Robinhood on your approved laptop")
    print("2. Extract the session token")
    print("3. Save it encrypted to AWS SSM")
    print("4. Lambda will use this token — never your password")
    print()

    try:
        token_data = login_and_get_token()
        save_token_to_ssm(token_data)
        verify_ssm_token()

        print()
        print("=" * 50)
        print("Setup complete.")
        print("Lambda can now read your Robinhood portfolio.")
        print()
        print("If this stops working in a few months:")
        print("  Run this script again to refresh the token.")
        print("=" * 50)

    except Exception as e:
        print(f"Error: {e}")
        print()
        print("Common fixes:")
        print("  1. Make sure you are on your approved laptop")
        print("  2. Check your .env has correct ROBINHOOD_USERNAME and PASSWORD")
        print("  3. Approve the device on your Robinhood phone app if prompted")
        sys.exit(1)
