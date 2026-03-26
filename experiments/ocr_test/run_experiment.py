from __future__ import annotations

import argparse
import importlib
import json
import logging
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = PROJECT_ROOT / "experiments" / "ocr_test"
INPUT_ROOT = TEST_ROOT / "input"
OUTPUT_ROOT = TEST_ROOT / "output"
META_ROOT = TEST_ROOT / "metadata"
MANIFEST_PATH = META_ROOT / "sample_manifest.json"
SUMMARY_PATH = META_ROOT / "run_summary.json"

PREOCR_OUT = OUTPUT_ROOT / "preocr"
OCRMYPDF_OUT = OUTPUT_ROOT / "ocrmypdf"
ROSTAING_OUT = OUTPUT_ROOT / "rostaing_ocr"
COMBINED_OUT = OUTPUT_ROOT / "combined"

logger = logging.getLogger("ocr_experiment")


@dataclass
class StageResult:
    file: str
    source: str
    stage: str
    status: str  # success|failed|skipped
    duration_ms: int
    details: dict[str, Any]


def _prepare_dirs() -> None:
    for p in (PREOCR_OUT, OCRMYPDF_OUT, ROSTAING_OUT, COMBINED_OUT, META_ROOT):
        p.mkdir(parents=True, exist_ok=True)

def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _load_manifest_files() -> list[dict[str, Any]]:
    if MANIFEST_PATH.exists():
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return list(data.get("entries", []))

    # fallback: scan input folders directly
    entries: list[dict[str, Any]] = []
    for source in ("bonds", "bills"):
        for pdf in (INPUT_ROOT / source).glob("*.pdf"):
            entries.append(
                {
                    "source": source,
                    "copied_path": str(pdf.resolve()),
                    "filename": pdf.name,
                }
            )
    return entries


def _stage_preocr(pdf_path: Path, source: str) -> StageResult:
    start = time.perf_counter()
    details: dict[str, Any] = {}
    status = "success"
    logger.info("PreOCR start: %s", pdf_path.name)
    try:
        import pdfplumber

        with pdfplumber.open(str(pdf_path)) as pdf:
            pages = len(pdf.pages)
            text_chars = 0
            empty_pages = 0
            for page in pdf.pages:
                txt = page.extract_text() or ""
                text_chars += len(txt)
                if not txt.strip():
                    empty_pages += 1
            avg_chars_per_page = text_chars / pages if pages else 0
            doc_type = "digital" if avg_chars_per_page > 120 else "likely_scanned"
            details = {
                "pages": pages,
                "text_chars": text_chars,
                "avg_chars_per_page": avg_chars_per_page,
                "empty_pages": empty_pages,
                "detected_type": doc_type,
            }
            out = PREOCR_OUT / f"{pdf_path.stem}.json"
            out.write_text(json.dumps(details, indent=2), encoding="utf-8")
    except Exception as exc:
        status = "failed"
        details = {"error": str(exc)}
        logger.exception("PreOCR failed for %s: %s", pdf_path.name, exc)

    logger.info("PreOCR %s: %s", status, pdf_path.name)

    return StageResult(
        file=pdf_path.name,
        source=source,
        stage="preocr",
        status=status,
        duration_ms=int((time.perf_counter() - start) * 1000),
        details=details,
    )


