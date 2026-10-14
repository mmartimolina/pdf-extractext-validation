"""Fixtures compartidos para los tests del microservicio de validación."""

import hashlib
from io import BytesIO

import pytest
from pypdf import PdfWriter


def _build_pdf(encrypted: bool = False, empty_page: bool = True) -> bytes:
    """Genera un PDF binario válido y determinista mediante pypdf."""
    buffer = BytesIO()
    writer = PdfWriter()
    if empty_page:
        writer.add_blank_page(width=72, height=72)
    if encrypted:
        writer.encrypt(user_password="test-password")
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def valid_pdf_bytes() -> bytes:
    """PDF válido sin texto extraíble (página en blanco)."""
    return _build_pdf()


@pytest.fixture
def encrypted_pdf_bytes() -> bytes:
    """PDF válido pero cifrado con contraseña."""
    return _build_pdf(encrypted=True)


def sha256_hex(data: bytes) -> str:
    """Checksum SHA-256 esperado, calculado de forma independiente."""
    return hashlib.sha256(data).hexdigest()
