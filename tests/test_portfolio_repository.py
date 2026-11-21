from datetime import datetime, timezone

import pytest

from storage.portfolio_repository import PortfolioRepository
from trading.portfolio import Transaction


def test_create_portfolio_starts_with_1000_usdt(tmp_path):
    repository = PortfolioRepository(tmp_path / "test.db")

    portfolio = repository.create_portfolio()

    assert portfolio.initial_balance == 1000.0
    assert portfolio.cash_balance == 1000.0
    assert portfolio.holdings == {}


def test_existing_portfolio_is_not_reset(tmp_path):
    repository = PortfolioRepository(tmp_path / "test.db")

    repository.create_portfolio(initial_balance=1000.0)
    portfolio = repository.create_portfolio(initial_balance=2000.0)

    assert portfolio.initial_balance == 1000.0
    assert portfolio.cash_balance == 1000.0


def test_load_portfolio_requires_existing_portfolio(tmp_path):
    repository = PortfolioRepository(tmp_path / "test.db")

    with pytest.raises(LookupError):
        repository.load_portfolio()


def test_portfolio_survives_restart(tmp_path):
    db_path = tmp_path / "test.db"
    repository = PortfolioRepository(db_path)
    portfolio = repository.create_portfolio()

    timestamp = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)

    portfolio.cash_balance = 400.0
    portfolio.holdings = {"BTC/USDT": 0.01}

    transaction = Transaction(
        symbol="BTC/USDT",
        side="buy",
        quantity=0.01,
        price=60000.0,
        fee=6.0,
        timestamp=timestamp,
    )

    portfolio.transactions.append(transaction)
    repository.save_trade(portfolio, transaction)

    new_repository = PortfolioRepository(db_path)
    restored = new_repository.load_portfolio()

    assert restored.initial_balance == 1000.0
    assert restored.cash_balance == 400.0
    assert restored.holdings == {"BTC/USDT": 0.01}
    assert len(restored.transactions) == 1
    assert restored.transactions[0].symbol == "BTC/USDT"
    assert restored.transactions[0].timestamp == timestamp


def test_invalid_save_does_not_corrupt_saved_portfolio(tmp_path):
    repository = PortfolioRepository(tmp_path / "test.db")
    portfolio = repository.create_portfolio()

    portfolio.cash_balance = 750.0
    repository.save_portfolio(portfolio)

    portfolio.cash_balance = -100.0

    with pytest.raises(ValueError):
        repository.save_portfolio(portfolio)

    restored = repository.load_portfolio()

    assert restored.cash_balance == 750.0


def test_save_portfolio_preserves_existing_transactions(tmp_path):
    repository = PortfolioRepository(tmp_path / "test.db")
    portfolio = repository.create_portfolio()

    timestamp = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)

    transaction = Transaction(
        symbol="BTC/USDT",
        side="buy",
        quantity=0.01,
        price=60000.0,
        fee=6.0,
        timestamp=timestamp,
    )

    portfolio.cash_balance = 400.0
    portfolio.holdings = {"BTC/USDT": 0.01}
    portfolio.transactions.append(transaction)

    repository.save_trade(portfolio, transaction)

    portfolio.cash_balance = 350.0
    portfolio.transactions.clear()

    repository.save_portfolio(portfolio)

    restored = repository.load_portfolio()

    assert restored.cash_balance == 350.0
    assert len(restored.transactions) == 1
    assert restored.transactions[0].timestamp == timestamp
