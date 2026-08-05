"""Load the demo slice into memory at startup, validated against the schema.

The backend is read-only: this is its ONLY disk access. A slice that does not
validate refuses to boot — better a loud failure at startup than a misaligned
chart in front of an evaluator.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.slice_schema import (EventDetail, Guardrail, IndexEntry, Mission,
                                  validate_slice_dir)


@dataclass(frozen=True)
class Slice:
    mission: Mission
    index: list[IndexEntry]
    events: dict[int, EventDetail]
    guardrail: Guardrail

    def index_entry(self, event_id: int) -> IndexEntry | None:
        return next((e for e in self.index if e.event_id == event_id), None)


def load_slice(slice_dir: Path) -> Slice:
    if not (slice_dir / "mission.json").exists():
        raise FileNotFoundError(
            f"No demo slice at {slice_dir}. Generate one with "
            f"`python scripts/build_demo_slice.py --synthetic` (no dataset needed) "
            f"or the real one on a machine holding the artifacts.")
    mission, index, events, guardrail = validate_slice_dir(slice_dir)
    return Slice(mission=mission, index=index, events=events, guardrail=guardrail)
