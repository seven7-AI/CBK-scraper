#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# Ensure Redis is up for dedup/metrics
docker compose up -d redis

# Run scraper as one-shot container
docker compose run --rm app python -m cbk_scraper.run

