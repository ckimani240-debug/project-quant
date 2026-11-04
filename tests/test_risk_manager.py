from datetime import date

import pytest

from risk_management.risk_manager import RiskManager
from trading.portfolio import Portfolio


@pytest.fixture
def setup_risk():
    return RiskManager(), Portfolio()


def test_new_portfolio_is_within_risk_limits(setup_risk):
    manager, portfolio = setup_risk

    result = manager.assess(portfolio, {})

    assert result.can_open_trade is True
    assert result.portfolio_value == 1000.0
    assert result.exposure_ratio == 0.0
    assert result.daily_loss_ratio == 0.0
    assert result.drawdown_ratio == 0.0


def test_exposure_limit_blocks_additional_position(setup_risk):
    manager, portfolio = setup_risk

    result = manager.assess(
        portfolio, {},
        additional_position_value=500,
    )

    assert result.can_open_trade is False
    assert "Maximum portfolio exposure reached" in result.reasons


def test_exposure_below_limit_is_allowed(setup_risk):
    manager, portfolio = setup_risk

    result = manager.assess(
        portfolio, {},
        additional_position_value=400,
    )

    assert result.can_open_trade is True
    assert result.exposure_ratio == 0.4


def test_daily_loss_limit_blocks_trading(setup_risk):
    manager, portfolio = setup_risk
    today = date(2026, 11, 4)

    manager.assess(portfolio, {}, today=today)

    portfolio.cash_balance = 970.0

    result = manager.assess(portfolio, {}, today=today)

    assert result.can_open_trade is False
    assert result.daily_loss_ratio == pytest.approx(0.03)
    assert "Maximum daily loss reached" in result.reasons


def test_daily_loss_resets_on_new_day(setup_risk):
    manager, portfolio = setup_risk

    manager.assess(portfolio, {}, today=date(2026, 11, 4))

    portfolio.cash_balance = 970.0
    manager.assess(portfolio, {}, today=date(2026, 11, 4))

    portfolio.cash_balance = 970.0

    result = manager.assess(
        portfolio, {}, today=date(2026, 11, 5)
    )

    assert result.daily_loss_ratio == 0.0
    assert result.can_open_trade is True


def test_drawdown_limit_blocks_trading(setup_risk):
    manager, portfolio = setup_risk

    manager.assess(portfolio, {})

    portfolio.cash_balance = 850.0

    result = manager.assess(portfolio, {})

    assert result.can_open_trade is False
    assert result.drawdown_ratio == pytest.approx(0.15)
    assert "Maximum portfolio drawdown reached" in result.reasons


def test_peak_value_tracks_new_high(setup_risk):
    manager, portfolio = setup_risk

    portfolio.cash_balance = 1100.0
    manager.assess(portfolio, {})

    assert manager.peak_portfolio_value == 1100.0


def test_invalid_proposed_position_is_rejected(setup_risk):
    manager, portfolio = setup_risk

    with pytest.raises(ValueError):
        manager.assess(
            portfolio, {},
            additional_position_value=-100,
        )


def test_invalid_market_price_is_rejected(setup_risk):
    manager, portfolio = setup_risk

    portfolio.holdings["BTC/USDT"] = 0.01

    with pytest.raises(ValueError):
        manager.assess(portfolio, {"BTC/USDT": 0})
