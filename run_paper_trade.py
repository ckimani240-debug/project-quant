
"""Read-only status viewer for Project Quant."""

import sqlite3
from pathlib import Path

from config.settings import load_settings


def main() -> None:
    settings = load_settings()
    database_path = settings.database_path

    print("\n" + "=" * 48)
    print("             PROJECT QUANT")
    print("          PAPER TRADING STATUS")
    print("=" * 48)

    if not database_path.is_file():
        print("\nDatabase not found:", database_path)
        print("No database was created or modified.")
        return

    # Open the existing database strictly in read-only mode.
    database_uri = database_path.resolve().as_uri() + "?mode=ro"

    try:
        with sqlite3.connect(database_uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row

            portfolio = connection.execute(
                """
                SELECT initial_balance, cash_balance
                FROM portfolio_state
                WHERE id = 1
                """
            ).fetchone()

            if portfolio is None:
                print("\nNo saved virtual portfolio exists.")
                return

            holdings = connection.execute(
                """
                SELECT symbol, quantity
                FROM holdings
                ORDER BY symbol
                """
            ).fetchall()

            transactions = connection.execute(
                """
                SELECT symbol, side, quantity, price, fee, timestamp
                FROM transactions
                ORDER BY id
                """
            ).fetchall()

            risk = connection.execute(
                """
                SELECT current_day, day_start_value,
                       peak_portfolio_value
                FROM risk_state
                WHERE id = 1
                """
            ).fetchone()

    except sqlite3.Error as error:
        print("\nDatabase reading error:", error)
        return

    print("\nVIRTUAL PORTFOLIO")
    print("-" * 48)
    print(f"Initial balance:  {portfolio['initial_balance']:,.2f} USDT")
    print(f"Available cash:   {portfolio['cash_balance']:,.2f} USDT")
    print(f"Open holdings:    {len(holdings)}")
    print(f"Transactions:     {len(transactions)}")

    print("\nHOLDINGS")
    print("-" * 48)

    if holdings:
        for holding in holdings:
            print(
                f"{holding['symbol']}: "
                f"{holding['quantity']:.8f}"
            )
    else:
        print("No open cryptocurrency holdings.")

    print("\nTRANSACTION HISTORY")
    print("-" * 48)

    if transactions:
        for trade in transactions:
            print(
                f"{trade['timestamp']} | "
                f"{trade['side'].upper()} "
                f"{trade['quantity']:.8f} {trade['symbol']} "
                f"@ {trade['price']:.4f} USDT | "
                f"Fee: {trade['fee']:.4f} USDT"
            )
    else:
        print("No transactions recorded.")

    print("\nRISK MONITORING")
    print("-" * 48)

    if risk is None or risk["current_day"] is None:
        print("No risk assessment has been recorded yet.")
    else:
        print(f"Monitoring day (UTC): {risk['current_day']}")
        print(f"Day-start value:       {risk['day_start_value']:.2f} USDT")
        print(f"Peak portfolio value:  {risk['peak_portfolio_value']:.2f} USDT")

    print("\nCONFIGURED RISK LIMITS")
    print("-" * 48)
    print(f"Maximum exposure: {settings.max_portfolio_exposure:.0%}")
    print(f"Maximum daily loss: {settings.max_daily_loss:.0%}")
    print(f"Maximum drawdown: {settings.max_drawdown:.0%}")

    print("\nSAFETY STATUS")
    print("-" * 48)
    print("Real-money trading: DISABLED")
    print("Leverage and futures: DISABLED")
    print("Automatic execution: DISABLED")
    print("Database access: READ ONLY")

    print("\n" + "=" * 48)
    print("       RESEARCH BEFORE RETURNS")
    print("=" * 48)


if __name__ == "__main__":
    main()
