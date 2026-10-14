"""Configuración del microservicio mediante variables de entorno."""

import os
from dataclasses import dataclass

#: Tamaño máximo predeterminado de archivo, en bytes (20 MiB).
DEFAULT_MAX_FILE_SIZE_MIB = 20


@dataclass(frozen=True)
class Settings:
    """Configuración inmutable de la aplicación.

    Atributos:
        max_file_size_bytes: tamaño máximo aceptado para un PDF, en bytes.
    """

    max_file_size_bytes: int

    @classmethod
    def from_env(cls) -> "Settings":
        """Construye la configuración desde variables de entorno.

        Variables:
            MAX_FILE_SIZE_MIB: tamaño máximo en MiB (entero positivo,
                predeterminado 20).

        Raises:
            ValueError: si la variable no es un entero positivo válido.
        """
        raw = os.environ.get("MAX_FILE_SIZE_MIB", str(DEFAULT_MAX_FILE_SIZE_MIB))
        try:
            mib = int(raw)
        except ValueError:
            raise ValueError(
                f"MAX_FILE_SIZE_MIB debe ser un entero positivo, se recibió: {raw!r}"
            ) from None
        if mib <= 0:
            raise ValueError(
                f"MAX_FILE_SIZE_MIB debe ser un entero positivo, se recibió: {raw!r}"
            )
        return cls(max_file_size_bytes=mib * 1024 * 1024)
