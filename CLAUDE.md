# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastAPI LibreOffice REST server for document conversion — primarily used to convert DOCX files to PDF for Moodle integration. The server accepts file uploads, invokes LibreOffice headless, and serves back the converted PDF.

## Development Setup

The application lives in `my_fastapi_project/` and is designed to run as `fastapi-user` on Ubuntu/Debian.

```bash
cd my_fastapi_project/
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi gunicorn uvicorn python-multipart werkzeug
```

**System dependency:** LibreOffice must be installed (`apt install libreoffice`) and `soffice` must be on PATH.

## Running the Server

```bash
# Dev/debug
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --log-level debug

# Via startup script (production)
./gunicorn_start
```

Server binds to `127.0.0.1:8000` by default (Nginx proxies public traffic).

## Testing the API

```bash
# Upload and convert a document
curl -F 'file=@sample1.docx' http://127.0.0.1:8000/upload
# Returns: {"result":{"pdf":"/upload/pdf/sample1.pdf","source":"/upload/source/sample1.docx"}}

# Download the converted PDF
curl http://127.0.0.1:8000/upload/pdf/sample1.pdf -o sample1.pdf

# Health check
curl http://127.0.0.1:8000/
```

## Architecture

```
main.py          — FastAPI app with 3 endpoints (GET /, POST /upload, GET /upload/pdf/{filename})
config.py        — Single dict with uploads_dir path (hardcoded for Linux deployment)
common/convert.py — LibreOffice conversion logic
```

**Request flow:** `POST /upload` → sanitize filename (werkzeug) → save to `tmp/source/` → call `convert_to()` with 15s timeout → return JSON with paths → client fetches PDF via `GET /upload/pdf/{filename}`.

**Conversion:** `convert_to()` in `common/convert.py` spawns `soffice --headless --writer --convert-to pdf --outdir [tmp/pdf/] [source_file]`, parses stdout with regex to confirm success, and raises `LibreOfficeError` on failure. Timeout is enforced via `subprocess.wait(timeout)` + `SIGTERM`.

**Error types returned by `/upload`:** `LibreOfficeError`, `TimeoutExpired`, `OtherError` — all returned as JSON with an `error` key.

## Docker

```bash
# Build and start
docker compose up --build

# Run in background
docker compose up -d --build

# Test
curl -F 'file=@sample1.docx' http://localhost:8000/upload
```

Converted files are stored in `./tmp/` on the host (mounted as `/app/tmp` in the container). The `UPLOADS_DIR` environment variable controls this path inside the container.

> **Note:** The LibreOffice Writer layer is large (~400 MB). Subsequent builds reuse the cached layer if `requirements.txt` and `apt` packages haven't changed.

## Configuration

`config.py` sets the uploads directory, falling back to the legacy bare-metal path if `UPLOADS_DIR` is not set:
```python
config = {"uploads_dir": "/home/fastapi-user/my_fastapi_project/tmp"}
```
Change this path if deploying to a different location. The `tmp/source/` and `tmp/pdf/` subdirectories must exist.

## Production Infrastructure

- **Gunicorn** with 4 Uvicorn workers (configured in `gunicorn_start`)
- **Supervisor** manages the Gunicorn process (`/etc/supervisor/conf.d/my_project.conf`)
- **Nginx** reverse proxies port 80 → 127.0.0.1:8000, with `client_max_body_size 1G`
- **Firewall** should restrict port 80 to Moodle server IP only
- **Cron job** for privacy: deletes files in `tmp/` older than 10 minutes

## Platform Notes

`libreoffice_exec()` in `common/convert.py` uses `shutil.which("soffice")` on Linux. macOS and Windows paths are placeholders and not fully implemented — this server is Linux-only in practice.
