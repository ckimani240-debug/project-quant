import pytest

from config.settings import Settings, REAL_MONEY_TRADING, load_settings


def test_default_starting_balance():
    settings = load_settings()
    assert settings.initial_balance_usdt == 1000.0


def test_initial_symbols_are_btc_and_eth():
    settings = load_settings()
    assert settings.symbols == ("BTC/USDT", "ETH/USDT")


def test_real_money_trading_is_disabled():
    settings = load_settings()
    assert REAL_MONEY_TRADING is False
    assert settings.real_money_trading is False


def test_leverage_is_not_enabled():
    from config.settings import LEVERAGE_ENABLED
    assert LEVERAGE_ENABLED is False


def test_invalid_balance_is_rejected():
    with pytest.raises(ValueError):
        Settings(initial_balance_usdt=0)


def test_invalid_fee_is_rejected():
    with pytest.raises(ValueError):
        Settings(fee_rate=0.1)


def test_risk_limits_have_expected_defaults():
    settings = load_settings()
    assert settings.max_portfolio_exposure == 0.5
    assert settings.max_risk_per_trade == 0.01
    assert settings.max_daily_loss == 0.03
    assert settings.max_drawdown == 0.15
