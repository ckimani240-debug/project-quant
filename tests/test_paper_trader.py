import pytest

from trading.portfolio import Portfolio
from trading.paper_trader import PaperTradingEngine


@pytest.fixture
def setup_trader():
    return PaperTradingEngine(), Portfolio()


def test_unapproved_trade_is_rejected(setup_trader):
    engine, portfolio = setup_trader

    with pytest.raises(PermissionError):
        engine.execute_trade(
            portfolio, "BTC/USDT", "buy", 0.001, 60000
        )

    assert portfolio.cash_balance == 1000.0
    assert portfolio.holdings == {}
    assert portfolio.transactions == []


def test_approved_btc_purchase(setup_trader):
    engine, portfolio = setup_trader

    transaction = engine.execute_trade(
        portfolio, "BTC/USDT", "buy", 0.001, 60000,
        approved=True,
    )

    assert transaction.side == "buy"
    assert portfolio.holdings["BTC/USDT"] == 0.001
    assert portfolio.cash_balance < 1000.0
    assert len(portfolio.transactions) == 1


def test_purchase_includes_fee_and_slippage(setup_trader):
    engine, portfolio = setup_trader

    transaction = engine.execute_trade(
        portfolio, "BTC/USDT", "buy", 0.001, 60000,
        approved=True,
    )

    expected_price = 60000 * (1 + engine.settings.slippage_rate)
    expected_fee = 0.001 * expected_price * engine.settings.fee_rate

    assert transaction.price == pytest.approx(expected_price)
    assert transaction.fee == pytest.approx(expected_fee)
    assert portfolio.cash_balance == pytest.approx(
        1000 - (0.001 * expected_price) - expected_fee
    )


def test_eth_purchase(setup_trader):
    engine, portfolio = setup_trader

    engine.execute_trade(
        portfolio, "ETH/USDT", "buy", 0.1, 2000,
        approved=True,
    )

    assert portfolio.holdings["ETH/USDT"] == 0.1


def test_sale_updates_cash_and_holdings(setup_trader):
    engine, portfolio = setup_trader

    engine.execute_trade(
        portfolio, "BTC/USDT", "buy", 0.001, 60000,
        approved=True,
    )

    engine.execute_trade(
        portfolio, "BTC/USDT", "sell", 0.001, 61000,
        approved=True,
    )

    assert "BTC/USDT" not in portfolio.holdings
    assert portfolio.cash_balance > 1000.0
    assert len(portfolio.transactions) == 2


def test_insufficient_cash_is_rejected(setup_trader):
    engine, portfolio = setup_trader

    with pytest.raises(ValueError, match="Insufficient virtual cash"):
        engine.execute_trade(
            portfolio, "BTC/USDT", "buy", 1, 60000,
            approved=True,
        )

    assert portfolio.cash_balance == 1000.0
    assert portfolio.holdings == {}


def test_insufficient_holdings_is_rejected(setup_trader):
    engine, portfolio = setup_trader

    with pytest.raises(ValueError, match="Insufficient virtual holdings"):
        engine.execute_trade(
            portfolio, "BTC/USDT", "sell", 0.001, 60000,
            approved=True,
        )

    assert portfolio.cash_balance == 1000.0
    assert portfolio.transactions == []


@pytest.mark.parametrize("symbol", ["DOGE/USDT", "SOL/USDT"])
def test_unsupported_asset_is_rejected(setup_trader, symbol):
    engine, portfolio = setup_trader

    with pytest.raises(ValueError, match="Unsupported trading symbol"):
        engine.execute_trade(
            portfolio, symbol, "buy", 1, 1,
            approved=True,
        )


@pytest.mark.parametrize("price", [0, -1, float("inf"), float("nan")])
def test_invalid_price_is_rejected(setup_trader, price):
    engine, portfolio = setup_trader

    with pytest.raises(ValueError):
        engine.execute_trade(
            portfolio, "BTC/USDT", "buy", 0.001, price,
            approved=True,
        )


@pytest.mark.parametrize("quantity", [0, -1, float("inf"), float("nan")])
def test_invalid_quantity_is_rejected(setup_trader, quantity):
    engine, portfolio = setup_trader

    with pytest.raises(ValueError):
        engine.execute_trade(
            portfolio, "BTC/USDT", "buy", quantity, 60000,
            approved=True,
        )


def test_invalid_trade_side_is_rejected(setup_trader):
    engine, portfolio = setup_trader

    with pytest.raises(ValueError, match="Side must be"):
        engine.execute_trade(
            portfolio, "BTC/USDT", "hold", 0.001, 60000,
            approved=True,
        )
