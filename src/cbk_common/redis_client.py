from __future__ import annotations

import logging
import os
from typing import Optional

import redis

logger = logging.getLogger(__name__)

_CLIENT: Optional[redis.Redis] = None


def get_redis() -> Optional[redis.Redis]:
    """Return a shared Redis client or None if not configured/reachable."""
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    url = os.getenv("REDIS_URL")
    try:
        if url:
            client = redis.from_url(url, decode_responses=True)
        else:
            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", "6379"))
            db = int(os.getenv("REDIS_DB", "0"))
            client = redis.Redis(host=host, port=port, db=db, decode_responses=True)

        # Light health check; if this fails we treat Redis as unavailable.
        client.ping()
        _CLIENT = client
        logger.info("Connected to Redis at %s", url or f"{host}:{port}/{db}")
    except Exception as exc:  # Redis not required for scraper to function
        logger.warning("Redis not available (%s); proceeding without Redis.", exc)
        _CLIENT = None
    return _CLIENT

