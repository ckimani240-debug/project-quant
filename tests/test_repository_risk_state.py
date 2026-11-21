"""Tests for risk-state persistence, atomic trade saves and stale-write guard."""

import sqlite3
from datetime import date, datetime, timezone

import pytest

from risk_management.risk_manager import RiskState
from storage.database import get_connection
from storage.portfolio_repository import (
    PortfolioRepository,
    StaleStateError,
)
from trading.portfolio import Transaction

DAY = date(2026, 11, 21)
TS = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def make_buy(symbol="BTC/USDT", quantity=0.01, price=60000.0, fee=0.6):
    return Transaction(
        symbol=symbol,
        side="buy",
        quantity=quantity,
        price=price,
        fee=fee,
        timestamp=TS,
    )


def make_sell(symbol="BTC/USDT", quantity=0.01, price=61000.0, fee=0.61):
    return Transaction(
        symbol=symbol,
        side="sell",
        quantity=quantity,
        price=price,
        fee=fee,
        timestamp=TS,
    )


@pytest.fixture
def repo(tmp_path):
    repository = PortfolioRepository(tmp_path / "test.db")
    repository.create_portfolio()
    return repository


def count_rows(repo, table):
    connection = get_connection(repo.db_path)
    try:
        return connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]
    finally:
        connection.close()


# ---------- risk state save / load ----------


def test_load_risk_state_returns_fresh_state_when_nothing_saved(repo):
    assert repo.load_risk_state() == RiskState()


def test_risk_state_round_trip(repo):
    state = RiskState(DAY, 1000.0, 1100.0)

    repo.save_risk_state(state)

    assert repo.load_risk_state() == state


def test_risk_state_survives_restart(tmp_path):
    db_path = tmp_path / "test.db"
    first = PortfolioRepository(db_path)
    first.create_portfolio()
    first.save_risk_state(RiskState(DAY, 950.0, 1200.0))

    second = PortfolioRepository(db_path)

    assert second.load_risk_state() == RiskState(DAY, 950.0, 1200.0)


def test_save_risk_state_overwrites_single_row(repo):
    repo.save_risk_state(RiskState(DAY, 1000.0, 1000.0))
    repo.save_risk_state(RiskState(DAY, 900.0, 1000.0))

    assert count_rows(repo, "risk_state") == 1
    assert repo.load_risk_state() == RiskState(DAY, 900.0, 1000.0)


def test_save_risk_state_rejects_wrong_type(repo):
    with pytest.raises(TypeError):
        repo.save_risk_state({"peak": 1000.0})


def _write_raw_risk_row(repo, day, start, peak):
    connection = get_connection(repo.db_path)
    try:
        with connection:
            connection.execute(
                "INSERT OR REPLACE INTO risk_state "
                "(id, current_day, day_start_value, peak_portfolio_value) "
                "VALUES (1, ?, ?, ?)",
                (day, start, peak),
            )
    finally:
        connection.close()


@pytest.mark.parametrize(
    "day,start,peak",
    [
        ("2026-11-21", None, 1000.0),
        ("2026-11-21", 1000.0, None),
        (None, 1000.0, 1000.0),
        ("not-a-date", 1000.0, 1000.0),
        ("2026-11-21", 0.0, 1000.0),
        ("2026-11-21", 1000.0, -5.0),
        ("2026-11-21", float("inf"), 1000.0),
    ],
)
def test_damaged_risk_row_fails_safely(repo, day, start, peak):
    _write_raw_risk_row(repo, day, start, peak)

    with pytest.raises(ValueError, match="damaged"):
        repo.load_risk_state()


# ---------- save_trade with risk state ----------


def test_save_trade_saves_portfolio_trade_and_risk_state(repo):
    portfolio = repo.load_portfolio()
    portfolio.cash_balance = 399.4
    portfolio.holdings = {"BTC/USDT": 0.01}
    trade = make_buy()
    portfolio.transactions.append(trade)

    repo.save_trade(
        portfolio,
        trade,
        risk_state=RiskState(DAY, 1000.0, 1000.0),
        expected_transaction_count=0,
    )

    restored = repo.load_portfolio()
    assert restored.cash_balance == 399.4
    assert restored.holdings == {"BTC/USDT": 0.01}
    assert len(restored.transactions) == 1
    assert repo.load_risk_state() == RiskState(DAY, 1000.0, 1000.0)


