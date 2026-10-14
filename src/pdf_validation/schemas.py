"""Esquemas del contrato HTTP."""

from pydantic import BaseModel, Field

from pdf_validation.checksum import CHECKSUM_ALGORITHM


class HealthResponse(BaseModel):
    """Respuesta de los healthchecks."""

    status: str


class ValidationSuccessResponse(BaseModel):
    """Respuesta exitosa de ``POST /validate``.

    El checksum identifica el contenido binario exacto aceptado. La política de
    persistencia y deduplicación corresponde al orquestador.
    """

    valid: bool = True
    file_size_bytes: int = Field(description="Tamaño del archivo recibido, en bytes.")
    checksum: str = Field(description="Checksum del contenido binario, en hexadecimal.")
    checksum_algorithm: str = Field(
        default=CHECKSUM_ALGORITHM, description="Algoritmo del checksum."
    )


class ErrorDetail(BaseModel):
    """Detalle estructurado de un error."""

    code: str = Field(description="Código identificable y estable del error.")
    message: str = Field(description="Mensaje legible y seguro para el consumidor.")


class ErrorResponse(BaseModel):
    """Envoltura uniforme de errores."""

    error: ErrorDetail
