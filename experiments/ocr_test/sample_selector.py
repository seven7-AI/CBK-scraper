from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOWNLOADS_BONDS = PROJECT_ROOT / "downloads" / "bonds"
DOWNLOADS_BILLS = PROJECT_ROOT / "downloads" / "bills"

TEST_ROOT = PROJECT_ROOT / "experiments" / "ocr_test"
INPUT_BONDS = TEST_ROOT / "input" / "bonds"
INPUT_BILLS = TEST_ROOT / "input" / "bills"
META_DIR = TEST_ROOT / "metadata"
MANIFEST_PATH = META_DIR / "sample_manifest.json"


@dataclass
class SampleEntry:
    source: str
    source_path: str
    copied_path: str
    filename: str
    size_bytes: int
    mtime_utc: str


def _latest_pdfs(folder: Path, count: int) -> list[Path]:
    files = [p for p in folder.glob("*.pdf") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:count]


def _prepare_dirs() -> None:
    INPUT_BONDS.mkdir(parents=True, exist_ok=True)
    INPUT_BILLS.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)


def _clear_previous_samples() -> None:
    for target in (INPUT_BONDS, INPUT_BILLS):
        if target.exists():
            for f in target.glob("*.pdf"):
                f.unlink()


def _copy_samples(paths: list[Path], dest_dir: Path, source: str) -> list[SampleEntry]:
    entries: list[SampleEntry] = []
    for src in paths:
        dst = dest_dir / src.name
        shutil.copy2(src, dst)
        st = dst.stat()
        entries.append(
            SampleEntry(
                source=source,
                source_path=str(src.resolve()),
                copied_path=str(dst.resolve()),
                filename=dst.name,
                size_bytes=st.st_size,
                mtime_utc=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            )
        )
    return entries


def main() -> int:
    if not DOWNLOADS_BONDS.exists() or not DOWNLOADS_BILLS.exists():
        raise FileNotFoundError("downloads/bonds or downloads/bills does not exist.")

    _prepare_dirs()
    _clear_previous_samples()

    bonds = _latest_pdfs(DOWNLOADS_BONDS, 5)
    bills = _latest_pdfs(DOWNLOADS_BILLS, 5)

    if len(bonds) < 5 or len(bills) < 5:
        raise RuntimeError(
            f"Insufficient PDFs for balanced sample. bonds={len(bonds)}, bills={len(bills)}"
        )

    entries = []
    entries.extend(_copy_samples(bonds, INPUT_BONDS, "bonds"))
    entries.extend(_copy_samples(bills, INPUT_BILLS, "bills"))

    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "selection_strategy": "balanced_latest_mtime_5_plus_5",
        "total_files": len(entries),
        "entries": [asdict(e) for e in entries],
    }
    MANIFEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Sample manifest written: {MANIFEST_PATH}")
    print(f"Selected {len(entries)} files (5 bonds + 5 bills).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