def test_all_transaction_fields_round_trip(repo):
    portfolio = repo.load_portfolio()
    portfolio.cash_balance = 399.4
    portfolio.holdings = {"BTC/USDT": 0.01}
    trade = make_buy()
    portfolio.transactions.append(trade)

    repo.save_trade(portfolio, trade)

    saved = repo.load_portfolio().transactions[0]
    assert saved.symbol == trade.symbol
    assert saved.side == trade.side
    assert saved.quantity == trade.quantity
    assert saved.price == trade.price
    assert saved.fee == trade.fee
    assert saved.timestamp == trade.timestamp


def test_old_style_save_trade_still_works(repo):
    portfolio = repo.load_portfolio()
    portfolio.cash_balance = 399.4
    portfolio.holdings = {"BTC/USDT": 0.01}
    trade = make_buy()
    portfolio.transactions.append(trade)

    repo.save_trade(portfolio, trade)

    assert count_rows(repo, "transactions") == 1
    assert repo.load_risk_state() == RiskState()


def test_full_sell_removes_holding_from_database(repo):
    portfolio = repo.load_portfolio()
    portfolio.cash_balance = 399.4
    portfolio.holdings = {"BTC/USDT": 0.01}
    buy = make_buy()
    portfolio.transactions.append(buy)
    repo.save_trade(portfolio, buy, expected_transaction_count=0)

    portfolio.cash_balance = 1008.8
    portfolio.holdings = {}
    sell = make_sell()
    portfolio.transactions.append(sell)
    repo.save_trade(portfolio, sell, expected_transaction_count=1)

    restored = repo.load_portfolio()
    assert restored.holdings == {}
    assert restored.cash_balance == 1008.8
    assert len(restored.transactions) == 2
    assert count_rows(repo, "holdings") == 0


def test_btc_and_eth_portfolio_round_trips(repo):
    portfolio = repo.load_portfolio()
    portfolio.cash_balance = 100.0
    portfolio.holdings = {"BTC/USDT": 0.01, "ETH/USDT": 0.25}
    trade = make_buy("ETH/USDT", 0.25, 2000.0, 0.5)
    portfolio.transactions.append(trade)

    repo.save_trade(portfolio, trade)

    restored = repo.load_portfolio()
    assert restored.holdings == {"BTC/USDT": 0.01, "ETH/USDT": 0.25}


# ---------- validation writes nothing ----------


@pytest.mark.parametrize(
    "bad",
    [
        Transaction("BTC/USDT", "hold", 0.01, 60000.0, 0.6, TS),
        Transaction("BTC/USDT", "buy", float("nan"), 60000.0, 0.6, TS),
        Transaction("BTC/USDT", "buy", 0.01, 0.0, 0.6, TS),
        Transaction("BTC/USDT", "buy", 0.01, 60000.0, -1.0, TS),
        Transaction("BTC/USDT", "buy", 0.01, 60000.0, 0.6, "yesterday"),
    ],
)
def test_invalid_transaction_writes_nothing(repo, bad):
    portfolio = repo.load_portfolio()
    portfolio.cash_balance = 500.0

    with pytest.raises(ValueError):
        repo.save_trade(portfolio, bad)

    restored = repo.load_portfolio()
    assert restored.cash_balance == 1000.0
    assert count_rows(repo, "transactions") == 0


def test_wrong_risk_state_type_writes_nothing(repo):
    portfolio = repo.load_portfolio()
    portfolio.cash_balance = 500.0

    with pytest.raises(TypeError):
        repo.save_trade(portfolio, make_buy(), risk_state="bad")

    assert repo.load_portfolio().cash_balance == 1000.0


