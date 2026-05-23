import finnhub
import time
import config
import logging

logger = logging.getLogger(__name__)

# Finnhub free tier: 60 calls per minute
# We make 2 calls per stock (analyst + earnings)
# 35 stocks = 70 calls — just over the limit
# Adding 1.5 second delay between stocks keeps us under 60/min
RATE_LIMIT_DELAY = 1.5


class FinnhubClient:
    """
    Fetches analyst recommendations and earnings calendar from Finnhub.
    Free tier: 60 API calls per minute.
    Rate limit delay added to prevent 429 errors on large portfolios.
    """

    def __init__(self):
        self.client     = finnhub.Client(api_key=config.FINNHUB_API_KEY)
        self._cache     = {}
        self._last_call = 0.0

    def _wait_for_rate_limit(self):
        """Wait if needed to stay under 60 calls per minute."""
        elapsed = time.time() - self._last_call
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_call = time.time()

    def _get_cached(self, key: str, fetch_fn, ttl_minutes: int = 60):
        """Return cached result if fresh, otherwise fetch and cache."""
        now = time.time()
        if key in self._cache:
            value, timestamp = self._cache[key]
            if now - timestamp < ttl_minutes * 60:
                return value
        result = fetch_fn()
        self._cache[key] = (result, now)
        return result

    def get_analyst_recommendations(self, ticker: str) -> dict:
        """
        Get analyst buy/sell/hold breakdown.
        Returns a score from 0 to 10.
        """
        def fetch():
            try:
                self._wait_for_rate_limit()
                recs = self.client.recommendation_trends(ticker)
                return recs[0] if recs else {}
            except Exception as e:
                logger.warning(f"Analyst recommendations failed for {ticker}: {e}")
                return {}

        data = self._get_cached(f"analyst_{ticker}", fetch, ttl_minutes=240)

        if not data:
            return {"score": 5.0, "strong_buy": 0, "buy": 0, "hold": 0, "sell": 0}

        strong_buy  = data.get("strongBuy",  0)
        buy         = data.get("buy",        0)
        hold        = data.get("hold",       0)
        sell        = data.get("sell",       0)
        strong_sell = data.get("strongSell", 0)

        total = strong_buy + buy + hold + sell + strong_sell
        if total == 0:
            return {"score": 5.0, "strong_buy": 0, "buy": 0, "hold": 0, "sell": 0}

        weighted = (
            (strong_buy  * 10.0) +
            (buy         *  7.5) +
            (hold        *  5.0) +
            (sell        *  2.5) +
            (strong_sell *  0.0)
        ) / total

        return {
            "score":      round(weighted, 2),
            "strong_buy": strong_buy,
            "buy":        buy,
            "hold":       hold,
            "sell":       sell + strong_sell,
        }

    def get_earnings_calendar(self, ticker: str) -> dict:
        """Check if earnings are coming up in the next 14 days."""
        from datetime import datetime, timedelta

        def fetch():
            try:
                self._wait_for_rate_limit()
                today     = datetime.now().strftime("%Y-%m-%d")
                two_weeks = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
                return self.client.earnings_calendar(
                    _from=today, to=two_weeks, symbol=ticker
                )
            except Exception as e:
                logger.warning(f"Earnings calendar failed for {ticker}: {e}")
                return {}

        data  = self._get_cached(f"earnings_{ticker}", fetch, ttl_minutes=360)
        earns = data.get("earningsCalendar", []) if data else []

        if not earns:
            return {"upcoming": False, "date": None, "days_away": None}

        earn_date = earns[0].get("date", "")
        try:
            days_away = (datetime.strptime(earn_date, "%Y-%m-%d") - datetime.now()).days
        except Exception:
            days_away = None

        return {
            "upcoming":  True,
            "date":      earn_date,
            "days_away": days_away,
        }


# Single instance shared across the app
finnhub_client = FinnhubClient()
