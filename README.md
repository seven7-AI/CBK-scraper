# CBK Treasury PDF Scraper

Downloads Treasury Bond and Treasury Bill (91-, 182-, 364-day) result PDFs from the [Central Bank of Kenya](https://www.centralbank.go.ke) website. **Checks previous runs** so already-scraped URLs are **never downloaded twice** (SQLite registry). Suitable for **daily scheduled runs** on Windows (Task Scheduler) or Linux/macOS (cron).

## Features

- **Treasury Bonds:** [treasury bonds results](https://www.centralbank.go.ke/bills-bonds/treasury-bonds/) – one table, all PDF links.
- **Treasury Bills:** [treasury bills](https://www.centralbank.go.ke/bills-bonds/treasury-bills/) – 91-, 182-, and 364-day result PDFs from three tables.
- **No duplicate downloads:** A local SQLite registry (`data/registry.db`) records every downloaded URL. Each run skips URLs that were already scraped in a previous run (bonds + bills combined).
- **Production-ready:** Logging to file and stdout, retries with backoff, configurable timeouts (120s page load by default for slow CBK site).

## Requirements

- Python 3.10+
- Playwright (Chromium)

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

## Usage

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

## Daily job (production) on Windows

To run the scraper **daily** on Windows (e.g. 02:00), use **Task Scheduler** and the provided script.

### Option A: Use the PowerShell script (recommended)

1. Open PowerShell and go to the project root.
2. Run the scheduler script (creates a daily task at 02:00 by default):

   ```powershell
   .\scripts\schedule_daily_windows.ps1
   ```

3. Optional: custom time (e.g. 03:30):

   ```powershell
   .\scripts\schedule_daily_windows.ps1 -Hour 3 -Minute 30
   ```

4. Run the task once manually to test:

   ```powershell
   Start-ScheduledTask -TaskName "CBK-Scraper-Daily"
   ```

5. To remove the task later:

   ```powershell
   Unregister-ScheduledTask -TaskName "CBK-Scraper-Daily"
   ```

The script uses the Python from `.venv\Scripts\python.exe` if present, so the task runs with the same env as your manual runs. Each run only downloads **new** PDFs; previous runs’ URLs are skipped via the registry.

### Option B: Create the task manually in Task Scheduler

1. Open **Task Scheduler** (taskschd.msc).
2. **Create Basic Task** → Name: e.g. `CBK-Scraper-Daily`.
3. **Trigger:** Daily, at 02:00 (or your preferred time).
4. **Action:** Start a program.
   - **Program:** `D:\2026 Projects\CBK-scraper\.venv\Scripts\python.exe` (use your project path and venv).
   - **Arguments:** `-m cbk_scraper.run`
   - **Start in:** `D:\2026 Projects\CBK-scraper` (project root).
5. Finish and run the task once to verify.

Every daily run will **check the registry** and only download PDFs that weren’t scraped in a previous run.

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
    schedule_daily_windows.ps1   # Register Windows daily task
  src/
    cbk_scraper/
      __init__.py
      config.py
      registry.py      # Prevents re-downloading (previous runs)
      scrape_bonds.py
      scrape_bills.py
      download.py
      run.py
  downloads/
    bonds/
    bills/
  data/
    registry.db        # Tracks scraped URLs (do not delete)
  logs/
```
