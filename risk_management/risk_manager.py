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


def _is_positive_finite(value: object) -> bool:
    """Return True for a real, finite number greater than zero."""

    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


@dataclass(frozen=True)
class RiskState:
    """The risk information that must survive an application restart.

    A fresh state has all three fields set to None. Otherwise all three
    must be valid. Anything in between is rejected, so a damaged saved
    state fails safely instead of being trusted.
    """

    current_day: date | None = None
    day_start_value: float | None = None
    peak_portfolio_value: float | None = None

    def __post_init__(self) -> None:
        fields = (
            self.current_day,
            self.day_start_value,
            self.peak_portfolio_value,
        )

        if all(value is None for value in fields):
            return

        if any(value is None for value in fields):
            raise ValueError("Risk state is incomplete")

        if isinstance(self.current_day, datetime) or not isinstance(
            self.current_day, date
        ):
            raise ValueError("Risk state day must be a date")

        if not _is_positive_finite(self.day_start_value):
            raise ValueError(
                "Risk state day-start value must be positive and finite"
            )

        if not _is_positive_finite(self.peak_portfolio_value):
            raise ValueError(
                "Risk state peak value must be positive and finite"
            )


class RiskManager:
    """Monitor exposure, daily losses, and portfolio drawdown."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.peak_portfolio_value: float | None = None
        self.day_start_value: float | None = None
        self.current_day: date | None = None

    def get_state(self) -> RiskState:
        """Return the current risk state as a validated, frozen value."""

        return RiskState(
            current_day=self.current_day,
            day_start_value=self.day_start_value,
            peak_portfolio_value=self.peak_portfolio_value,
        )

    def commit_state(self, state: RiskState) -> None:
        """Adopt a risk state (for example after a trade was saved).

        Also used to restore a state loaded from the database.
        """

        if not isinstance(state, RiskState):
            raise TypeError("state must be a RiskState")

        self.current_day = state.current_day
        self.day_start_value = state.day_start_value
        self.peak_portfolio_value = state.peak_portfolio_value

    def evaluate(
        self,
        portfolio: Portfolio,
        market_prices: dict[str, float],
        *,
        additional_position_value: float = 0.0,
        today: date | None = None,
    ) -> tuple[RiskAssessment, RiskState]:
        """Assess risk and propose the next risk state, changing nothing.

        additional_position_value is the proposed position's market value.
        It is used only to estimate exposure, not to change the portfolio.
        The returned RiskState is NOT stored; pass it to commit_state()
        once the related trade has been saved successfully.
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

        if (
            self.current_day != assessment_day
            or self.day_start_value is None
        ):
            new_day = assessment_day
            new_day_start_value = portfolio_value
        else:
            new_day = self.current_day
            new_day_start_value = self.day_start_value

        if self.peak_portfolio_value is None:
            new_peak = portfolio_value
        else:
            new_peak = max(self.peak_portfolio_value, portfolio_value)

        daily_loss_ratio = max(
            0.0,
            (new_day_start_value - portfolio_value) / new_day_start_value,
        )

        drawdown_ratio = max(
            0.0,
            (new_peak - portfolio_value) / new_peak,
        )

        reasons = []

        if exposure_ratio >= self.settings.max_portfolio_exposure:
            reasons.append("Maximum portfolio exposure reached")

        if daily_loss_ratio >= self.settings.max_daily_loss:
            reasons.append("Maximum daily loss reached")

        if drawdown_ratio >= self.settings.max_drawdown:
            reasons.append("Maximum portfolio drawdown reached")

        assessment = RiskAssessment(
            portfolio_value=portfolio_value,
            exposure_ratio=exposure_ratio,
            daily_loss_ratio=daily_loss_ratio,
            drawdown_ratio=drawdown_ratio,
            can_open_trade=not reasons,
            reasons=tuple(reasons),
        )

        proposed_state = RiskState(
            current_day=new_day,
            day_start_value=new_day_start_value,
            peak_portfolio_value=new_peak,
        )

        return assessment, proposed_state

    def assess(
        self,
        portfolio: Portfolio,
        market_prices: dict[str, float],
        *,
        additional_position_value: float = 0.0,
        today: date | None = None,
    ) -> RiskAssessment:
        """Assess risk and record the new state immediately.

        Behaves exactly as before. Code that must be able to undo the
        state change (such as a trade that might fail to save) should use
        evaluate() and commit_state() instead.
        """

        assessment, proposed_state = self.evaluate(
            portfolio,
            market_prices,
            additional_position_value=additional_position_value,
            today=today,
        )

        self.commit_state(proposed_state)

        return assessment
