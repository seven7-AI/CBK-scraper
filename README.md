# CBK Treasury PDF Scraper

Downloads Treasury Bond and Treasury Bill (91-, 182-, 364-day) result PDFs from the [Central Bank of Kenya](https://www.centralbank.go.ke) website. **Checks previous runs** so already-scraped URLs are **never downloaded twice** (SQLite registry + Redis). Includes an OCR pipeline that converts downloaded PDFs into Markdown and JSON, and is designed for **daily scheduled runs** on Windows (Task Scheduler) or Linux/macOS (cron).

## Features

- **Treasury Bonds:** [treasury bonds results](https://www.centralbank.go.ke/bills-bonds/treasury-bonds/) – one table, all PDF links.
- **Treasury Bills:** [treasury bills](https://www.centralbank.go.ke/bills-bonds/treasury-bills/) – 91-, 182-, and 364-day result PDFs from three tables.
- **No duplicate downloads:** A local SQLite registry (`data/registry.db`) records every downloaded URL. Each run skips URLs that were already scraped in a previous run (bonds + bills combined).
- **Production-ready:** Logging to file and stdout, retries with backoff, configurable timeouts (120s page load by default for slow CBK site).

## Requirements

- Python 3.10+
- Playwright (Chromium)
- Redis (optional but recommended for fast dedup/metrics)

## Installation

1. Open a terminal in the project root.

2. Create a virtual environment and install dependencies:

   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   pip install -e .
   ```

3. Install Playwright browsers (one-time):

   ```powershell
   playwright install chromium
   ```

## Configuration

Edit `config.yaml` in the project root:

- **base_url** – CBK site base.
- **downloads.bonds** / **downloads.bills** – Where to save PDFs.
- **data_dir** / **registry_db** – Where the **registry** lives (used to skip already-downloaded URLs).
- **logs_dir** – Log files.
- **page_load_timeout_sec** – Default 120 for slow loads.
- **download_timeout_sec**, **download_retries** – Download behaviour.

Optional env overrides: `CBK_DOWNLOADS_ROOT`, `CBK_DATA_DIR`, `CBK_REGISTRY_DB`, `CBK_LOGS_DIR`.

## Usage – scraper

From the project root with the venv activated:

```powershell
# Run both bonds and bills (default). Already-downloaded URLs are skipped.
python -m cbk_scraper.run

# Bonds only
python -m cbk_scraper.run --bonds

# Bills only
python -m cbk_scraper.run --bills
```

If you didn’t run `pip install -e .`, set the path first:

```powershell
$env:PYTHONPATH = "src"; python -m cbk_scraper.run
```

Logs go to `logs/cbk_scraper_YYYYMMDD.log`. PDFs go to `downloads/bonds/` and `downloads/bills/`. The registry in `data/registry.db` ensures **no re-downloads** on later runs.

---

## OCR processing – turning PDFs into Markdown/JSON

After PDFs have been downloaded into `downloads/bonds/` and `downloads/bills/`, run the OCR job:

```powershell
python -m cbk_ocr.run_ocr
```

This will:

- Walk the `downloads/` directories.
- Skip PDFs already processed (tracked in Redis sets).
- Extract text with `pdfplumber` (text-first engine).
- Write Markdown to `processed/markdown/{bonds,bills}/`.
- Write structured JSON (pages + metadata) to `processed/json/{bonds,bills}/`.

You can limit processing during tests:

```powershell
python -m cbk_ocr.run_ocr --limit 5
```

---

## Daily jobs (production) on Windows

To run both the scraper and OCR **daily** on Windows, use **Task Scheduler** and the provided scripts.

### Option A: Use the PowerShell script (recommended)

1. Open PowerShell and go to the project root.
2. Run the **dual-job** scheduler script to create two daily tasks:

   ```powershell
   # Scraper at 10:00, OCR at 12:00 (defaults)
   .\scripts\schedule_daily_jobs_windows.ps1

   # Custom times, e.g. scraper 09:00 and OCR 11:30
   .\scripts\schedule_daily_jobs_windows.ps1 -ScraperHour 9 -ScraperMinute 0 -OcrHour 11 -OcrMinute 30
   ```

   This creates:

   - `CBK-Scraper-10AM` → runs `python -m cbk_scraper.run`
   - `CBK-OCR-12PM` → runs `python -m cbk_ocr.run_ocr`

3. Run the tasks once manually to test:

   ```powershell
   Start-ScheduledTask -TaskName "CBK-Scraper-10AM"
   Start-ScheduledTask -TaskName "CBK-OCR-12PM"
   ```

4. To remove them later:

   ```powershell
   Unregister-ScheduledTask -TaskName "CBK-Scraper-10AM"
   Unregister-ScheduledTask -TaskName "CBK-OCR-12PM"
   ```

Both tasks use the Python from `.venv\Scripts\python.exe` if present, so they run with the same env as your manual runs. The scraper only downloads **new** PDFs (SQLite + Redis dedup), and the OCR job only processes **new** PDFs (Redis tracking).

### Option B: Create one or both tasks manually in Task Scheduler

1. Open **Task Scheduler** (taskschd.msc).
2. **Create Basic Task** → Name: e.g. `CBK-Scraper-Daily`.
3. **Trigger:** Daily, at 10:00 (or your preferred time).
4. **Action:** Start a program.
   - **Program:** `D:\2026 Projects\CBK-scraper\.venv\Scripts\python.exe` (use your project path and venv).
   - **Arguments:** `-m cbk_scraper.run`
   - **Start in:** `D:\2026 Projects\CBK-scraper` (project root).
5. Finish and run the task once to verify.

Repeat similar steps to create a second task (e.g. `CBK-OCR-12PM`) that runs:

- Program: your `.venv\Scripts\python.exe`
- Arguments: `-m cbk_ocr.run_ocr`
- Start in: project root

---

## Daily job on Linux / macOS (cron)

```bash
# Edit crontab
crontab -e

# Run daily at 02:00 (adjust path and Python)
0 2 * * * cd /path/to/CBK-scraper && .venv/bin/python -m cbk_scraper.run >> /path/to/CBK-scraper/logs/cron.log 2>&1
```

---

## Project layout

```
CBK-scraper/
  config.yaml
  requirements.txt
  pyproject.toml
  README.md
  scripts/
    schedule_daily_windows.ps1       # Legacy: single scraper task
    schedule_daily_jobs_windows.ps1  # Scraper 10AM + OCR 12PM
  src/
    cbk_common/
      __init__.py
      logging_utils.py
      redis_client.py
    cbk_scraper/
      __init__.py
      config.py
      registry.py      # Prevents re-downloading (previous runs)
      scrape_bonds.py
      scrape_bills.py
      download.py
      run.py
    cbk_ocr/
      __init__.py
      engine.py
      pipeline.py
      redis_store.py
      run_ocr.py
  downloads/
    bonds/
    bills/
  data/
    registry.db        # Tracks scraped URLs (do not delete)
  logs/
  processed/
    markdown/
      bonds/
      bills/
    json/
      bonds/
      bills/
  docs/
    ocr_evaluation.md
```
