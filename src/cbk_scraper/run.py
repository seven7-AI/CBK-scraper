"""CLI entrypoint: run bonds and/or bills scraper then download PDFs (skips already-downloaded URLs)."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config, get_paths
from .scrape_bonds import scrape_bonds
from .scrape_bills import scrape_bills
from .download import download_pdfs


def setup_logging(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"cbk_scraper_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="CBK Treasury PDF Scraper – download bonds and bills PDFs. "
        "Uses a local registry so already-scraped URLs are never re-downloaded."
    )
    parser.add_argument("--bonds", action="store_true", help="Scrape and download Treasury Bonds PDFs")
    parser.add_argument("--bills", action="store_true", help="Scrape and download Treasury Bills (91/182/364) PDFs")
    parser.add_argument("--no-bonds", action="store_true", help="Disable bonds (use with --bills for bills only)")
    parser.add_argument("--no-bills", action="store_true", help="Disable bills (use with --bonds for bonds only)")
    args = parser.parse_args()

    run_bonds = args.bonds or (not args.bills and not args.no_bonds)
    run_bills = args.bills or (not args.bonds and not args.no_bills)
    if not run_bonds and not run_bills:
        run_bonds = run_bills = True

    cfg = load_config()
    paths = get_paths(cfg)
    setup_logging(paths["logs_dir"])
    logger = logging.getLogger(__name__)

    base_url = cfg.get("base_url", "https://www.centralbank.go.ke")
    page_timeout = cfg.get("page_load_timeout_sec", 120)
    page_delay = cfg.get("delay_between_pages_sec", 1.0)

    all_ok = True
    total_downloaded = total_skipped = total_failed = 0

    if run_bonds:
        logger.info("=== Treasury Bonds ===")
        try:
            urls = scrape_bonds(
                base_url=base_url,
                page_load_timeout_sec=page_timeout,
                delay_between_pages_sec=page_delay,
            )
            logger.info("Bonds: %d PDF URLs collected", len(urls))
            if urls:
                paths["bonds_dir"].mkdir(parents=True, exist_ok=True)
                d, s, f = download_pdfs(
                    urls,
                    paths["bonds_dir"],
                    "bonds",
                    registry_path=paths["registry_db"],
                    base_url=base_url,
                )
                total_downloaded += d
                total_skipped += s
                total_failed += f
                logger.info("Bonds: downloaded=%d skipped=%d failed=%d", d, s, f)
        except Exception as e:
            logger.exception("Bonds failed: %s", e)
            all_ok = False

    if run_bills:
        logger.info("=== Treasury Bills ===")
        try:
            urls = scrape_bills(
                base_url=base_url,
                page_load_timeout_sec=page_timeout,
                delay_between_pages_sec=page_delay,
            )
            logger.info("Bills: %d PDF URLs collected", len(urls))
            if urls:
                paths["bills_dir"].mkdir(parents=True, exist_ok=True)
                d, s, f = download_pdfs(
                    urls,
                    paths["bills_dir"],
                    "bills",
                    registry_path=paths["registry_db"],
                    base_url=base_url,
                )
                total_downloaded += d
                total_skipped += s
                total_failed += f
                logger.info("Bills: downloaded=%d skipped=%d failed=%d", d, s, f)
        except Exception as e:
            logger.exception("Bills failed: %s", e)
            all_ok = False

    logger.info("=== Done: downloaded=%d skipped=%d failed=%d", total_downloaded, total_skipped, total_failed)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
