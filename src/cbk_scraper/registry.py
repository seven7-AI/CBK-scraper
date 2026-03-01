"""SQLite registry for downloaded PDFs – never download the same URL twice."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse


def _normalize_url(url: str, base: str = "https://www.centralbank.go.ke") -> str:
    """Strip fragment and query; resolve relative URLs; collapse double slashes in path."""
    u = url.strip()
    if u.startswith("/"):
        u = urljoin(base, u)
    parsed = urlparse(u)
    path = parsed.path.replace("//", "/") if "//" in parsed.path else parsed.path
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def _ensure_db(registry_path: Path) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(registry_path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS downloads (
                url TEXT PRIMARY KEY,
                local_path TEXT NOT NULL,
                downloaded_at TEXT NOT NULL,
                source TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def already_downloaded(
    registry_path: Path, url: str, base_url: str = "https://www.centralbank.go.ke"
) -> bool:
    """Return True if this URL was already scraped/downloaded in a previous run."""
    _ensure_db(registry_path)
    norm = _normalize_url(url, base_url)
    conn = sqlite3.connect(str(registry_path))
    try:
        row = conn.execute("SELECT 1 FROM downloads WHERE url = ?", (norm,)).fetchone()
        return row is not None
    finally:
        conn.close()


def mark_downloaded(
    registry_path: Path,
    url: str,
    local_path: str | Path,
    source: str,
    base_url: str = "https://www.centralbank.go.ke",
) -> None:
    """Record a successful download. Idempotent (INSERT OR IGNORE)."""
    _ensure_db(registry_path)
    norm = _normalize_url(url, base_url)
    local_str = str(Path(local_path).resolve())
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(str(registry_path))
    try:
        conn.execute(
            "INSERT OR IGNORE INTO downloads (url, local_path, downloaded_at, source) VALUES (?, ?, ?, ?)",
            (norm, local_str, now, source),
        )
        conn.commit()
    finally:
        conn.close()


def get_registry_path(config: Optional[dict] = None) -> Path:
    """Resolve registry DB path from config."""
    from .config import get_paths
    return get_paths(config or None)["registry_db"]
