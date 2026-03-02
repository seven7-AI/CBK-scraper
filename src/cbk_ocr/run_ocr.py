from __future__ import annotations

import argparse
import sys

from .pipeline import run_ocr_job


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run OCR over downloaded CBK Treasury PDFs (bonds and bills). "
        "Skips PDFs already processed in previous runs using Redis tracking."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of PDFs to process in this run",
    )
    args = parser.parse_args()
    return run_ocr_job(limit=args.limit)


if __name__ == "__main__":
    sys.exit(main())

