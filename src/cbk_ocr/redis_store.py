from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from cbk_common.redis_client import get_redis

logger = logging.getLogger(__name__)

PROCESSED_FILES_KEY = "cbk:ocr:processed_files"
PROCESSED_URLS_KEY = "cbk:ocr:processed_urls"


def is_processed(file_id: str) -> bool:
    r = get_redis()
    if r is None:
        return False
    try:
        return bool(r.sismember(PROCESSED_FILES_KEY, file_id))
    except Exception as exc:
        logger.warning("Redis is_processed failed: %s", exc)
        return False


def mark_processed(file_id: str, url: Optional[str], source: str) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.sadd(PROCESSED_FILES_KEY, file_id)
        if url:
            r.sadd(PROCESSED_URLS_KEY, url)

        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        run_key = f"cbk:ocr:run:{date_str}"
        r.hincrby(run_key, "processed", 1)
        r.hincrby(run_key, f"processed_{source}", 1)
        # keep run stats for 14 days
        r.expire(run_key, 14 * 24 * 3600)
    except Exception as exc:
        logger.warning("Redis mark_processed failed: %s", exc)

