
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

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI using Wilder's standard smoothing method.

    The first RSI value requires period + 1 prices.
    A completely flat market returns RSI 50.
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series")

    if isinstance(period, bool) or not isinstance(period, int) or period <= 0:
        raise ValueError("period must be a positive integer")

    if not pd.api.types.is_numeric_dtype(prices):
        raise TypeError("prices must contain numeric values")

    if not prices.empty and not prices.isna().all():
        if not prices.map(lambda value: pd.notna(value) and pd.api.types.is_number(value)).all():
            raise ValueError("prices must contain valid numeric values")

    delta = prices.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    result = pd.Series(float("nan"), index=prices.index, dtype=float)

    if len(prices) <= period:
        return result

    average_gain = gains.iloc[1:period + 1].mean()
    average_loss = losses.iloc[1:period + 1].mean()

    def calculate_value(gain, loss):
        if loss == 0 and gain == 0:
            return 50.0
        if loss == 0:
            return 100.0
        if gain == 0:
            return 0.0

        relative_strength = gain / loss
        return 100 - (100 / (1 + relative_strength))

    result.iloc[period] = calculate_value(average_gain, average_loss)

    for i in range(period + 1, len(prices)):
        average_gain = (
            average_gain * (period - 1) + gains.iloc[i]
        ) / period

        average_loss = (
            average_loss * (period - 1) + losses.iloc[i]
        ) / period

        result.iloc[i] = calculate_value(average_gain, average_loss)

    return result
