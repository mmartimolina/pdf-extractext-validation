"""Lógica de dominio: validación de PDF y cálculo del checksum SHA-256.

Puertas del microservicio: :func:`validate_pdf` es la única función pública.
Los errores se comunican mediante :class:`PdfValidationError`, que la capa HTTP
traduce a respuestas coherentes.
"""

from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from pdf_validation.checksum import CHECKSUM_ALGORITHM, checksum_hex


class PdfValidationError(Exception):
    """Error de dominio de validación de PDF.

    Atributos:
        code: identificador estable del error (p. ej. ``EMPTY_PDF``).
        message: mensaje legible y seguro para el consumidor.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ValidationReport:
    """Resultado exitoso de la validación de un PDF."""

    size_bytes: int
    checksum: str
    checksum_algorithm: str = CHECKSUM_ALGORITHM


def validate_pdf(data: bytes, max_size_bytes: int) -> ValidationReport:
    """Valida que ``data`` sea un PDF legible y devuelve un reporte de validación.

    La validación comprueba la estructura del documento con pypdf (cabecera,
    xref/tabla de referencias y páginas), no solo la firma ``%PDF-``. Los PDFs
    cifrados se rechazan porque no pueden procesarse aguas abajo sin credenciales.

    Args:
        data: bytes completos del archivo PDF.
        max_size_bytes: tamaño máximo aceptado, en bytes.

    Returns:
        ``ValidationReport`` con el tamaño y el checksum SHA-256 del contenido.

    Raises:
        PdfValidationError: con ``code`` igual a ``EMPTY_PDF``, ``PDF_TOO_LARGE``,
            ``ENCRYPTED_PDF`` o ``INVALID_PDF`` según la causa.
    """
    if not data:
        raise PdfValidationError("EMPTY_PDF", "El archivo está vacío.")

    if len(data) > max_size_bytes:
        raise PdfValidationError(
            "PDF_TOO_LARGE",
            f"El archivo excede el tamaño máximo permitido de {max_size_bytes} bytes.",
        )

    try:
        reader = PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise PdfValidationError(
                "ENCRYPTED_PDF",
                "El PDF está cifrado y no puede procesarse sin credenciales.",
            )
        # Fuerza el parseo de xref y del catálogo de páginas para detectar
        # corrupción estructural que la sola cabecera no revela.
        if len(reader.pages) == 0:
            raise PdfValidationError("INVALID_PDF", "El PDF no contiene páginas.")
    except PdfValidationError:
        raise
    except (PdfReadError, ValueError, OSError, TypeError) as exc:
        raise PdfValidationError(
            "INVALID_PDF", "El archivo no es un PDF válido o está corrupto."
        ) from exc

    return ValidationReport(size_bytes=len(data), checksum=checksum_hex(data))
