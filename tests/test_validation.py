"""Tests del módulo de dominio de validación de PDF."""

import pytest
from conftest import sha256_hex

from pdf_validation.checksum import checksum_hex
from pdf_validation.validation import PdfValidationError, validate_pdf

# Valor calculado con `certutil -hashfile` / `hashlib` como fuente independiente.
KNOWN_SHA256 = "31f9da27c48271724190fc0875a84fd363ff9c72ea0a03152b3b8b646579aab5"


def test_valid_pdf_is_accepted_with_sha256_checksum(valid_pdf_bytes):
    result = validate_pdf(valid_pdf_bytes, max_size_bytes=20 * 1024 * 1024)

    assert result.checksum == sha256_hex(valid_pdf_bytes)
    assert result.checksum_algorithm == "sha256"
    assert result.size_bytes == len(valid_pdf_bytes)


def test_known_content_produces_known_sha256():
    assert checksum_hex(b"%PDF-fixed content for checksum test") == KNOWN_SHA256


def test_empty_input_is_rejected():
    with pytest.raises(PdfValidationError) as exc_info:
        validate_pdf(b"", max_size_bytes=1024)
    assert exc_info.value.code == "EMPTY_PDF"


def test_input_exceeding_max_size_is_rejected():
    data = b"x" * 2048
    with pytest.raises(PdfValidationError) as exc_info:
        validate_pdf(data, max_size_bytes=1024)
    assert exc_info.value.code == "PDF_TOO_LARGE"


def test_non_pdf_bytes_are_rejected():
    with pytest.raises(PdfValidationError) as exc_info:
        validate_pdf(b"esto no es un pdf", max_size_bytes=1024)
    assert exc_info.value.code == "INVALID_PDF"


def test_header_only_is_not_enough():
    with pytest.raises(PdfValidationError) as exc_info:
        validate_pdf(b"%PDF-1.7\n", max_size_bytes=1024)
    assert exc_info.value.code == "INVALID_PDF"


def test_truncated_pdf_is_rejected(valid_pdf_bytes):
    truncated = valid_pdf_bytes[:64]
    with pytest.raises(PdfValidationError) as exc_info:
        validate_pdf(truncated, max_size_bytes=20 * 1024 * 1024)
    assert exc_info.value.code == "INVALID_PDF"


def test_pdf_without_pages_is_rejected():
    from io import BytesIO

    from pypdf import PdfWriter

    buffer = BytesIO()
    PdfWriter().write(buffer)  # PDF estructuralmente válido pero sin páginas.
    with pytest.raises(PdfValidationError) as exc_info:
        validate_pdf(buffer.getvalue(), max_size_bytes=20 * 1024 * 1024)
    assert exc_info.value.code == "INVALID_PDF"


def test_encrypted_pdf_is_rejected(encrypted_pdf_bytes):
    with pytest.raises(PdfValidationError) as exc_info:
        validate_pdf(encrypted_pdf_bytes, max_size_bytes=20 * 1024 * 1024)
    assert exc_info.value.code == "ENCRYPTED_PDF"
