"""Portfolio risk monitoring for Project Quant.

This module evaluates risk for virtual trading only.
It does not place or approve trades.
"""

import math
from dataclasses import dataclass
from datetime import date, datetime, timezone

from config.settings import Settings, load_settings
from trading.portfolio import Portfolio


@dataclass(frozen=True)
class RiskAssessment:
    """Snapshot of the portfolio's current risk status."""

    portfolio_value: float
    exposure_ratio: float
    daily_loss_ratio: float
    drawdown_ratio: float
    can_open_trade: bool
    reasons: tuple[str, ...]


class RiskManager:
    """Monitor exposure, daily losses, and portfolio drawdown."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.peak_portfolio_value: float | None = None
        self.day_start_value: float | None = None
        self.current_day: date | None = None

    def max_risk_amount(self, portfolio_value: float) -> float:
        """Largest loss (in USDT) one trade may risk, per max_risk_per_trade."""

        if not math.isfinite(portfolio_value) or portfolio_value <= 0:
            raise ValueError("Portfolio value must be positive and finite")

        return portfolio_value * self.settings.max_risk_per_trade

    def calculate_trade_risk(
        self,
        quantity: float,
        execution_price: float,
        stop_price: float,
    ) -> float:
        """Loss (in USDT) if a purchase is exited at its stop price.

        Includes the entry fee, the exit fee and exit slippage, so it is
        the cash paid in minus the cash received back at the stop.
        """

        for name, value in (
            ("quantity", quantity),
            ("execution_price", execution_price),
            ("stop_price", stop_price),
        ):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number")

        if stop_price >= execution_price:
            raise ValueError("stop_price must be below the execution price")

        fee = self.settings.fee_rate
        slippage = self.settings.slippage_rate

        cash_paid = quantity * execution_price * (1 + fee)
        cash_back = quantity * stop_price * (1 - slippage) * (1 - fee)

        return cash_paid - cash_back

    def assess(
        self,
        portfolio: Portfolio,
        market_prices: dict[str, float],
        *,
        additional_position_value: float = 0.0,
        today: date | None = None,
    ) -> RiskAssessment:
        """Assess whether opening an additional position is within limits.

        additional_position_value is the proposed position's market value.
        It is used only to estimate exposure, not to change the portfolio.
        """

        if (
            not math.isfinite(additional_position_value)
            or additional_position_value < 0
        ):
            raise ValueError(
                "additional_position_value must be finite and non-negative"
            )

        for symbol in portfolio.holdings:
            price = market_prices.get(symbol)

            if price is None or not math.isfinite(price) or price <= 0:
                raise ValueError(f"Missing or invalid market price for {symbol}")

        portfolio_value = portfolio.get_portfolio_value(market_prices)

        if not math.isfinite(portfolio_value) or portfolio_value <= 0:
            raise ValueError("Portfolio value must be positive and finite")

        held_value = sum(
            quantity * market_prices[symbol]
            for symbol, quantity in portfolio.holdings.items()
        )

        exposure_ratio = (
            held_value + additional_position_value
        ) / portfolio_value

        assessment_day = today or datetime.now(timezone.utc).date()

        if self.current_day != assessment_day:
            self.current_day = assessment_day
            self.day_start_value = portfolio_value

        if self.peak_portfolio_value is None:
            self.peak_portfolio_value = portfolio_value
        else:
            self.peak_portfolio_value = max(
                self.peak_portfolio_value, portfolio_value
            )

        daily_loss_ratio = max(
            0.0,
            (self.day_start_value - portfolio_value) / self.day_start_value,
        )

        drawdown_ratio = max(
            0.0,
            (self.peak_portfolio_value - portfolio_value)
            / self.peak_portfolio_value,
        )

        reasons = []

        if exposure_ratio >= self.settings.max_portfolio_exposure:
            reasons.append("Maximum portfolio exposure reached")

        if daily_loss_ratio >= self.settings.max_daily_loss:
            reasons.append("Maximum daily loss reached")

        if drawdown_ratio >= self.settings.max_drawdown:
            reasons.append("Maximum portfolio drawdown reached")

        return RiskAssessment(
            portfolio_value=portfolio_value,
            exposure_ratio=exposure_ratio,
            daily_loss_ratio=daily_loss_ratio,
            drawdown_ratio=drawdown_ratio,
            can_open_trade=not reasons,
            reasons=tuple(reasons),
        )
