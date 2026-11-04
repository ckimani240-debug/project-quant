"""Virtual portfolio models for Project Quant.

This module tracks paper-trading balances only. It does not place orders.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Transaction:
    """A recorded virtual portfolio transaction."""

    symbol: str
    side: str
    quantity: float
    price: float
    fee: float
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def total_value(self) -> float:
        """Return the transaction value before fees."""
        return self.quantity * self.price


@dataclass
class Portfolio:
    """A virtual portfolio containing cash and cryptocurrency holdings."""

    initial_balance: float = 1000.0
    cash_balance: float = field(init=False)
    holdings: dict[str, float] = field(default_factory=dict)
    transactions: list[Transaction] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.initial_balance <= 0:
            raise ValueError("Initial balance must be positive")

        self.cash_balance = self.initial_balance

    def get_holdings(self) -> dict[str, float]:
        """Return a copy of current asset quantities."""
        return self.holdings.copy()

    def get_transaction_history(self) -> list[Transaction]:
        """Return a copy of the transaction history."""
        return self.transactions.copy()

    def get_portfolio_value(self, market_prices: dict[str, float]) -> float:
        """Calculate cash plus the market value of all holdings."""
        total = self.cash_balance

        for symbol, quantity in self.holdings.items():
            if symbol not in market_prices:
                raise ValueError(f"Missing market price for {symbol}")

            price = market_prices[symbol]

            if price <= 0:
                raise ValueError(f"Invalid market price for {symbol}")

            total += quantity * price

        return total
