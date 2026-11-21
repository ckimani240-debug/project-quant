"""Approval-controlled paper-trading engine.

This module only changes the local virtual portfolio.
It does not connect to an exchange or place real orders.
"""

import copy
import math
import sqlite3

from config.settings import Settings, load_settings
from risk_management.risk_manager import RiskManager
from storage.portfolio_repository import PortfolioRepository
from trading.portfolio import Portfolio, Transaction


class PaperTradingEngine:
    """Execute approved simulated trades with risk checks.

    With a repository, every trade is saved atomically (portfolio,
    transaction and risk state together). The live portfolio and the
    risk manager are updated only after the save succeeds.
    Without a repository, trades affect memory only.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        risk_manager: RiskManager | None = None,
        repository: PortfolioRepository | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.risk_manager = risk_manager or RiskManager(self.settings)
        self.repository = repository

    def load_portfolio(self) -> Portfolio:
        """Load the saved portfolio and risk state (creating if needed).

        An existing portfolio is never reset. A damaged saved risk state
        raises ValueError, so trading stops instead of continuing blind.
        """

        if self.repository is None:
            raise RuntimeError("No repository is configured")

        portfolio = self.repository.create_portfolio(
            self.settings.initial_balance_usdt
        )
        self.risk_manager.commit_state(self.repository.load_risk_state())

        return portfolio

    def _record_state_after_block(self, state) -> None:
        """Remember the risk state even though a purchase was blocked.

        The blocked purchase is rejected either way. If the state cannot
        be saved, the in-memory state is left unchanged to match the
        database.
        """

        try:
            if self.repository is not None:
                self.repository.save_risk_state(state)

            self.risk_manager.commit_state(state)
        except sqlite3.Error:
            pass

    def execute_trade(
        self,
        portfolio: Portfolio,
        symbol: str,
        side: str,
        quantity: float,
        market_price: float,
        *,
        approved: bool = False,
        market_prices: dict[str, float] | None = None,
    ) -> Transaction:
        """Execute one approved virtual buy or sell.

        market_prices supplies current prices for other existing holdings.
        The traded symbol's supplied market_price takes precedence.
        """

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

        # Prepare current prices for every asset already held.
        prices = dict(market_prices or {})

        if symbol in portfolio.holdings:
            prices[symbol] = market_price

        for held_symbol in portfolio.holdings:
            if held_symbol not in prices:
                raise ValueError(
                    f"Missing market price for existing holding: {held_symbol}. "
                    "Supply it through market_prices."
                )

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

        # All changes are made on a copy. The live portfolio is touched
        # only after everything (including the database save) succeeds.
        working = copy.deepcopy(portfolio)

        if side == "buy":
            total_cost = trade_value + fee

            if total_cost > portfolio.cash_balance:
                raise ValueError("Insufficient virtual cash for this purchase")

            # Assess risk without storing anything yet.
            assessment, proposed_state = self.risk_manager.evaluate(
                portfolio,
                prices,
                additional_position_value=trade_value,
            )

            if not assessment.can_open_trade:
                self._record_state_after_block(proposed_state)
                raise PermissionError(
                    "Purchase blocked by risk manager: "
                    + "; ".join(assessment.reasons)
                )

            transaction = Transaction(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=execution_price,
                fee=fee,
            )

            working.cash_balance -= total_cost
            working.holdings[symbol] = (
                working.holdings.get(symbol, 0.0) + quantity
            )

        else:
            current_quantity = portfolio.holdings.get(symbol, 0.0)

            if quantity > current_quantity:
                raise ValueError("Insufficient virtual holdings for this sale")

            # A sale is never blocked by a risk limit. It is still
            # rejected if a held asset's price is missing or invalid.
            _, proposed_state = self.risk_manager.evaluate(portfolio, prices)

            transaction = Transaction(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=execution_price,
                fee=fee,
            )

            net_proceeds = trade_value - fee
            working.cash_balance += net_proceeds

            remaining = current_quantity - quantity

            if math.isclose(remaining, 0.0, abs_tol=1e-12):
                working.holdings.pop(symbol)
            else:
                working.holdings[symbol] = remaining

        working.transactions.append(transaction)

        # Save everything in one database transaction. If this raises,
        # nothing below runs and the live state stays unchanged.
        if self.repository is not None:
            self.repository.save_trade(
                working,
                transaction,
                risk_state=proposed_state,
                expected_transaction_count=len(portfolio.transactions),
            )

        # The save succeeded (or no repository is used): update live state.
        portfolio.cash_balance = working.cash_balance
        portfolio.holdings.clear()
        portfolio.holdings.update(working.holdings)
        portfolio.transactions.append(transaction)
        self.risk_manager.commit_state(proposed_state)

        return transaction
