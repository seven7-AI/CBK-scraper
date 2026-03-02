from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    """Simple JSON log formatter with a fixed set of fields."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        log: Dict[str, Any] = {
            "timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "service": self.service,
            "message": record.getMessage(),
        }

        # Common extra fields for scraping / OCR
        for field in (
            "event",
            "pdf_url",
            "pdf_path",
            "source",
            "file_size_bytes",
            "pages",
            "duration_ms",
        ):
            value = getattr(record, field, None)
            if value is not None:
                log[field] = value

        if record.exc_info:
            log["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log, ensure_ascii=False)


def configure_json_logging(logs_dir: Path, service: str) -> None:
    """Configure root logger with JSON output to stdout and a daily log file."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{service}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Remove any handlers added by basicConfig or previous setup
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = JsonFormatter(service=service)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root.addHandler(stream_handler)
    root.addHandler(file_handler)

