"""SQLite persistence for Project Quant portfolios."""

import math
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

from risk_management.risk_manager import RiskState
from storage.database import get_connection, initialize_database
from trading.portfolio import Portfolio, Transaction


class StaleStateError(RuntimeError):
    """Raised when saved data does not match what the caller expected."""


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

    @staticmethod
    def _write_risk_state(connection, state: RiskState) -> None:
        """Write the single risk-state row using an open connection."""

        day_text = (
            None
            if state.current_day is None
            else state.current_day.isoformat()
        )

        connection.execute(
            """
            INSERT OR REPLACE INTO risk_state (
                id,
                current_day,
                day_start_value,
                peak_portfolio_value
            )
            VALUES (1, ?, ?, ?)
            """,
            (
                day_text,
                state.day_start_value,
                state.peak_portfolio_value,
            ),
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
        *,
        risk_state: RiskState | None = None,
        expected_transaction_count: int | None = None,
    ) -> None:
        """Atomically save a portfolio update and append one transaction.

        risk_state, when given, is saved in the same database transaction.

        expected_transaction_count, when given, is the number of
        transactions the caller believes are already saved (before this
        trade). If the database disagrees, nothing is written and
        StaleStateError is raised. This blocks duplicate saves and
        overwrites from an out-of-date copy of the portfolio.
        """

        self._validate_portfolio(portfolio)
        self._validate_transaction(transaction)

        if risk_state is not None and not isinstance(risk_state, RiskState):
            raise TypeError("risk_state must be a RiskState")

        if expected_transaction_count is not None and (
            isinstance(expected_transaction_count, bool)
            or not isinstance(expected_transaction_count, int)
            or expected_transaction_count < 0
        ):
            raise ValueError(
                "expected_transaction_count must be a non-negative integer"
            )

        with closing(get_connection(self.db_path)) as connection:
            with connection:
                # Take the write lock first, so the count check and the
                # writes below cannot be interleaved with another program.
                connection.execute("BEGIN IMMEDIATE")

                if expected_transaction_count is not None:
                    saved_count = connection.execute(
                        "SELECT COUNT(*) FROM transactions"
                    ).fetchone()[0]

                    if saved_count != expected_transaction_count:
                        raise StaleStateError(
                            "Saved transaction count is "
                            f"{saved_count}, expected "
                            f"{expected_transaction_count}. "
                            "Nothing was saved."
                        )

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

                if risk_state is not None:
                    self._write_risk_state(connection, risk_state)

    def load_risk_state(self) -> RiskState:
        """Restore the saved risk state.

        Returns a fresh RiskState if none has been saved. A damaged saved
        row raises ValueError instead of being trusted.
        """

        with closing(get_connection(self.db_path)) as connection:
            row = connection.execute(
                """
                SELECT current_day, day_start_value, peak_portfolio_value
                FROM risk_state
                WHERE id = 1
                """
            ).fetchone()

        if row is None:
            return RiskState()

        try:
            day_text = row["current_day"]
            current_day = (
                None if day_text is None else date.fromisoformat(day_text)
            )

            return RiskState(
                current_day=current_day,
                day_start_value=row["day_start_value"],
                peak_portfolio_value=row["peak_portfolio_value"],
            )
        except (ValueError, TypeError) as error:
            raise ValueError("Saved risk state is damaged") from error

    def save_risk_state(self, state: RiskState) -> None:
        """Save the risk state on its own."""

        if not isinstance(state, RiskState):
            raise TypeError("state must be a RiskState")

        with closing(get_connection(self.db_path)) as connection:
            with connection:
                self._write_risk_state(connection, state)

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
