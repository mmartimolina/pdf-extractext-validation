"""Cálculo del checksum de contenido aceptado.

El checksum identifica el contenido binario exacto del archivo aceptado.
La igualdad de checksum no constituye una garantía matemática absoluta de
identidad (SHA-256 mantiene la posibilidad teórica de colisiones).
"""

from hashlib import sha256

#: Algoritmo utilizado para el checksum de contenido.
CHECKSUM_ALGORITHM = "sha256"


def checksum_hex(data: bytes) -> str:
    """Devuelve el checksum SHA-256 en hexadecimal minúsculas de ``data``."""
    return sha256(data).hexdigest()
