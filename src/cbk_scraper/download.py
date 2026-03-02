"""Download PDFs with registry check and retries; never download the same file twice."""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from datetime import datetime, timezone

import httpx

from cbk_common.redis_client import get_redis

from .config import load_config, get_paths
from . import registry

logger = logging.getLogger(__name__)


def _sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"|?*\\\x00-\x1f]', "_", name)
    name = name.strip(". ") or "download"
    return name[:200]


def _filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    name = path.split("/")[-1] if "/" in path else path
    if not name or not name.endswith(".pdf"):
        name = name or "document.pdf"
    if not name.lower().endswith(".pdf"):
        name = name + ".pdf"
    return _sanitize_filename(name)


def download_pdfs(
    urls: list[str],
    output_dir: Path,
    source: str,
    *,
    registry_path: Path | None = None,
    base_url: str | None = None,
    timeout_sec: float | None = None,
    retries: int | None = None,
    retry_backoff_sec: float | None = None,
    delay_between_sec: float | None = None,
) -> tuple[int, int, int]:
    """
    Download each URL to output_dir only if not already in registry (previous run).
    Returns (downloaded_count, skipped_count, failed_count).
    """
    cfg = load_config()
    paths = get_paths(cfg)
    reg_path = registry_path or paths["registry_db"]
    base = base_url or cfg.get("base_url", "https://www.centralbank.go.ke")
    timeout = timeout_sec if timeout_sec is not None else cfg.get("download_timeout_sec", 60)
    max_retries = retries if retries is not None else cfg.get("download_retries", 3)
    backoff = retry_backoff_sec if retry_backoff_sec is not None else cfg.get("download_retry_backoff_sec", 2.0)
    delay = delay_between_sec if delay_between_sec is not None else cfg.get("delay_between_pdf_requests_sec", 0.5)
    user_agent = cfg.get("user_agent", "CBK-Scraper/1.0")

    redis_client = get_redis()
    urls_key = "cbk:scraper:downloaded_urls"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = skipped = failed = 0

    with httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": user_agent},
    ) as client:
        for url in urls:
            if delay > 0:
                time.sleep(delay)
            norm_url = registry._normalize_url(url, base)  # type: ignore[attr-defined]
            if redis_client is not None and redis_client.sismember(urls_key, norm_url):
                logger.debug("Redis dedup: already downloaded (previous run): %s", url)
                skipped += 1
                continue
            if registry.already_downloaded(reg_path, url, base):
                logger.debug("SQLite dedup: already downloaded (previous run): %s", url)
                skipped += 1
                continue
            filename = _filename_from_url(url)
            local_path = output_dir / filename
            if local_path.exists() and not registry.already_downloaded(reg_path, url, base):
                try:
                    from hashlib import sha256
                    h = sha256(url.encode()).hexdigest()[:8]
                    stem = local_path.stem + "_" + h
                    local_path = output_dir / (stem + local_path.suffix)
                except Exception:
                    pass
            ok = False
            for attempt in range(max_retries):
                try:
                    r = client.get(url)
                    r.raise_for_status()
                    local_path.write_bytes(r.content)
                    registry.mark_downloaded(reg_path, url, local_path, source, base)
                    # Best-effort Redis update
                    if redis_client is not None:
                        redis_client.sadd(urls_key, norm_url)
                    logger.info(
                        "Downloaded: %s -> %s",
                        url,
                        local_path.name,
                        extra={
                            "event": "download_finished",
                            "pdf_url": url,
                            "pdf_path": str(local_path),
                            "source": source,
                            "file_size_bytes": local_path.stat().st_size,
                        },
                    )
                    downloaded += 1
                    ok = True
                    break
                except Exception as e:
                    logger.warning("Attempt %d for %s: %s", attempt + 1, url, e)
                    if attempt < max_retries - 1:
                        time.sleep(backoff)
            if not ok:
                if local_path.exists():
                    try:
                        local_path.unlink()
                    except OSError:
                        pass
                failed += 1
                logger.error("Failed to download: %s", url)

    return downloaded, skipped, failed
