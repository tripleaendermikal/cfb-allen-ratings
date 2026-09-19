"""Shared paths for the in-season pipeline and CFB_DATA_ROOT."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def data_root() -> Path:
    """Directory for large CSV inputs/outputs (default: parent of this repo)."""
    env = os.environ.get("CFB_DATA_ROOT")
    if env:
        return Path(env)
    return REPO_ROOT.parent