@pytest.mark.parametrize("bad_count", [-1, 1.5, "0", True])
def test_bad_expected_count_is_rejected(repo, bad_count):
    portfolio = repo.load_portfolio()

    with pytest.raises(ValueError):
        repo.save_trade(
            portfolio, make_buy(), expected_transaction_count=bad_count
        )

    assert count_rows(repo, "transactions") == 0


# ---------- rollback ----------


def test_failure_after_portfolio_update_rolls_everything_back(repo):
    """Force the transaction INSERT to fail; the portfolio update and risk
    state written in the same database transaction must roll back."""

    connection = get_connection(repo.db_path)
    try:
        with connection:
            connection.execute(
                """
                CREATE TRIGGER block_inserts
                BEFORE INSERT ON transactions
                BEGIN
                    SELECT RAISE(ABORT, 'forced failure');
                END
                """
            )
    finally:
        connection.close()

    portfolio = repo.load_portfolio()
    portfolio.cash_balance = 399.4
    portfolio.holdings = {"BTC/USDT": 0.01}
    trade = make_buy()
    portfolio.transactions.append(trade)

    with pytest.raises(sqlite3.DatabaseError):
        repo.save_trade(
            portfolio,
            trade,
            risk_state=RiskState(DAY, 1000.0, 1000.0),
            expected_transaction_count=0,
        )

    restored = repo.load_portfolio()
    assert restored.cash_balance == 1000.0
    assert restored.holdings == {}
    assert restored.transactions == []
    assert repo.load_risk_state() == RiskState()


# ---------- stale-write / duplicate guard ----------


def test_duplicate_save_is_rejected_and_writes_nothing(repo):
    portfolio = repo.load_portfolio()
    portfolio.cash_balance = 399.4
    portfolio.holdings = {"BTC/USDT": 0.01}
    trade = make_buy()
    portfolio.transactions.append(trade)

    repo.save_trade(portfolio, trade, expected_transaction_count=0)

    with pytest.raises(StaleStateError):
        repo.save_trade(portfolio, trade, expected_transaction_count=0)

    assert count_rows(repo, "transactions") == 1


def test_out_of_date_copy_cannot_overwrite_newer_state(tmp_path):
    db_path = tmp_path / "test.db"
    app_one = PortfolioRepository(db_path)
    app_one.create_portfolio()
    app_two = PortfolioRepository(db_path)

    stale_copy = app_two.load_portfolio()

    newer = app_one.load_portfolio()
    newer.cash_balance = 399.4
    newer.holdings = {"BTC/USDT": 0.01}
    first_trade = make_buy()
    newer.transactions.append(first_trade)
    app_one.save_trade(newer, first_trade, expected_transaction_count=0)

    stale_copy.cash_balance = 700.0
    stale_copy.holdings = {"ETH/USDT": 0.15}
    second_trade = make_buy("ETH/USDT", 0.15, 2000.0, 0.3)
    stale_copy.transactions.append(second_trade)

    with pytest.raises(StaleStateError):
        app_two.save_trade(
            stale_copy, second_trade, expected_transaction_count=0
        )

    restored = app_one.load_portfolio()
    assert restored.cash_balance == 399.4
    assert restored.holdings == {"BTC/USDT": 0.01}
    assert len(restored.transactions) == 1


def test_stale_guard_also_blocks_risk_state_change(repo):
    first_portfolio = repo.load_portfolio()
    first_portfolio.cash_balance = 399.4
    first_portfolio.holdings = {"BTC/USDT": 0.01}
    trade = make_buy()
    first_portfolio.transactions.append(trade)
    repo.save_trade(
        first_portfolio,
        trade,
        risk_state=RiskState(DAY, 1000.0, 1000.0),
        expected_transaction_count=0,
    )

    with pytest.raises(StaleStateError):
        repo.save_trade(
            first_portfolio,
            trade,
            risk_state=RiskState(DAY, 1.0, 1.0),
            expected_transaction_count=0,
        )

    assert repo.load_risk_state() == RiskState(DAY, 1000.0, 1000.0)
