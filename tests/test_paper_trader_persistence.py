"""Tests for paper trading with SQLite persistence."""

import sqlite3
from datetime import date, datetime, timezone

import pytest

from risk_management.risk_manager import RiskState
from storage.database import get_connection
from storage.portfolio_repository import (
    PortfolioRepository,
    StaleStateError,
)
from trading.paper_trader import PaperTradingEngine
from trading.portfolio import Portfolio

OLD_DAY = date(2026, 11, 1)


def make_engine(db_path):
    repository = PortfolioRepository(db_path)
    return PaperTradingEngine(repository=repository), repository


def buy_btc(engine, portfolio):
    return engine.execute_trade(
        portfolio, "BTC/USDT", "buy", 0.001, 60000, approved=True
    )


# ---------- saving and restarting ----------


def test_trade_is_saved_and_survives_restart(tmp_path):
    db_path = tmp_path / "t.db"
    engine, _ = make_engine(db_path)
    portfolio = engine.load_portfolio()

    buy_btc(engine, portfolio)

    engine2, _ = make_engine(db_path)
    restored = engine2.load_portfolio()

    assert restored.cash_balance == portfolio.cash_balance
    assert restored.holdings == {"BTC/USDT": 0.001}
    assert len(restored.transactions) == 1
    assert engine2.risk_manager.get_state() == engine.risk_manager.get_state()
    assert engine2.risk_manager.get_state().peak_portfolio_value == 1000.0


def test_restart_does_not_duplicate_history(tmp_path):
    db_path = tmp_path / "t.db"
    engine, _ = make_engine(db_path)
    portfolio = engine.load_portfolio()

    buy_btc(engine, portfolio)
    engine.execute_trade(
        portfolio, "BTC/USDT", "sell", 0.001, 61000, approved=True
    )

    engine2, _ = make_engine(db_path)
    restored = engine2.load_portfolio()

    assert len(restored.transactions) == 2
    assert restored.holdings == {}
    assert restored.cash_balance == portfolio.cash_balance


# ---------- failure leaves everything unchanged ----------


def test_failed_save_leaves_memory_database_and_risk_state_unchanged(
    tmp_path,
):
    engine, repository = make_engine(tmp_path / "t.db")
    portfolio = engine.load_portfolio()

    connection = get_connection(repository.db_path)
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

    with pytest.raises(sqlite3.DatabaseError):
        buy_btc(engine, portfolio)

    # Live memory unchanged.
    assert portfolio.cash_balance == 1000.0
    assert portfolio.holdings == {}
    assert portfolio.transactions == []
    assert engine.risk_manager.get_state() == RiskState()

    # Database unchanged.
    saved = repository.load_portfolio()
    assert saved.cash_balance == 1000.0
    assert saved.holdings == {}
    assert saved.transactions == []
    assert repository.load_risk_state() == RiskState()


def test_stale_portfolio_cannot_overwrite_newer_saved_state(tmp_path):
    db_path = tmp_path / "t.db"
    engine_a, repo_a = make_engine(db_path)
    portfolio_a = engine_a.load_portfolio()
    engine_b, _ = make_engine(db_path)
    portfolio_b = engine_b.load_portfolio()

    buy_btc(engine_a, portfolio_a)

    with pytest.raises(StaleStateError):
        engine_b.execute_trade(
            portfolio_b, "ETH/USDT", "buy", 0.1, 2000, approved=True
        )

    assert portfolio_b.cash_balance == 1000.0
    assert portfolio_b.holdings == {}
    assert portfolio_b.transactions == []
    assert engine_b.risk_manager.get_state() == RiskState()

    saved = repo_a.load_portfolio()
    assert saved.holdings == {"BTC/USDT": 0.001}
    assert len(saved.transactions) == 1


# ---------- risk limits through the trader ----------


