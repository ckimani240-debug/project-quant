"""SQLite persistence for Project Quant portfolios."""

import math
from contextlib import closing
from datetime import datetime
from pathlib import Path

from storage.database import get_connection, initialize_database
from trading.portfolio import Portfolio, Transaction


class PortfolioRepository:
    """Create, save and restore virtual portfolios using SQLite."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_database(self.db_path)

    @staticmethod
    def _validate_portfolio(portfolio: Portfolio) -> None:
        """Validate portfolio balances and holdings."""

        if (
            not math.isfinite(portfolio.initial_balance)
            or portfolio.initial_balance <= 0
        ):
            raise ValueError(
                "Initial balance must be positive and finite"
            )

        if (
            not math.isfinite(portfolio.cash_balance)
            or portfolio.cash_balance < 0
        ):
            raise ValueError(
                "Cash balance must be finite and non-negative"
            )

        for symbol, quantity in portfolio.holdings.items():
            if (
                not isinstance(symbol, str)
                or not symbol
                or not math.isfinite(quantity)
                or quantity <= 0
            ):
                raise ValueError("Invalid holding")

    @staticmethod
    def _validate_transaction(transaction: Transaction) -> None:
        """Validate a simulated transaction before persistence."""

        if (
            not isinstance(transaction.symbol, str)
            or not transaction.symbol
            or transaction.side not in ("buy", "sell")
            or not math.isfinite(transaction.quantity)
            or transaction.quantity <= 0
            or not math.isfinite(transaction.price)
            or transaction.price <= 0
            or not math.isfinite(transaction.fee)
            or transaction.fee < 0
            or not isinstance(transaction.timestamp, datetime)
        ):
            raise ValueError("Invalid transaction")

    @staticmethod
    def _update_portfolio(
        connection,
        portfolio: Portfolio,
    ) -> None:
        """Update an existing portfolio and its holdings."""

        cursor = connection.execute(
            """
            UPDATE portfolio_state
            SET
                initial_balance = ?,
                cash_balance = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (
                portfolio.initial_balance,
                portfolio.cash_balance,
            ),
        )

        if cursor.rowcount != 1:
            raise LookupError("No saved portfolio exists")

        connection.execute("DELETE FROM holdings")

        connection.executemany(
            """
            INSERT INTO holdings (symbol, quantity)
            VALUES (?, ?)
            """,
            list(portfolio.holdings.items()),
        )

    def create_portfolio(
        self,
        initial_balance: float = 1000.0,
    ) -> Portfolio:
        """Create a portfolio if none exists; never reset an existing one."""

        if (
            not math.isfinite(initial_balance)
            or initial_balance <= 0
        ):
            raise ValueError(
                "Initial balance must be positive and finite"
            )

        with closing(get_connection(self.db_path)) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO portfolio_state (
                        id, initial_balance, cash_balance
                    )
                    VALUES (1, ?, ?)
                    """,
                    (initial_balance, initial_balance),
                )

        return self.load_portfolio()

    def save_portfolio(self, portfolio: Portfolio) -> None:
        """Save balances and holdings without modifying trade history."""

        self._validate_portfolio(portfolio)

        with closing(get_connection(self.db_path)) as connection:
            with connection:
                self._update_portfolio(connection, portfolio)

    def save_trade(
        self,
        portfolio: Portfolio,
        transaction: Transaction,
    ) -> None:
        """Atomically save a portfolio update and append one transaction."""

        self._validate_portfolio(portfolio)
        self._validate_transaction(transaction)

        with closing(get_connection(self.db_path)) as connection:
            with connection:
                self._update_portfolio(connection, portfolio)

                connection.execute(
                    """
                    INSERT INTO transactions (
                        symbol,
                        side,
                        quantity,
                        price,
                        fee,
                        timestamp
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        transaction.symbol,
                        transaction.side,
                        transaction.quantity,
                        transaction.price,
                        transaction.fee,
                        transaction.timestamp.isoformat(),
                    ),
                )

    def load_portfolio(self) -> Portfolio:
        """Restore the saved portfolio, holdings and transactions."""

        with closing(get_connection(self.db_path)) as connection:
            state = connection.execute(
                """
                SELECT initial_balance, cash_balance
                FROM portfolio_state
                WHERE id = 1
                """
            ).fetchone()

            if state is None:
                raise LookupError("No saved portfolio exists")

            portfolio = Portfolio(
                initial_balance=state["initial_balance"]
            )
            portfolio.cash_balance = state["cash_balance"]

            holdings = connection.execute(
                "SELECT symbol, quantity FROM holdings"
            ).fetchall()

            portfolio.holdings = {
                row["symbol"]: row["quantity"]
                for row in holdings
            }

            transactions = connection.execute(
                """
                SELECT symbol, side, quantity, price, fee, timestamp
                FROM transactions
                ORDER BY id
                """
            ).fetchall()

            portfolio.transactions = [
                Transaction(
                    symbol=row["symbol"],
                    side=row["side"],
                    quantity=row["quantity"],
                    price=row["price"],
                    fee=row["fee"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                )
                for row in transactions
            ]

            return portfolio
