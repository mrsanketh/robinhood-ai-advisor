import robin_stocks.robinhood as rh
import config
import logging

logger = logging.getLogger(__name__)


class RobinhoodClient:
    """
    Reads your real Robinhood portfolio.
    Uses robin_stocks library — free and open source.

    Login uses your credentials from .env once,
    then caches the session token for future runs.
    """

    def __init__(self):
        self._logged_in = False

    def login(self):
        """Login to Robinhood using credentials from .env"""
        if self._logged_in:
            return
        try:
            rh.login(
                username=config.ROBINHOOD_USERNAME,
                password=config.ROBINHOOD_PASSWORD,
                store_session=True   # saves token locally after first login
            )
            self._logged_in = True
            logger.info("Logged in to Robinhood")
        except Exception as e:
            logger.error(f"Robinhood login failed: {e}")
            raise

    def get_holdings(self) -> list:
        """
        Read all your stock positions.
        Returns a list of dicts with ticker, shares, buy price, current value.
        """
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

                shares    = float(position.get("quantity", 0))
                avg_cost  = float(position.get("average_buy_price", 0))
                equity    = shares * avg_cost

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
