"""Project path helpers for backend runtime files."""

from __future__ import annotations

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
RUNTIME_DIR = DATA_DIR / "runtime"
LOG_DIR = RUNTIME_DIR / "logs"
STATE_DIR = RUNTIME_DIR / "state"


def ensure_runtime_dirs() -> None:
    for path in (DATA_DIR, RUNTIME_DIR, LOG_DIR, STATE_DIR):
        path.mkdir(parents=True, exist_ok=True)
