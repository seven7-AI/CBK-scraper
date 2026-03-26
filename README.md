# CBK Treasury Scraper + OCR (Linux Docker)

Production scraper and OCR pipeline for Central Bank of Kenya Treasury PDFs.

- Scrapes Treasury Bonds and Treasury Bills (91/182/364-day tables)
- Downloads PDFs with deduplication (SQLite + Redis)
- Runs OCR/text extraction to Markdown and JSON
- Designed for Linux servers using Docker Compose + host cron

## Requirements

- Linux server with Docker Engine + Docker Compose plugin
- Internet access to `centralbank.go.ke`
- UV package manager (recommended for local runs): [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)

## Dependency Management (UV)

This project is UV-managed with dependencies declared in `pyproject.toml`.

Local setup:

```bash
uv sync
```

Run commands via UV:

```bash
uv run python -m cbk_scraper.run
uv run python -m cbk_ocr.run_ocr
uv run python experiments/ocr_test/sample_selector.py
uv run python experiments/ocr_test/run_experiment.py --rostaing
```

## Quick Start (Docker)

From project root:

```bash
docker compose build
docker compose up -d redis
docker compose run --rm app python -m cbk_scraper.run
docker compose run --rm app python -m cbk_ocr.run_ocr
```

Outputs:

- PDFs: `downloads/bonds/`, `downloads/bills/`
- OCR Markdown: `processed/markdown/{bonds,bills}/`
- OCR JSON: `processed/json/{bonds,bills}/`
- Logs: `logs/`
- SQLite registry: `data/registry.db`

## Docker Architecture

- `app` service: runs scraper/OCR commands on-demand
- `redis` service: dedup/metrics cache and OCR processed tracking
- bind mounts for persistent data:
  - `downloads/`, `processed/`, `logs/`, `data/`

`docker-compose.yml` sets:

- `REDIS_HOST=redis`, `REDIS_PORT=6379`
- path overrides (`CBK_DOWNLOADS_ROOT`, `CBK_DATA_DIR`, `CBK_LOGS_DIR`)

The Docker image installs dependencies using UV (`uv sync --no-dev`) from `pyproject.toml`.

## Scheduling with Host Cron (Linux)

Use host cron to run containerized jobs at required times:

- Scraper: 10:00 daily
- OCR: 12:00 daily

Helper scripts:

- `scripts/run_scraper.sh`
- `scripts/run_ocr.sh`

Make scripts executable:

```bash
chmod +x scripts/run_scraper.sh scripts/run_ocr.sh
```

Add cron entries (`crontab -e`) using absolute paths:

```bash
0 10 * * * /absolute/path/to/CBK-scraper/scripts/run_scraper.sh >> /absolute/path/to/CBK-scraper/logs/cron_scraper.log 2>&1
0 12 * * * /absolute/path/to/CBK-scraper/scripts/run_ocr.sh >> /absolute/path/to/CBK-scraper/logs/cron_ocr.log 2>&1
```

## Configuration

Main config file: `config.yaml`

Key settings:

- `base_url`
- `downloads.root`, `downloads.bonds`, `downloads.bills`
- `registry_db`
- `logs_dir`
- page/download timeout and retry settings

Environment overrides (already used in compose):

- `CBK_DOWNLOADS_ROOT`
- `CBK_DATA_DIR`
- `CBK_REGISTRY_DB`
- `CBK_LOGS_DIR`
- `REDIS_URL` or (`REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`)

## Notes on Deduplication

- Scraper dedup checks Redis set `cbk:scraper:downloaded_urls` first
- Falls back to SQLite registry in `data/registry.db`
- OCR dedup checks Redis set `cbk:ocr:processed_files`

The jobs are idempotent and safe to run repeatedly.

## Project Layout

```text
CBK-scraper/
  Dockerfile
  docker-compose.yml
  .dockerignore
  config.yaml
  requirements.txt
  pyproject.toml
  README.md
  scripts/
    run_scraper.sh
    run_ocr.sh
  src/
    cbk_common/
      logging_utils.py
      redis_client.py
    cbk_scraper/
      config.py
      registry.py
      scrape_bonds.py
      scrape_bills.py
      download.py
      run.py
    cbk_ocr/
      engine.py
      pipeline.py
      redis_store.py
      run_ocr.py
  downloads/
  processed/
  logs/
  data/
```

## OCR Experiment Sandbox (10 sample docs)

Use the sandbox under `experiments/ocr_test/` to test OCR libraries without
touching production OCR outputs.

What it does:

- Selects a balanced sample of 10 PDFs from `downloads/` (5 bonds + 5 bills)
- Copies samples to `experiments/ocr_test/input/{bonds,bills}`
- Writes all test outputs to `experiments/ocr_test/output/`
- Stores manifest and run summary in `experiments/ocr_test/metadata/`

Commands:

```bash
# 1) Build sample set
python experiments/ocr_test/sample_selector.py

# 2) Run all experiment stages (default)
python experiments/ocr_test/run_experiment.py

# Or run selected stages (Rostaing is mandatory)
python experiments/ocr_test/run_experiment.py --preocr --ocrmypdf --rostaing

# 3) Restore OCR text into best-effort markdown tables
python experiments/ocr_test/restore_tables.py
python experiments/ocr_test/restore_tables.py --limit 3
```

Stages:

- `PreOCR`: simple type detection heuristic (`digital` vs `likely_scanned`)
- `OCRmyPDF`: preserves original PDF while adding OCR text layer (if `ocrmypdf` command is installed)
- `RostaingOCR`: required when enabled; no fallback module names are used
