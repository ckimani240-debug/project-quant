"""Tests for the Project Quant SQLite database."""

import sqlite3

from storage.database import initialize_database


def test_database_creates_required_tables(tmp_path):
    db_path = tmp_path / "test_quant.db"

    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    assert {
        "schema_version",
        "portfolio_state",
        "holdings",
        "transactions",
        "risk_state",
    }.issubset(tables)


def test_database_records_schema_version(tmp_path):
    db_path = tmp_path / "test_quant.db"

    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        version = connection.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()[0]

    assert version == 1


def test_database_initialization_is_repeatable(tmp_path):
    db_path = tmp_path / "test_quant.db"

    initialize_database(db_path)
    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        version_count = connection.execute(
            "SELECT COUNT(*) FROM schema_version"
        ).fetchone()[0]

    assert version_count == 1


def test_database_rejects_invalid_holding_quantity(tmp_path):
    db_path = tmp_path / "test_quant.db"
    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        try:
            connection.execute(
                "INSERT INTO holdings (symbol, quantity) VALUES (?, ?)",
                ("BTC/USDT", -1),
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("Invalid holding quantity was accepted")