def _stage_ocrmypdf(pdf_path: Path, source: str) -> StageResult:
    start = time.perf_counter()
    out_pdf = OCRMYPDF_OUT / f"{pdf_path.stem}.ocr.pdf"
    details: dict[str, Any] = {"output_pdf": str(out_pdf)}
    logger.info("OCRmyPDF start: %s", pdf_path.name)

    if shutil.which("ocrmypdf") is None:
        logger.warning("OCRmyPDF skipped (command not found): %s", pdf_path.name)
        return StageResult(
            file=pdf_path.name,
            source=source,
            stage="ocrmypdf",
            status="skipped",
            duration_ms=int((time.perf_counter() - start) * 1000),
            details={"reason": "ocrmypdf command not found"},
        )

    try:
        proc = subprocess.run(
            [
                "ocrmypdf",
                "--skip-text",
                "--output-type",
                "pdf",
                str(pdf_path),
                str(out_pdf),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        details["returncode"] = proc.returncode
        details["stdout_tail"] = (proc.stdout or "")[-1000:]
        details["stderr_tail"] = (proc.stderr or "")[-1000:]
        status = "success" if proc.returncode == 0 else "failed"
        # Guard against false-positive return code when dependencies are missing.
        stderr_l = (proc.stderr or "").lower()
        if "missingdependencyerror" in stderr_l or "could not find program" in stderr_l:
            status = "failed"
            details["dependency_error_detected"] = True
        if status == "success" and not out_pdf.exists():
            status = "failed"
            details["dependency_error_detected"] = True
            details["reason"] = "Output PDF not created"
    except Exception as exc:
        status = "failed"
        details = {"error": str(exc)}
        logger.exception("OCRmyPDF failed for %s: %s", pdf_path.name, exc)

    logger.info("OCRmyPDF %s: %s", status, pdf_path.name)

    return StageResult(
        file=pdf_path.name,
        source=source,
        stage="ocrmypdf",
        status=status,
        duration_ms=int((time.perf_counter() - start) * 1000),
        details=details,
    )


def _stage_rostaing(pdf_path: Path, source: str) -> StageResult:
    start = time.perf_counter()
    out_json = ROSTAING_OUT / f"{pdf_path.stem}.json"
    out_txt = ROSTAING_OUT / f"{pdf_path.stem}.txt"
    logger.info("RostaingOCR start: %s", pdf_path.name)

    try:
        rostaing_module = importlib.import_module("rostaing_ocr")
        extractor_cls = getattr(rostaing_module, "ocr_extractor", None)
        if extractor_cls is None:
            raise AttributeError("rostaing_ocr.ocr_extractor is not available")
    except Exception as exc:
        reason = f"Rostaing OCR module unavailable (rostaing_ocr): {exc}"
        out_json.write_text(
            json.dumps(
                {
                    "status": "failed",
                    "reason": reason,
                    "pdf_path": str(pdf_path),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.error("RostaingOCR failed for %s: %s", pdf_path.name, reason)
        return StageResult(
            file=pdf_path.name,
            source=source,
            stage="rostaing_ocr",
            status="failed",
            duration_ms=int((time.perf_counter() - start) * 1000),
            details={"reason": reason, "output_json": str(out_json)},
        )

    try:
        logger.info("RostaingOCR extracting text: %s", pdf_path.name)
        extractor = extractor_cls(
            file_path=str(pdf_path),
            output_file=str(out_txt),
            print_to_console=False,
            save_file=True,
        )
        extracted_text = (getattr(extractor, "extracted_text", "") or "").strip()
        extractor_status = str(getattr(extractor, "status", "unknown"))
        processing_time = float(getattr(extractor, "processing_time", 0.0))
        if extractor_status.lower() != "success" or not extracted_text:
            raise RuntimeError(
                f"RostaingOCR extraction failed (status={extractor_status}, chars={len(extracted_text)})"
            )

        logger.info(
            "RostaingOCR extracted chars=%d in %.3fs for %s",
            len(extracted_text),
            processing_time,
            pdf_path.name,
        )
        out_json.write_text(
            json.dumps(
                {
                    "status": "success",
                    "module_used": "rostaing_ocr",
                    "pdf_path": str(pdf_path),
                    "output_txt": str(out_txt),
                    "chars": len(extracted_text),
                    "processing_time_seconds": processing_time,
                    "extracted_text": extracted_text,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        status = "success"
        details = {
            "output_json": str(out_json),
            "output_txt": str(out_txt),
            "module_used": "rostaing_ocr",
            "chars": len(extracted_text),
            "processing_time_seconds": processing_time,
        }
    except Exception as exc:
        status = "failed"
        details = {"error": str(exc)}
        logger.exception("RostaingOCR failed for %s: %s", pdf_path.name, exc)

    logger.info("RostaingOCR %s: %s", status, pdf_path.name)

    return StageResult(
        file=pdf_path.name,
        source=source,
        stage="rostaing_ocr",
        status=status,
        duration_ms=int((time.perf_counter() - start) * 1000),
        details=details,
    )


def main() -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(description="Run OCR experiments on test sample PDFs.")
    parser.add_argument("--preocr", action="store_true", help="Run PreOCR detection stage")
    parser.add_argument("--ocrmypdf", action="store_true", help="Run OCRmyPDF stage")
    parser.add_argument("--rostaing", action="store_true", help="Run RostaingOCR stage")
    args = parser.parse_args()

    # Default: run all stages
    run_preocr = args.preocr or (not args.preocr and not args.ocrmypdf and not args.rostaing)
    run_ocrmypdf = args.ocrmypdf or (not args.preocr and not args.ocrmypdf and not args.rostaing)
    run_rostaing = args.rostaing or (not args.preocr and not args.ocrmypdf and not args.rostaing)

    # Rostaing is mandatory for this experiment run.
    if not run_rostaing:
        raise RuntimeError(
            "RostaingOCR stage is mandatory and must be enabled. "
            "Run with --rostaing (or run with no flags to run all stages)."
        )

    try:
        importlib.import_module("rostaing_ocr")
    except Exception as exc:
        raise RuntimeError(
            "RostaingOCR is required for this run and no fallback is enabled. "
            "Install with: pip install rostaing-ocr"
        ) from exc

    _prepare_dirs()
    entries = _load_manifest_files()
    if not entries:
        raise RuntimeError(
            "No sample files found. Run: python experiments/ocr_test/sample_selector.py"
        )

    all_results: list[StageResult] = []
    run_start = time.perf_counter()
    logger.info("Loaded %d sample files for OCR experiments", len(entries))
    logger.info(
        "Stage plan (execution order): rostaing_ocr=%s, preocr=%s, ocrmypdf=%s",
        run_rostaing,
        run_preocr,
        run_ocrmypdf,
    )

    for idx, e in enumerate(entries, start=1):
        source = e.get("source", "unknown")
        pdf_path = Path(e["copied_path"])
        if not pdf_path.exists():
            logger.warning(
                "Skipping missing sample file (%d/%d): %s",
                idx,
                len(entries),
                pdf_path,
            )
            continue
        logger.info("Processing file (%d/%d): %s [%s]", idx, len(entries), pdf_path.name, source)

        # Rostaing runs first and is fail-fast for entire pipeline.
        rostaing_result = _stage_rostaing(pdf_path, source)
        all_results.append(rostaing_result)
        if rostaing_result.status != "success":
            logger.error(
                "Aborting run due to RostaingOCR failure on file (%d/%d): %s",
                idx,
                len(entries),
                pdf_path.name,
            )
            raise RuntimeError(
                f"RostaingOCR failed for {pdf_path.name}; stopping entire experiment run."
            )

        if run_preocr:
            all_results.append(_stage_preocr(pdf_path, source))
        if run_ocrmypdf:
            all_results.append(_stage_ocrmypdf(pdf_path, source))
        logger.info("Completed file (%d/%d): %s", idx, len(entries), pdf_path.name)

    summary: dict[str, Any] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_input_files": len(entries),
        "total_stage_runs": len(all_results),
        "total_duration_ms": int((time.perf_counter() - run_start) * 1000),
        "results": [asdict(r) for r in all_results],
    }

    # Aggregate counts
    counts: dict[str, dict[str, int]] = {}
    for r in all_results:
        counts.setdefault(r.stage, {"success": 0, "failed": 0, "skipped": 0})
        counts[r.stage][r.status] += 1
    summary["stage_counts"] = counts

    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Run summary written: {SUMMARY_PATH}")
    logger.info("Run summary written: %s", SUMMARY_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

