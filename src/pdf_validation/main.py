"""Punto de entrada del microservicio para ejecución directa con uvicorn."""

from pdf_validation.app import create_app
from pdf_validation.logging_config import configure_logging

configure_logging()

app = create_app()
