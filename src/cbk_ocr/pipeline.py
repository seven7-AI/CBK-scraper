from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from cbk_common.logging_utils import configure_json_logging

from cbk_scraper.config import get_paths, load_config
from cbk_scraper.registry import get_registry_path

from .engine import OcrResult, OcrPage, TextFirstOcrEngine
from .redis_store import is_processed, mark_processed

logger = logging.getLogger(__name__)


def _iter_pdf_files() -> Iterable[Tuple[Path, str]]:
    """Yield (pdf_path, source) for bonds and bills downloads."""
    cfg = load_config()
    paths = get_paths(cfg)
    bonds_dir = paths["bonds_dir"]
    bills_dir = paths["bills_dir"]

    for root, source in ((bonds_dir, "bonds"), (bills_dir, "bills")):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.pdf")):
            yield path, source


def _file_id(path: Path) -> str:
    return sha256(str(path.resolve()).encode("utf-8")).hexdigest()


def _lookup_url_for_path(pdf_path: Path) -> Optional[str]:
    """Best-effort lookup of source URL from SQLite registry using local_path."""
    registry_db = get_registry_path()
    if not registry_db.exists():
        return None
    conn = sqlite3.connect(str(registry_db))
    try:
        row = conn.execute(
            "SELECT url FROM downloads WHERE local_path = ?",
            (str(pdf_path.resolve()),),
        ).fetchone()
        return row[0] if row else None
    except Exception:
        return None
    finally:
        conn.close()


def _write_markdown(result: OcrResult, pdf_path: Path, out_dir: Path, source: str) -> Path:
    out_dir = out_dir / source
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / (pdf_path.stem + ".md")
    lines: List[str] = []
    lines.append(f"# {pdf_path.name}")
    for page in result.pages:
        lines.append("")
        lines.append(f"## Page {page.page_number}")
        lines.append("")
        lines.append(page.text)
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def _write_json(result: OcrResult, metadata: dict, out_dir: Path, source: str) -> Path:
    out_dir = out_dir / source
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / (metadata["filename_stem"] + ".json")
    payload = {
        "pages": [asdict(page) for page in result.pages],
        "plain_text": result.plain_text,
        "metadata": metadata,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


def run_ocr_job(limit: Optional[int] = None) -> int:
    """Run OCR over new PDFs under downloads/, skipping those already processed.

    Returns 0 on success (even if nothing to do), non-zero if unrecoverable error.
    """
    cfg = load_config()
    paths = get_paths(cfg)
    logs_dir = paths["logs_dir"]
    configure_json_logging(logs_dir, service="cbk-ocr")

    logger.info("Starting OCR job for CBK PDFs", extra={"event": "ocr_started"})
    engine = TextFirstOcrEngine()

    processed = skipped = failed = 0
    markdown_root = paths["project_root"] / "processed" / "markdown"
    json_root = paths["project_root"] / "processed" / "json"

    for pdf_path, source in _iter_pdf_files():
        file_id = _file_id(pdf_path)
        if is_processed(file_id):
            skipped += 1
            logger.info(
                "Skipping already processed PDF",
                extra={"event": "ocr_skipped", "pdf_path": str(pdf_path), "source": source},
            )
            continue

        url = _lookup_url_for_path(pdf_path)
        try:
            result = engine.extract(pdf_path)
            meta = {
                "filename": pdf_path.name,
                "filename_stem": pdf_path.stem,
                "source": source,
                "pdf_path": str(pdf_path.resolve()),
                "url": url,
                "file_size_bytes": pdf_path.stat().st_size,
            }
            md_path = _write_markdown(result, pdf_path, markdown_root, source)
            json_path = _write_json(result, meta, json_root, source)
            mark_processed(file_id, url, source)
            processed += 1
            logger.info(
                "OCR processed PDF",
                extra={
                    "event": "ocr_finished",
                    "pdf_path": str(pdf_path),
                    "source": source,
                    "pages": len(result.pages),
                    "file_size_bytes": meta["file_size_bytes"],
                    "markdown_path": str(md_path),
                    "json_path": str(json_path),
                },
            )
        except Exception as exc:
            failed += 1
            logger.exception(
                "OCR failed for %s: %s",
                pdf_path,
                exc,
                extra={"event": "ocr_failed", "pdf_path": str(pdf_path), "source": source},
            )

        if limit is not None and processed >= limit:
            break

    logger.info(
        "OCR job finished",
        extra={
            "event": "ocr_finished_summary",
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
        },
    )
    return 0

