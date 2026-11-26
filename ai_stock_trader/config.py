"""Small local .env loader; CI continues to provide credentials as environment variables."""

from __future__ import annotations

import os
from pathlib import Path


def load_local_environment(path: Path | str = ".env") -> None:
    """Load simple KEY=VALUE entries without replacing already-set environment values."""
    env_path = Path(path)
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key, value = key.strip(), value.strip()
        if key and key.replace("_", "").isalnum():
            os.environ.setdefault(key, value.strip("\"'"))
