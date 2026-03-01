"""Load and resolve configuration (YAML + env overrides)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT: Path | None = None


def _find_project_root() -> Path:
    global _PROJECT_ROOT
    if _PROJECT_ROOT is not None:
        return _PROJECT_ROOT
    cur = Path(__file__).resolve().parent
    for _ in range(4):
        if (cur / "config.yaml").exists():
            _PROJECT_ROOT = cur
            return cur
        cur = cur.parent
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    return _PROJECT_ROOT


def load_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load config from config.yaml; resolve paths relative to project root."""
    root = _find_project_root()
    path = Path(config_path) if config_path else root / "config.yaml"
    if not path.is_absolute():
        path = root / path
    cfg: dict[str, Any] = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    if os.environ.get("CBK_DOWNLOADS_ROOT"):
        cfg.setdefault("downloads", {})["root"] = os.environ["CBK_DOWNLOADS_ROOT"]
    if os.environ.get("CBK_DATA_DIR"):
        cfg["data_dir"] = os.environ["CBK_DATA_DIR"]
    if os.environ.get("CBK_REGISTRY_DB"):
        cfg["registry_db"] = os.environ["CBK_REGISTRY_DB"]
    if os.environ.get("CBK_LOGS_DIR"):
        cfg["logs_dir"] = os.environ["CBK_LOGS_DIR"]
    return cfg


def get_paths(cfg: dict[str, Any] | None = None) -> dict[str, Path]:
    """Return resolved paths (absolute) for downloads, data, logs, registry."""
    if cfg is None:
        cfg = load_config()
    root = _find_project_root()

    downloads_cfg = cfg.get("downloads") or {}
    if isinstance(downloads_cfg, str):
        downloads_root = root / downloads_cfg
        bonds_dir = downloads_root / "bonds"
        bills_dir = downloads_root / "bills"
    else:
        downloads_root = root / downloads_cfg.get("root", "downloads")
        bonds_dir = root / downloads_cfg.get("bonds", "downloads/bonds")
        bills_dir = root / downloads_cfg.get("bills", "downloads/bills")
    if not bonds_dir.is_absolute():
        bonds_dir = root / bonds_dir
    if not bills_dir.is_absolute():
        bills_dir = root / bills_dir

    data_dir = Path(cfg.get("data_dir", "data"))
    data_dir = root / data_dir if not data_dir.is_absolute() else data_dir
    registry_db = Path(cfg.get("registry_db", "data/registry.db"))
    registry_db = root / registry_db if not registry_db.is_absolute() else registry_db
    logs_dir = Path(cfg.get("logs_dir", "logs"))
    logs_dir = root / logs_dir if not logs_dir.is_absolute() else logs_dir

    return {
        "project_root": root,
        "downloads_root": downloads_root,
        "bonds_dir": bonds_dir,
        "bills_dir": bills_dir,
        "data_dir": data_dir,
        "registry_db": registry_db,
        "logs_dir": logs_dir,
    }


def get_config() -> dict[str, Any]:
    """Full config with paths resolved."""
    cfg = load_config()
    cfg["_paths"] = get_paths(cfg)
    return cfg
