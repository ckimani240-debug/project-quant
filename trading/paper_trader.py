"""Approval-controlled paper-trading engine.

This module only changes the local virtual portfolio.
It does not connect to an exchange or place real orders.
"""

import math

from config.settings import load_settings
from trading.portfolio import Portfolio, Transaction


class PaperTradingEngine:
    """Execute approved simulated trades against a virtual portfolio."""

    def __init__(self) -> None:
        self.settings = load_settings()

    def execute_trade(
        self,
        portfolio: Portfolio,
        symbol: str,
        side: str,
        quantity: float,
        market_price: float,
        *,
        approved: bool = False,
    ) -> Transaction:
        """Execute one approved virtual buy or sell."""

        if approved is not True:
            raise PermissionError("Trade rejected: explicit approval required")

        if symbol not in self.settings.symbols:
            raise ValueError(f"Unsupported trading symbol: {symbol}")

        if side not in ("buy", "sell"):
            raise ValueError("Side must be 'buy' or 'sell'")

        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("Quantity must be a positive finite number")

        if not math.isfinite(market_price) or market_price <= 0:
            raise ValueError("Market price must be a positive finite number")

        # Simulate slippage against the trader.
        if side == "buy":
            execution_price = market_price * (
                1 + self.settings.slippage_rate
            )
        else:
            execution_price = market_price * (
                1 - self.settings.slippage_rate
            )

        trade_value = quantity * execution_price
        fee = trade_value * self.settings.fee_rate

        if side == "buy":
            total_cost = trade_value + fee

            if total_cost > portfolio.cash_balance:
                raise ValueError("Insufficient virtual cash for this purchase")

            portfolio.cash_balance -= total_cost
            portfolio.holdings[symbol] = (
                portfolio.holdings.get(symbol, 0.0) + quantity
            )

        else:
            current_quantity = portfolio.holdings.get(symbol, 0.0)

            if quantity > current_quantity:
                raise ValueError("Insufficient virtual holdings for this sale")

            net_proceeds = trade_value - fee
            portfolio.cash_balance += net_proceeds

            remaining = current_quantity - quantity

            if math.isclose(remaining, 0.0, abs_tol=1e-12):
                portfolio.holdings.pop(symbol)
            else:
                portfolio.holdings[symbol] = remaining

        transaction = Transaction(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=execution_price,
            fee=fee,
        )

        portfolio.transactions.append(transaction)

        return transaction
