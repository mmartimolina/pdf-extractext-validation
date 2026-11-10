"""Aplicación FastAPI del microservicio de validación de PDF."""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from pdf_validation.checksum import CHECKSUM_ALGORITHM
from pdf_validation.consul import ConsulRegistration
from pdf_validation.config import Settings
from pdf_validation.schemas import (
    ErrorResponse,
    HealthResponse,
    ValidationSuccessResponse,
)
from pdf_validation.validation import PdfValidationError, validate_pdf

logger = logging.getLogger("pdf_validation")

_ERROR_STATUS = {
    "EMPTY_PDF": 400,
    "UNSUPPORTED_MEDIA_TYPE": 415,
    "PDF_TOO_LARGE": 413,
    "INVALID_PDF": 422,
    "ENCRYPTED_PDF": 422,
}


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Propaga ``X-Request-ID`` entrante o genera uno nuevo por solicitud."""

    async def dispatch(self, request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def _error_response(code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=_ERROR_STATUS[code],
        content={"error": {"code": code, "message": message}},
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    consul = ConsulRegistration("pdf-validation", 8000, "/health/ready")
    await consul.register()
    try:
        yield
    finally:
        await consul.deregister()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construye la aplicación FastAPI con la configuración indicada.

    Args:
        settings: configuración explícita; si se omite se lee del entorno.
    """
    if settings is None:
        settings = Settings.from_env()

    app = FastAPI(
        title="pdf-validation",
        summary="Microservicio de validación de archivos PDF.",
        version="0.1.0",
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.add_middleware(RequestIdMiddleware)

    @app.get("/health/live", response_model=HealthResponse, summary="Liveness probe")
    async def health_live() -> HealthResponse:
        """Indica que el proceso está vivo."""
        return HealthResponse(status="alive")

    @app.get("/health/ready", response_model=HealthResponse, summary="Readiness probe")
    async def health_ready() -> HealthResponse:
        """Indica que la aplicación está lista para recibir solicitudes."""
        return HealthResponse(status="ready")

    @app.post(
        "/validate",
        response_model=ValidationSuccessResponse,
        summary="Valida un PDF recibido como cuerpo binario",
        responses={
            400: {"model": ErrorResponse, "description": "Cuerpo vacío."},
            413: {
                "model": ErrorResponse,
                "description": "Archivo excede el tamaño máximo.",
            },
            415: {"model": ErrorResponse, "description": "Content-Type no soportado."},
            422: {
                "model": ErrorResponse,
                "description": "PDF inválido, corrupto o cifrado.",
            },
        },
    )
    async def validate(request: Request) -> ValidationSuccessResponse | JSONResponse:
        """Valida los bytes de un PDF y devuelve el checksum SHA-256 del contenido."""
        content_type = request.headers.get("content-type", "").split(";")[0].strip()
        if content_type != "application/pdf":
            return _error_response(
                "UNSUPPORTED_MEDIA_TYPE",
                "Se requiere Content-Type application/pdf.",
            )

        data = await request.body()
        try:
            report = validate_pdf(data, settings.max_file_size_bytes)
        except PdfValidationError as exc:
            logger.warning(
                "validation_failed request_id=%s code=%s size=%d",
                request.state.request_id,
                exc.code,
                len(data),
            )
            return _error_response(exc.code, exc.message)

        logger.info(
            "validation_ok request_id=%s size=%d checksum=%s algorithm=%s",
            request.state.request_id,
            report.size_bytes,
            report.checksum,
            report.checksum_algorithm,
        )
        return ValidationSuccessResponse(
            file_size_bytes=report.size_bytes,
            checksum=report.checksum,
            checksum_algorithm=CHECKSUM_ALGORITHM,
        )

    return app
