import robin_stocks.robinhood as rh
import config
import logging
import os

logger = logging.getLogger(__name__)


def _is_lambda() -> bool:
    """Check if we are running inside AWS Lambda."""
    return os.path.exists("/var/task")


def _load_token_from_ssm() -> dict:
    """Load session token from SSM Parameter Store."""
    import boto3
    import json
    ssm      = boto3.client("ssm", region_name="us-east-1")
    response = ssm.get_parameter(
        Name="/robinhood-ai/session_token",
        WithDecryption=True
    )
    return json.loads(response["Parameter"]["Value"])


def _save_token_to_ssm(token_data: dict):
    """Save refreshed session token back to SSM."""
    import boto3
    import json
    import pickle
    import tempfile

    ssm = boto3.client("ssm", region_name="us-east-1")
    ssm.put_parameter(
        Name="/robinhood-ai/session_token",
        Value=json.dumps(token_data),
        Type="SecureString",
        Overwrite=True,
    )


class RobinhoodClient:
    """
    Reads your real Robinhood portfolio.

    On laptop: logs in normally using credentials from .env
    On Lambda: uses session token from SSM Parameter Store
               token never stored in code or files
    """

    def __init__(self):
        self._logged_in = False

    def login(self):
        """Login to Robinhood — uses SSM token on Lambda, credentials locally."""
        if self._logged_in:
            return

        if _is_lambda():
            self._login_with_token()
        else:
            self._login_with_credentials()

    def _login_with_token(self):
        """Lambda login — uses session token from SSM, no device approval needed."""
        try:
            import pickle
            import tempfile

            os.environ["HOME"] = "/tmp"

            token_data = _load_token_from_ssm()

            # Write token to /tmp so robin_stocks can find it
            token_dir  = "/tmp/.tokens"
            os.makedirs(token_dir, exist_ok=True)
            token_file = os.path.join(token_dir, "robinhood.pickle")

            with open(token_file, "wb") as f:
                pickle.dump(token_data, f)

            # Login using stored token
            rh.login(
                username=config.ROBINHOOD_USERNAME,
                password=config.ROBINHOOD_PASSWORD,
                store_session=True,
                pickle_path=token_file,
            )

            self._logged_in = True
            logger.info("Logged into Robinhood using SSM token")

        except Exception as e:
            logger.error(f"Token login failed: {e}")
            raise RuntimeError(
                f"Robinhood token login failed: {e}\n"
                "Run: python scripts/save_robinhood_token.py on your laptop"
            )

    def _login_with_credentials(self):
        """Local login — uses credentials from .env, requires device approval once."""
        try:
            rh.login(
                username=config.ROBINHOOD_USERNAME,
                password=config.ROBINHOOD_PASSWORD,
                store_session=True,
            )
            self._logged_in = True
            logger.info("Logged into Robinhood using credentials")
        except Exception as e:
            logger.error(f"Robinhood login failed: {e}")
            raise

    def get_holdings(self) -> list:
        """Read all your stock positions."""
        self.login()
        try:
            positions = rh.get_open_stock_positions()
            holdings  = []

            for position in positions:
                ticker = rh.get_instrument_by_url(
                    position["instrument"]
                ).get("symbol", "")

                if not ticker:
                    continue

                shares   = float(position.get("quantity", 0))
                avg_cost = float(position.get("average_buy_price", 0))
                equity   = shares * avg_cost

                holdings.append({
                    "ticker":   ticker,
                    "shares":   round(shares, 4),
                    "avg_cost": round(avg_cost, 2),
                    "equity":   round(equity, 2),
                })

            return holdings

        except Exception as e:
            logger.error(f"Could not read holdings: {e}")
            return []

    def get_total_value(self) -> float:
        """Get total portfolio value in dollars."""
        self.login()
        try:
            profile = rh.load_portfolio_profile()
            return float(profile.get("equity", 0))
        except Exception as e:
            logger.error(f"Could not get portfolio value: {e}")
            return 0.0

    def logout(self):
        """Logout from Robinhood."""
        try:
            rh.logout()
            self._logged_in = False
        except Exception as e:
            logger.warning(f"Logout failed: {e}")


# Single instance shared across the app
robinhood_client = RobinhoodClient()
