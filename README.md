# pdf-validation

Microservicio de **validación de archivos PDF** del ecosistema de procesamiento de PDF.

## Propósito y límites

Recibe los bytes binarios de un PDF y decide si puede continuar el procesamiento:

- Rechaza archivos vacíos, mayores al tamaño máximo configurado, corruptos, ilegibles o cifrados.
- Verifica la estructura real del PDF con **pypdf** (cabecera, xref y catálogo de páginas); no basta con la firma `%PDF-`.
- Calcula el **checksum SHA-256** del contenido binario aceptado.
- Expone healthchecks (`/health/live`, `/health/ready`) y logs estructurados en JSON con `X-Request-ID`.

**No hace** (responsabilidad de otros microservicios):

- No extrae texto ni genera resúmenes, ni llama a modelos de IA.
- No persiste documentos ni metadatos; **tampoco deduplica**: el checksum identifica el contenido binario exacto, pero la política de duplicados corresponde al orquestador o al servicio de persistencia.
- No descarga ni ejecuta contenido proporcionado por los usuarios; la validación es local sobre los bytes recibidos.

## Requisitos

- Python 3.13 y [uv](https://docs.astral.sh/uv/) para ejecución local.
- Docker y Docker Compose para ejecución contenedorizada.

## Instalación y ejecución local

```powershell
uv sync                 # instala dependencias (crea .venv)
uv run uvicorn pdf_validation.main:app --app-dir src --port 8000
```

## Ejecución con Docker

Opción 1 — puerto predeterminado (8000):

```powershell
docker compose up --build
```

Opción 2 — si el puerto 8000 del host está ocupado, publicar en otro puerto (p. ej. 8001):

```powershell
$env:PORT="8001"
docker compose up --build
```

El contenedor corre con usuario no privilegiado (`app`) y escucha siempre en el puerto interno **8000**. La variable `PORT` cambia únicamente el **puerto publicado en el host** (`docker-compose.yml` mapea `${PORT:-8000}:8000`). El contenedor define un `HEALTHCHECK` contra `/health/live`; además, Compose verifica `/health/ready` y reinicia el servicio con política `unless-stopped`.

El servicio se une a la **red externa compartida `pdf-ecosystem-net`**, donde también viven Consul, `extract` (3 réplicas tras Nginx), `pdf-summarize`, `pdf-persistence` y MongoDB. Se registra en Consul de forma **estática** mediante `services.json` (administrado por el servidor Consul, repositorio `pdf-extractext-summarize/infra/consul`), con healthcheck HTTP contra `/health/ready` cada 10 s. No hay registro dinámico desde el código: es un servicio de instancia única.

## Variables de entorno

| Variable            | Descripción                                  | Predeterminado |
|---------------------|----------------------------------------------|----------------|
| `MAX_FILE_SIZE_MIB` | Tamaño máximo aceptado de PDF, en MiB        | `20`           |
| `PORT`              | Puerto publicado por Docker Compose (host)   | `8000`         |

## Contrato HTTP

### `GET /health/live`

Indica que el proceso está vivo. `200 OK` → `{"status": "alive"}`

### `GET /health/ready`

Indica que la aplicación está lista. `200 OK` → `{"status": "ready"}`

### `POST /validate`

Valida un PDF binario. El cuerpo completo es el archivo (sin multipart).

- **Content-Type requerido:** `application/pdf`
- **Timeout recomendado del consumidor:** 10 s (la validación es local y O(tamaño)).

**Respuesta exitosa** `200 OK`:

```json
{
  "valid": true,
  "file_size_bytes": 429,
  "checksum": "260e2f55fdddd8a17c66699f0852fed9d9299cfe5b47d5d12c1b6cfb8f824f0c",
  "checksum_algorithm": "sha256"
}
```

Ejemplo de uso:

```powershell
curl.exe -X POST -H "Content-Type: application/pdf" --data-binary "@documento.pdf" http://localhost:8000/validate
```

**Errores** (envoltura uniforme `{"error": {"code", "message"}}`):

| HTTP | code                     | Causa                              |
|------|--------------------------|------------------------------------|
| 400  | `EMPTY_PDF`              | Cuerpo vacío                       |
| 413  | `PDF_TOO_LARGE`          | Excede `MAX_FILE_SIZE_MIB`         |
| 415  | `UNSUPPORTED_MEDIA_TYPE` | Content-Type distinto de PDF       |
| 422  | `INVALID_PDF`            | No es PDF legible, corrupto, truncado o sin páginas |
| 422  | `ENCRYPTED_PDF`          | PDF cifrado (política: rechazar)   |

Las respuestas no incluyen el contenido del archivo, trazas internas ni secretos. Todas las respuestas incluyen el header `X-Request-ID` (propagado si el cliente lo envía; si no, se genera).

## Checksum

- **Algoritmo:** SHA-256, en hexadecimal minúsculas (64 caracteres).
- Identifica el **contenido binario exacto** del archivo aceptado.
- La igualdad de checksum **no** es una garantía matemática absoluta de identidad (posibilidad teórica de colisión).
- Instalación previa usaba MD5; la nueva implementación adopta **SHA-256** como opción preferida (no existe especificación vigente que exija MD5).

## Observabilidad

- **Logs estructurados JSON** por stdout (cada línea: `timestamp`, `level`, `logger`, `message`). Configurados en `pdf_validation/logging_config.py` y activados en el punto de entrada `main.py`.
- **Request-ID:** middleware propaga o genera `X-Request-ID`; se incluye en los logs de validación.
- Los logs **nunca** incluyen bytes del PDF ni cuerpos de solicitudes (solo código de error, tamaño y checksum).
- **Verificación:** `uv run uvicorn pdf_validation.main:app --app-dir src`, enviar una solicitud y observar una línea JSON por registro en stdout.
- **Pendiente:** métricas Prometheus y trazas OpenTelemetry/W3C `traceparent`, a definir cuando exista el contrato común del ecosistema (la infraestructura FastAPI ya lo permite, pero no se exporta nada hoy).

## Arquitectura

```
src/pdf_validation/
├── config.py          # Settings.from_env(): MAX_FILE_SIZE_MIB
├── checksum.py        # checksum_hex(): SHA-256 hex
├── validation.py      # validate_pdf(data, max_size) -> ValidationReport | PdfValidationError
├── schemas.py         # Contratos Pydantic (éxito y error)
├── app.py             # create_app(): rutas, middleware Request-ID, traducción de errores
├── logging_config.py  # Logs JSON
└── main.py            # Punto de entrada uvicorn
tests/                 # pytest: dominio, configuración, API, logging
```

Módulos pequeños con interfaces mínimas: la única puerta del dominio es `validate_pdf`; la capa HTTP solo traduce códigos de error a estados (`_ERROR_STATUS`).

## Seguridad

- La validación es **local sobre los bytes recibidos**; no se escriben archivos temporales (`BytesIO`).
- Los PDFs cifrados se **rechazan** (`ENCRYPTED_PDF`): no pueden procesarse aguas abajo sin credenciales.
- pypdf no ejecuta JavaScript ni acciones activas del PDF durante la lectura estructural.
- Usuario no privilegiado en el contenedor.
- Limitación conocida de la biblioteca: pypdf realiza validación estructural; no detecta PDFs con contenido postscript raro o ramas exóticas que otras herramientas (p. ej. Ghostscript) sí revelarían.

## Pruebas y calidad

```powershell
uv run pytest            # suite completa con cobertura
uv run ruff check .      # lint
uv run ruff format --check .
```

Fixtures de PDF generados de forma controlada con pypdf (`tests/conftest.py`); los tests son independientes entre sí y no mockean la lógica central de validación.

## Contrato de integración (para el orquestador)

1. `POST /validate` con `Content-Type: application/pdf` y cuerpo = bytes del PDF.
2. Éxito `200`: usar `checksum` + `checksum_algorithm` como identidad de contenido para la política de persistencia/deduplicación (fuera de este servicio).
3. Errores: `400`/`413`/`415` indican entrada inválida (rechazar antes de reintentar); `422` indica PDF no procesable.
4. Timeout recomendado: 10 s. Healthchecks: `/health/live` (liveness) y `/health/ready` (readiness).

**Decisión compartida pendiente:** formato exacto intercambiado para `checksum_algorithm` entre microservicios y si la deduplicación vive en el orquestador o en el servicio de persistencia. Registrado como pendiente; no se asume aquí.

## Decisiones técnicas

- **pypdf** como biblioteca mantenida, sin ejecución de contenido activo y con lectura desde memoria.
- **FastAPI + uvicorn**, **uv** para dependencias reproducibles (`uv.lock`), **pytest-cov**, **Ruff** (lint + formato).
- Sin multipart: el cuerpo binario directo es más simple y suficiente para un único archivo.
- Métricas y trazas diferidas hasta contar con el contrato común del ecosistema.
