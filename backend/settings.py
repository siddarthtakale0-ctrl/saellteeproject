"""Backend settings — paths and defaults. (Named `settings`, never `config`: that
top-level name belongs to src/config.py once the pipeline is imported.)"""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SLICE_DIR = Path(os.getenv("ESA_DEMO_SLICE", REPO / "data" / "demo_slice"))
FRONTEND_DIST = REPO / "frontend" / "dist"

DEFAULT_SPEED = 3600.0   # mission seconds per real second
MAX_SPEED = 100_000.0
TICK_SECONDS = 0.25      # real-time cadence of SSE `tick` events (payload is tiny)
