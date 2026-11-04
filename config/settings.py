"""Central configuration for Project Quant.

Every setting is documented here. Credentials are never stored in code;
future API keys must be read from environment variables.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Safety switch. Real-money trading is NOT supported in this version.
# Changing this value does not add any real-order code; it exists so the
# rule is explicit and tested.
REAL_MONEY_TRADING: bool = False

# Safety switch. Leverage and futures are not supported.
LEVERAGE_ENABLED: bool = False


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    # Starting virtual cash balance, in USDT.
    initial_balance_usdt: float = 1000.0
    # Symbols supported initially.
    symbols: tuple[str, ...] = ("BTC/USDT", "ETH/USDT")
    # Supported candle timeframes.
    timeframes: tuple[str, ...] = ("15m", "1h", "4h", "1d", "1w")
    # Assumed exchange fee per trade side (0.001 = 0.1%).
    fee_rate: float = 0.001
    # Assumed slippage per trade side (0.0005 = 0.05%).
    slippage_rate: float = 0.0005
    # Max fraction of portfolio value allowed in open positions.
    max_portfolio_exposure: float = 0.5
    # Max fraction of portfolio risked on a single trade.
    max_risk_per_trade: float = 0.01
    # Max simulated loss per day, as a fraction of portfolio value.
    max_daily_loss: float = 0.03
    # Drawdown from peak at which trading recommendations pause.
    max_drawdown: float = 0.15
    # Where market data and logs are stored.
    data_dir: str = "data"
    log_dir: str = "logs"
    real_money_trading: bool = field(default=REAL_MONEY_TRADING, init=False)

    def __post_init__(self) -> None:
        if self.initial_balance_usdt <= 0:
            raise ValueError("initial_balance_usdt must be positive")
        for name in ("fee_rate", "slippage_rate"):
            if not 0 <= getattr(self, name) < 0.1:
                raise ValueError(f"{name} must be between 0 and 0.1")
        for name in ("max_portfolio_exposure", "max_risk_per_trade",
                     "max_daily_loss", "max_drawdown"):
            if not 0 < getattr(self, name) <= 1:
                raise ValueError(f"{name} must be in (0, 1]")
        if self.real_money_trading or LEVERAGE_ENABLED:
            raise RuntimeError("Real-money trading and leverage are disabled")


def load_settings() -> Settings:
    """Return the default settings."""
    return Settings()
