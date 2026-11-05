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


def test_trade_risk_includes_fees_and_slippage(setup_risk):
    manager, _ = setup_risk

    # Pay 100 * 1.001 = 100.1. Stop at 90 returns 90 * 0.9995 * 0.999.
    risk = manager.calculate_trade_risk(1, 100, 90)

    assert risk == pytest.approx(100.1 - 90 * 0.9995 * 0.999)


def test_trade_risk_rejects_stop_at_or_above_price(setup_risk):
    manager, _ = setup_risk

    with pytest.raises(ValueError, match="below the execution price"):
        manager.calculate_trade_risk(1, 100, 100)


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf")])
def test_trade_risk_rejects_invalid_numbers(setup_risk, bad):
    manager, _ = setup_risk

    with pytest.raises(ValueError):
        manager.calculate_trade_risk(bad, 100, 90)

    with pytest.raises(ValueError):
        manager.calculate_trade_risk(1, bad, 90)

    with pytest.raises(ValueError):
        manager.calculate_trade_risk(1, 100, bad)


def test_max_risk_amount_is_one_percent_of_portfolio(setup_risk):
    manager, _ = setup_risk

    assert manager.max_risk_amount(1000) == pytest.approx(10.0)

    with pytest.raises(ValueError):
        manager.max_risk_amount(0)
