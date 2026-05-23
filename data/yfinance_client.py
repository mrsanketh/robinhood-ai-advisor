import yfinance as yf
import pandas as pd
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class YFinanceClient:
    """
    Fetches free stock data from Yahoo Finance.
    No API key needed.
    Uses caching so we don't hit Yahoo repeatedly for the same stock.
    """

    @lru_cache(maxsize=200)
    def get_info(self, ticker: str) -> dict:
        """Get company fundamentals — PE ratio, revenue growth, profit margin etc."""
        try:
            stock = yf.Ticker(ticker)
            return stock.info or {}
        except Exception as e:
            logger.warning(f"Could not fetch info for {ticker}: {e}")
            return {}

    @lru_cache(maxsize=200)
    def get_history(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        """Get price history for the past year."""
        try:
            stock = yf.Ticker(ticker)
            return stock.history(period=period)
        except Exception as e:
            logger.warning(f"Could not fetch history for {ticker}: {e}")
            return pd.DataFrame()

    def get_current_price(self, ticker: str) -> float:
        """Get the latest closing price."""
        hist = self.get_history(ticker, period="5d")
        if hist.empty:
            return 0.0
        return round(float(hist["Close"].iloc[-1]), 2)

    def get_moving_averages(self, ticker: str) -> dict:
        """
        Calculate 50-day and 200-day moving averages.
        Used by the momentum scorer.
        """
        hist = self.get_history(ticker, period="1y")
        if hist.empty or len(hist) < 50:
            return {"current": None, "ma50": None, "ma200": None}

        closes = hist["Close"]
        return {
            "current": round(float(closes.iloc[-1]), 2),
            "ma50":    round(float(closes.tail(50).mean()), 2),
            "ma200":   round(float(closes.tail(200).mean()), 2) if len(closes) >= 200 else None,
        }

    def get_rsi(self, ticker: str, period: int = 14) -> float:
        """
        Calculate RSI (Relative Strength Index).
        Above 70 = overbought (risky to buy).
        Below 30 = oversold (potential opportunity).
        40-60 = healthy range.
        """
        hist = self.get_history(ticker, period="3mo")
        if hist.empty or len(hist) < period + 1:
            return 50.0  # return neutral if not enough data

        delta = hist["Close"].diff()
        gain  = delta.where(delta > 0, 0).rolling(period).mean()
        loss  = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs    = gain / loss.replace(0, 1e-10)
        rsi   = 100 - (100 / (1 + rs))
        return round(float(rsi.iloc[-1]), 2)

    def get_52_week_performance(self, ticker: str) -> float:
        """Return % change in stock price over the past 52 weeks."""
        hist = self.get_history(ticker, period="1y")
        if hist.empty or len(hist) < 2:
            return 0.0
        start = float(hist["Close"].iloc[0])
        end   = float(hist["Close"].iloc[-1])
        return round(((end - start) / start) * 100, 2)


# Single instance shared across the whole app
yf_client = YFinanceClient()