def _setup_loss(tmp_path, cash, state):
    """Create a saved portfolio with reduced cash and a saved risk state,
    then return a NEW engine (a restart) and its portfolio."""

    db_path = tmp_path / "t.db"
    engine, repository = make_engine(db_path)
    portfolio = engine.load_portfolio()
    portfolio.cash_balance = cash
    repository.save_portfolio(portfolio)
    repository.save_risk_state(state)

    engine2, repository2 = make_engine(db_path)
    return engine2, repository2, engine2.load_portfolio()


def test_drawdown_peak_survives_restart_and_blocks_buy(tmp_path):
    engine, repository, portfolio = _setup_loss(
        tmp_path, 840.0, RiskState(OLD_DAY, 1000.0, 1000.0)
    )

    assert engine.risk_manager.peak_portfolio_value == 1000.0

    with pytest.raises(PermissionError, match="drawdown"):
        buy_btc(engine, portfolio)

    assert portfolio.cash_balance == 840.0
    assert portfolio.holdings == {}
    assert portfolio.transactions == []
    assert repository.load_portfolio().transactions == []


def test_daily_loss_blocks_buy_through_trader(tmp_path):
    today = datetime.now(timezone.utc).date()
    engine, _, portfolio = _setup_loss(
        tmp_path, 960.0, RiskState(today, 1000.0, 1000.0)
    )

    with pytest.raises(PermissionError, match="daily loss"):
        buy_btc(engine, portfolio)

    assert portfolio.cash_balance == 960.0
    assert portfolio.transactions == []


def test_blocked_buy_still_records_risk_state(tmp_path):
    engine, repository, portfolio = _setup_loss(
        tmp_path, 840.0, RiskState(OLD_DAY, 1000.0, 1000.0)
    )

    with pytest.raises(PermissionError):
        buy_btc(engine, portfolio)

    saved = repository.load_risk_state()
    assert saved.current_day == datetime.now(timezone.utc).date()
    assert saved.day_start_value == 840.0
    assert saved.peak_portfolio_value == 1000.0
    assert engine.risk_manager.get_state() == saved


def test_blocked_buy_stays_blocked_if_risk_state_save_fails(
    tmp_path, monkeypatch
):
    engine, repository, portfolio = _setup_loss(
        tmp_path, 840.0, RiskState(OLD_DAY, 1000.0, 1000.0)
    )
    before = engine.risk_manager.get_state()

    def broken_save(state):
        raise sqlite3.OperationalError("disk problem")

    monkeypatch.setattr(repository, "save_risk_state", broken_save)

    with pytest.raises(PermissionError, match="drawdown"):
        buy_btc(engine, portfolio)

    assert engine.risk_manager.get_state() == before
    assert repository.load_risk_state() == before


def test_sale_is_rejected_when_another_holding_has_no_price():
    engine = PaperTradingEngine()
    portfolio = Portfolio()
    portfolio.holdings["BTC/USDT"] = 0.001
    portfolio.holdings["ETH/USDT"] = 0.1

    with pytest.raises(ValueError, match="Missing market price"):
        engine.execute_trade(
            portfolio, "BTC/USDT", "sell", 0.001, 61000, approved=True
        )

    assert portfolio.holdings == {"BTC/USDT": 0.001, "ETH/USDT": 0.1}
    assert portfolio.transactions == []


def test_load_portfolio_requires_a_repository():
    with pytest.raises(RuntimeError):
        PaperTradingEngine().load_portfolio()


def test_damaged_risk_state_stops_loading(tmp_path):
    engine, repository = make_engine(tmp_path / "t.db")
    engine.load_portfolio()

    connection = get_connection(repository.db_path)
    try:
        with connection:
            connection.execute(
                "INSERT OR REPLACE INTO risk_state "
                "(id, current_day, day_start_value, peak_portfolio_value) "
                "VALUES (1, 'bad', 1000.0, 1000.0)"
            )
    finally:
        connection.close()

    engine2, _ = make_engine(repository.db_path)

    with pytest.raises(ValueError, match="damaged"):
        engine2.load_portfolio()
