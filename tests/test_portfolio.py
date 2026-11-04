import pytest

from trading.portfolio import Portfolio


def test_portfolio_starts_with_1000_usdt():
    portfolio = Portfolio()
    assert portfolio.cash_balance == 1000.0


def test_portfolio_starts_with_no_holdings():
    portfolio = Portfolio()
    assert portfolio.get_holdings() == {}


def test_portfolio_starts_with_no_transactions():
    portfolio = Portfolio()
    assert portfolio.get_transaction_history() == []


def test_portfolio_value_includes_holdings():
    portfolio = Portfolio()
    portfolio.holdings = {
        "BTC/USDT": 0.01,
        "ETH/USDT": 0.5,
    }

    prices = {
        "BTC/USDT": 60000.0,
        "ETH/USDT": 2000.0,
    }

    assert portfolio.get_portfolio_value(prices) == 2600.0


def test_missing_market_price_is_rejected():
    portfolio = Portfolio()
    portfolio.holdings = {"BTC/USDT": 0.01}

    with pytest.raises(ValueError):
        portfolio.get_portfolio_value({})


def test_zero_market_price_is_rejected():
    portfolio = Portfolio()
    portfolio.holdings = {"BTC/USDT": 0.01}

    with pytest.raises(ValueError):
        portfolio.get_portfolio_value({"BTC/USDT": 0})


def test_invalid_initial_balance_is_rejected():
    with pytest.raises(ValueError):
        Portfolio(initial_balance=0)
