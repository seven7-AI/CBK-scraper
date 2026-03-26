#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# Ensure Redis is up for OCR processed tracking
docker compose up -d redis

# Run OCR as one-shot container
docker compose run --rm app python -m cbk_ocr.run_ocr

