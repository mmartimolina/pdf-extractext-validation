"""Tests de la configuración de logs estructurados."""

import json
import logging

from pdf_validation.logging_config import JsonFormatter, configure_logging


def test_json_formatter_emits_parseable_json():
    record = logging.LogRecord(
        "pdf_validation", logging.INFO, __file__, 1, "validation_ok", (), None
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "pdf_validation"
    assert payload["message"] == "validation_ok"
    assert "timestamp" in payload


def test_configure_logging_installs_json_handler():
    configure_logging()
    root = logging.getLogger()
    assert root.handlers
    assert any(isinstance(h.formatter, JsonFormatter) for h in root.handlers)
