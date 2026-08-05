"""Path bootstrap — MUST be imported before any `src/` module.

`src/m4_report/pipeline.py` and friends import each other by plain name
(`import config`, `from aggregate import ...`) and rely on `src/` and
`src/m3_attribution/` being on `sys.path`. This module performs that insertion
once, explicitly, so the backend never depends on import-order luck.

Because of this, the names `config`, `aggregate`, `attribute`, `baseline`,
`channels`, `context`, `evaluate` and `visualize` are TAKEN at top level:
no backend module may use them (see docs/FRONTEND_PLAN.md §1).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def ensure_src_on_path() -> None:
    for p in (str(REPO / "src" / "m3_attribution"), str(REPO / "src"), str(REPO)):
        if p not in sys.path:
            sys.path.insert(0, p)
