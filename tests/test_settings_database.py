"""Tests for the database path setting and balance validation."""

from pathlib import Path

import pytest

from config.settings import PROJECT_ROOT, Settings, load_settings


def test_database_path_is_inside_project_data_folder():
    path = load_settings().database_path

    assert path == PROJECT_ROOT / "data" / "project_quant.db"
    assert path.is_absolute()


def test_project_root_contains_config_folder():
    assert (PROJECT_ROOT / "config" / "settings.py").is_file()


def test_database_path_does_not_depend_on_working_directory(
    tmp_path, monkeypatch
):
    before = load_settings().database_path
    monkeypatch.chdir(tmp_path)

    assert load_settings().database_path == before


@pytest.mark.parametrize(
    "bad", [float("nan"), float("inf"), float("-inf"), 0, -1.0]
)
def test_bad_initial_balance_is_rejected(bad):
    with pytest.raises(ValueError):
        Settings(initial_balance_usdt=bad)


@pytest.mark.parametrize(
    "bad", ["", "../evil.db", "sub/dir.db", "/etc/passwd"]
)
def test_bad_database_filename_is_rejected(bad):
    with pytest.raises(ValueError, match="plain file name"):
        Settings(database_filename=bad)


def test_custom_plain_filename_is_accepted():
    settings = Settings(database_filename="other.db")

    assert settings.database_path.name == "other.db"
    assert isinstance(settings.database_path, Path)
