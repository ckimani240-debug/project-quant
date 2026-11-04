
"""Technical analysis indicators for Project Quant."""

import pandas as pd


def calculate_sma(prices: pd.Series, window: int) -> pd.Series:
    """Calculate a simple moving average.

    The result is only available after a complete window of prices.
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")

    if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
        raise ValueError("window must be a positive integer")

    return prices.rolling(
        window=window,
        min_periods=window,
    ).mean()


def calculate_ema(prices: pd.Series, span: int) -> pd.Series:
    """Calculate an exponential moving average.

    Recent prices receive more weight than older prices.
    The result is only available after a complete span of prices.
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")

    if isinstance(span, bool) or not isinstance(span, int) or span <= 0:
        raise ValueError("span must be a positive integer")

    return prices.ewm(
        span=span,
        adjust=False,
        min_periods=span,
    ).mean()

