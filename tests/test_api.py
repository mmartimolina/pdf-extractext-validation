"""Tests de integración del contrato HTTP de la aplicación FastAPI."""

import pytest
from conftest import sha256_hex
from fastapi.testclient import TestClient

from pdf_validation.app import create_app

PDF_HEADERS = {"Content-Type": "application/pdf"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("MAX_FILE_SIZE_MIB", raising=False)
    return TestClient(create_app())


def test_health_live(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_health_ready(client):
    response = client.get("/health/ready")
    assert response.status_code == 200


def test_validate_valid_pdf_returns_checksum(client, valid_pdf_bytes):
    response = client.post("/validate", content=valid_pdf_bytes, headers=PDF_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["checksum"] == sha256_hex(valid_pdf_bytes)
    assert body["checksum_algorithm"] == "sha256"
    assert body["file_size_bytes"] == len(valid_pdf_bytes)


def test_validate_rejects_wrong_content_type(client, valid_pdf_bytes):
    response = client.post(
        "/validate", content=valid_pdf_bytes, headers={"Content-Type": "text/plain"}
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_validate_rejects_empty_body(client):
    response = client.post("/validate", content=b"", headers=PDF_HEADERS)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMPTY_PDF"


def test_validate_rejects_oversized_file():
    from pdf_validation.config import Settings

    app = create_app(Settings(max_file_size_bytes=1024))
    oversized = b"x" * 2048
    response = TestClient(app).post("/validate", content=oversized, headers=PDF_HEADERS)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PDF_TOO_LARGE"


def test_validate_rejects_non_pdf(client):
    response = client.post("/validate", content=b"hola", headers=PDF_HEADERS)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PDF"


def test_validate_rejects_encrypted_pdf(client, encrypted_pdf_bytes):
    response = client.post(
        "/validate", content=encrypted_pdf_bytes, headers=PDF_HEADERS
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ENCRYPTED_PDF"


def test_response_includes_request_id(client):
    response = client.get("/health/live")
    assert "x-request-id" in response.headers


def test_incoming_request_id_is_propagated(client):
    response = client.get("/health/live", headers={"X-Request-ID": "req-123"})
    assert response.headers["x-request-id"] == "req-123"


def test_failed_validation_is_logged_without_pdf_bytes(client, caplog):
    with caplog.at_level("WARNING", logger="pdf_validation"):
        client.post("/validate", content=b"no pdf", headers=PDF_HEADERS)
    messages = [record.getMessage() for record in caplog.records]
    assert any("INVALID_PDF" in message for message in messages)
    assert not any("no pdf" in message for message in messages)
