from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = PROJECT_ROOT / "experiments" / "ocr_test"
ROSTAING_TXT_ROOT = TEST_ROOT / "output" / "rostaing_ocr"
RESTORE_MD_ROOT = TEST_ROOT / "output" / "restored_markdown"
RESTORE_JSON_ROOT = TEST_ROOT / "output" / "restored_structured"
RESTORE_META_PATH = TEST_ROOT / "metadata" / "restore_summary.json"

logger = logging.getLogger("ocr_restore")


@dataclass
class RestoreResult:
    file: str
    status: str
    detected_tables: int
    output_md: str
    output_json: str
    details: dict[str, Any]


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _prepare_dirs() -> None:
    RESTORE_MD_ROOT.mkdir(parents=True, exist_ok=True)
    RESTORE_JSON_ROOT.mkdir(parents=True, exist_ok=True)
    RESTORE_META_PATH.parent.mkdir(parents=True, exist_ok=True)


def _split_cells(line: str) -> list[str]:
    if "\t" in line:
        cells = [c.strip() for c in re.split(r"\t+", line) if c.strip()]
    else:
        cells = [c.strip() for c in re.split(r"\s{2,}", line) if c.strip()]
    return cells


def _is_table_candidate(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("--- Page "):
        return False
    cells = _split_cells(stripped)
    if len(cells) >= 2:
        return True
    # weak heuristic: lines with many numeric tokens often belong to tabular rows
    numeric_tokens = re.findall(r"\b\d[\d,./-]*\b", stripped)
    return len(numeric_tokens) >= 3


def _to_markdown_table(rows: list[list[str]]) -> str:
    width = max(len(r) for r in rows)
    padded = [r + [""] * (width - len(r)) for r in rows]
    header = padded[0]
    sep = ["---"] * width
    body = padded[1:] if len(padded) > 1 else []

    def fmt(row: list[str]) -> str:
        return "| " + " | ".join(row) + " |"

    lines = [fmt(header), fmt(sep)]
    lines.extend(fmt(r) for r in body)
    return "\n".join(lines)


def _restore_one(txt_path: Path) -> RestoreResult:
    logger.info("Restore start: %s", txt_path.name)
    md_path = RESTORE_MD_ROOT / f"{txt_path.stem}.md"
    json_path = RESTORE_JSON_ROOT / f"{txt_path.stem}.json"

    text = txt_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    blocks: list[list[list[str]]] = []
    current: list[list[str]] = []

    for line in lines:
        if _is_table_candidate(line):
            cells = _split_cells(line.strip())
            if not cells:
                cells = [line.strip()]
            current.append(cells)
            continue

        if current:
            if len(current) >= 2:
                blocks.append(current)
            current = []

    if current and len(current) >= 2:
        blocks.append(current)

    md_sections = [
        f"# Restored Output: {txt_path.stem}",
        "",
        "This is a best-effort reconstruction from OCR text. "
        "Table geometry may differ from the source PDF.",
        "",
    ]

    if not blocks:
        md_sections.extend(["## No table-like blocks detected", "", "```text", text, "```"])
    else:
        for idx, block in enumerate(blocks, start=1):
            md_sections.append(f"## Detected Table {idx}")
            md_sections.append("")
            md_sections.append(_to_markdown_table(block))
            md_sections.append("")

    md_path.write_text("\n".join(md_sections), encoding="utf-8")

    payload = {
        "source_txt": str(txt_path),
        "detected_tables": len(blocks),
        "tables": [{"index": i + 1, "rows": rows} for i, rows in enumerate(blocks)],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "Restore done: %s (tables=%d) -> %s",
        txt_path.name,
        len(blocks),
        md_path,
    )
    return RestoreResult(
        file=txt_path.name,
        status="success",
        detected_tables=len(blocks),
        output_md=str(md_path),
        output_json=str(json_path),
        details={"line_count": len(lines)},
    )


def main() -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(description="Restore OCR text into markdown table blocks.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of files")
    args = parser.parse_args()

    _prepare_dirs()
    txt_files = sorted(ROSTAING_TXT_ROOT.glob("*.txt"))
    if args.limit and args.limit > 0:
        txt_files = txt_files[: args.limit]

    if not txt_files:
        raise RuntimeError("No rostaing .txt files found. Run OCR experiment first.")

    logger.info("Restoring %d OCR text files", len(txt_files))
    results = [_restore_one(path) for path in txt_files]
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_files": len(results),
        "total_detected_tables": sum(r.detected_tables for r in results),
        "results": [asdict(r) for r in results],
    }
    RESTORE_META_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Restore summary written: %s", RESTORE_META_PATH)
    print(f"Restore summary written: {RESTORE_META_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
