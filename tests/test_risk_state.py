"""Tests for persistent risk state and the evaluate/commit split."""

from datetime import date, datetime, timezone

import pytest

from risk_management.risk_manager import RiskManager, RiskState
from trading.portfolio import Portfolio

DAY_1 = date(2026, 11, 4)
DAY_2 = date(2026, 11, 5)


# ---------- RiskState validation ----------


def test_fresh_risk_state_is_all_none():
    state = RiskState()

    assert state.current_day is None
    assert state.day_start_value is None
    assert state.peak_portfolio_value is None


def test_valid_risk_state_is_accepted():
    state = RiskState(DAY_1, 1000.0, 1100.0)

    assert state.current_day == DAY_1
    assert state.day_start_value == 1000.0
    assert state.peak_portfolio_value == 1100.0


@pytest.mark.parametrize(
    "args",
    [
        (DAY_1, None, None),
        (None, 1000.0, 1000.0),
        (DAY_1, 1000.0, None),
        (DAY_1, None, 1000.0),
        (None, None, 1000.0),
    ],
)
def test_incomplete_risk_state_is_rejected(args):
    with pytest.raises(ValueError, match="incomplete"):
        RiskState(*args)


@pytest.mark.parametrize(
    "bad_value",
    [0, -1.0, float("nan"), float("inf"), "1000", True],
)
def test_invalid_day_start_value_is_rejected(bad_value):
    with pytest.raises(ValueError):
        RiskState(DAY_1, bad_value, 1000.0)


@pytest.mark.parametrize(
    "bad_value",
    [0, -1.0, float("nan"), float("inf"), "1000", True],
)
def test_invalid_peak_value_is_rejected(bad_value):
    with pytest.raises(ValueError):
        RiskState(DAY_1, 1000.0, bad_value)


def test_invalid_day_is_rejected():
    with pytest.raises(ValueError, match="date"):
        RiskState("2026-11-04", 1000.0, 1000.0)


def test_datetime_is_not_accepted_as_day():
    with pytest.raises(ValueError, match="date"):
        RiskState(
            datetime(2026, 11, 4, tzinfo=timezone.utc),
            1000.0,
            1000.0,
        )


def test_risk_state_is_frozen():
    state = RiskState(DAY_1, 1000.0, 1000.0)

    with pytest.raises(Exception):
        state.peak_portfolio_value = 5000.0


# ---------- get_state / commit_state ----------


def test_new_manager_has_fresh_state():
    assert RiskManager().get_state() == RiskState()


def test_commit_state_restores_values():
    manager = RiskManager()

    manager.commit_state(RiskState(DAY_1, 900.0, 1100.0))

    assert manager.current_day == DAY_1
    assert manager.day_start_value == 900.0
    assert manager.peak_portfolio_value == 1100.0
    assert manager.get_state() == RiskState(DAY_1, 900.0, 1100.0)


def test_commit_state_rejects_wrong_type():
    manager = RiskManager()

    with pytest.raises(TypeError):
        manager.commit_state({"peak": 1000.0})


# ---------- evaluate() changes nothing ----------


def test_evaluate_does_not_change_manager_state():
    manager = RiskManager()
    portfolio = Portfolio()

    manager.evaluate(portfolio, {}, today=DAY_1)

    assert manager.get_state() == RiskState()


def test_evaluate_returns_proposed_state():
    manager = RiskManager()
    portfolio = Portfolio()

    assessment, proposed = manager.evaluate(portfolio, {}, today=DAY_1)

    assert assessment.can_open_trade is True
    assert proposed == RiskState(DAY_1, 1000.0, 1000.0)


def test_evaluate_proposes_new_peak_without_storing_it():
    manager = RiskManager()
    manager.commit_state(RiskState(DAY_1, 1000.0, 1000.0))
    portfolio = Portfolio()
    portfolio.cash_balance = 1100.0

    _, proposed = manager.evaluate(portfolio, {}, today=DAY_1)

    assert proposed.peak_portfolio_value == 1100.0
    assert manager.peak_portfolio_value == 1000.0


def test_evaluate_proposes_new_day_baseline_without_storing_it():
    manager = RiskManager()
    manager.commit_state(RiskState(DAY_1, 1000.0, 1000.0))
    portfolio = Portfolio()
    portfolio.cash_balance = 950.0

    _, proposed = manager.evaluate(portfolio, {}, today=DAY_2)

    assert proposed.current_day == DAY_2
    assert proposed.day_start_value == 950.0
    assert manager.current_day == DAY_1
    assert manager.day_start_value == 1000.0


def test_evaluate_rejects_invalid_input_without_changing_state():
    manager = RiskManager()
    manager.commit_state(RiskState(DAY_1, 1000.0, 1000.0))
    portfolio = Portfolio()

    with pytest.raises(ValueError):
        manager.evaluate(
            portfolio, {}, additional_position_value=-1, today=DAY_1
        )

    assert manager.get_state() == RiskState(DAY_1, 1000.0, 1000.0)


# ---------- assess() still records state (old behaviour) ----------


def test_assess_records_state_like_before():
    manager = RiskManager()
    portfolio = Portfolio()

    manager.assess(portfolio, {}, today=DAY_1)

    assert manager.get_state() == RiskState(DAY_1, 1000.0, 1000.0)


# ---------- restart behaviour ----------


def test_restored_state_still_sees_drawdown_after_restart():
    """The whole point: a restart must not erase a remembered peak."""

    portfolio = Portfolio()
    portfolio.cash_balance = 860.0

    fresh = RiskManager()
    forgetful = fresh.assess(portfolio, {}, today=DAY_1)
    assert forgetful.drawdown_ratio == 0.0

    restored = RiskManager()
    restored.commit_state(RiskState(DAY_1, 1000.0, 1000.0))
    result = restored.assess(portfolio, {}, today=DAY_1)

    assert result.drawdown_ratio == pytest.approx(0.14)
    assert result.daily_loss_ratio == pytest.approx(0.14)
    assert result.can_open_trade is False


def test_restored_state_matches_continuous_run():
    portfolio = Portfolio()

    continuous = RiskManager()
    continuous.assess(portfolio, {}, today=DAY_1)
    portfolio.cash_balance = 880.0
    expected = continuous.assess(portfolio, {}, today=DAY_1)

    restored = RiskManager()
    restored.commit_state(RiskState(DAY_1, 1000.0, 1000.0))
    actual = restored.assess(portfolio, {}, today=DAY_1)

    assert actual == expected
    assert restored.get_state() == continuous.get_state()


# ---------- extra risk-manager gaps from the audit ----------


@pytest.mark.parametrize(
    "bad_price",
    [None, float("nan"), float("inf"), -5.0, 0],
)
def test_bad_prices_for_held_assets_are_rejected(bad_price):
    manager = RiskManager()
    portfolio = Portfolio()
