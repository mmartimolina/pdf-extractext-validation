"""Tests de configuración por variables de entorno."""

import pytest

from pdf_validation.config import Settings

DEFAULT_MAX_BYTES = 20 * 1024 * 1024


def test_default_max_file_size_is_20_mib(monkeypatch):
    monkeypatch.delenv("MAX_FILE_SIZE_MIB", raising=False)
    settings = Settings.from_env()
    assert settings.max_file_size_bytes == DEFAULT_MAX_BYTES


def test_max_file_size_configurable_via_env(monkeypatch):
    monkeypatch.setenv("MAX_FILE_SIZE_MIB", "5")
    settings = Settings.from_env()
    assert settings.max_file_size_bytes == 5 * 1024 * 1024


def test_invalid_max_file_size_is_rejected(monkeypatch):
    monkeypatch.setenv("MAX_FILE_SIZE_MIB", "cero")
    with pytest.raises(ValueError):
        Settings.from_env()


def test_non_positive_max_file_size_is_rejected(monkeypatch):
    monkeypatch.setenv("MAX_FILE_SIZE_MIB", "0")
    with pytest.raises(ValueError):
        Settings.from_env()
