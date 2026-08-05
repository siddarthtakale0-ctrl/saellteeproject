"""Schema of the demo slice — the single contract between builder, backend and frontend.

Every file under ``data/demo_slice/`` must validate against these models. The builder
(`scripts/build_demo_slice.py`) writes them, the backend loader refuses to boot on a
mismatch, and the tests exercise both. Alignment invariants (window index == index of
its first sample, attribution rows == marked windows, close anchor inside the slice)
live here as validators so a malformed slice fails at load time, not at render time.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TimeRange(BaseModel):
    start: str  # ISO timestamp
    end: str


class HeadlineFalseAlarms(BaseModel):
    value: int
    normal_windows: int
    scope: str  # human sentence: where this number was measured


class HeadlineBriefs(BaseModel):
    passed: int
    total: int
    scope: str


class Headline(BaseModel):
    false_alarms: HeadlineFalseAlarms
    briefs: HeadlineBriefs


class About(BaseModel):
    f05: float
    f05_scope: str  # the F0.5 is measured on the FULL test set — not the minimap range
    note: str


class Mission(BaseModel):
    """data/demo_slice/mission.json"""
    synthetic: bool
    channels: list[str]
    window_size: int
    gap: int
    alpha_star: float
    sample_period_sec: float
    time_range: TimeRange  # the range the minimap covers (third 3 on real data)
    headline: Headline
    about: About
    events_total: int
    replayable_event_ids: list[int]
    autoplay_event_id: int  # the event the frontend replays on page load

    @model_validator(mode="after")
    def _autoplay_replayable(self) -> "Mission":
        if self.autoplay_event_id not in self.replayable_event_ids:
            raise ValueError("autoplay_event_id must be replayable")
        return self


class StartRecord(BaseModel):
    """Verbatim record from m4_start_windows.json — the INPUT of start_flag()."""
    event_id: int
    window_idx: int
    t: str
    score: float
    p: float
    confidence: float
    intensity_pct_vs_calib: float
    intensity_label: str
    channels: list[list]  # [[channel_name, pct], ...] first-window ranking


class EventContext(BaseModel):
    """Verbatim M3 context (the whitelist of src/m3_attribution/context.py)."""
    event_id: int
    start: str
    end: str
    duration_sec: float
    n_windows: int
    m2_confidence: float
    intensity: float
    priority: float
    top_channels: list[list]
    dominant_channels: list[str]
    localization: str
    shared_relations: dict
    window_span: list[int]


class IndexEntry(BaseModel):
    """One row of events_index.json — enough for the minimap + tooltips."""
    event_id: int
    verdict: str  # PASS | FLAG | BLOCK
    replayable: bool
    context: EventContext
    start_record: StartRecord


class Samples(BaseModel):
    start_idx: int  # GLOBAL index of the first sample in these arrays
    timestamps: list[str]
    channels: dict[str, list[float]]

    @model_validator(mode="after")
    def _aligned(self) -> "Samples":
        n = len(self.timestamps)
        for ch, vals in self.channels.items():
            if len(vals) != n:
                raise ValueError(f"{ch}: {len(vals)} samples != {n} timestamps")
        return self


class Windows(BaseModel):
    start_idx: int  # GLOBAL index of the first window; == Samples.start_idx (stride 1)
    score: list[float]
    p: list[Optional[float]]  # None where the window falls outside third 3

    @model_validator(mode="after")
    def _aligned(self) -> "Windows":
        if len(self.p) != len(self.score):
            raise ValueError(f"p ({len(self.p)}) != score ({len(self.score)})")
        return self


class Attribution(BaseModel):
    window_idx: list[int]  # GLOBAL indices — the event's marked windows, ordered
    channels: list[str]
    matrix: list[list[float]]  # (n_marked, n_channels) — pct share per window

    @model_validator(mode="after")
    def _shape(self) -> "Attribution":
        if len(self.matrix) != len(self.window_idx):
            raise ValueError(f"matrix rows {len(self.matrix)} != windows {len(self.window_idx)}")
        for row in self.matrix:
            if len(row) != len(self.channels):
                raise ValueError(f"matrix row width {len(row)} != channels {len(self.channels)}")
        return self


class Neighbor(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    sim: float
    channels: list[str]
    klass: str = Field(alias="class")
    category: str
    locality: str


class Retrieval(BaseModel):
    neighbors: list[Neighbor]
    max_sim: float
    novelty: float


class EventDetail(BaseModel):
    """data/demo_slice/events/{id}.json — everything needed to replay one event."""
    event_id: int
    samples: Samples
    windows: Windows
    marked_window_idx: list[int]
    attribution: Attribution
    retrieval: Retrieval
    alert_md: str
    brief: Optional[str]
    verdict: str
    reasons: list[str]
    flag_text: str

    @model_validator(mode="after")
    def _invariants(self) -> "EventDetail":
        s, w = self.samples, self.windows
        if w.start_idx != s.start_idx:
            raise ValueError("windows.start_idx != samples.start_idx (stride-1 axis broken)")
        n_samples = len(s.timestamps)
        n_windows = len(w.score)
        # window i spans samples [i, i+WS); the slice must contain whole windows only.
        if n_windows > n_samples:
            raise ValueError(f"{n_windows} windows cannot fit in {n_samples} samples")
        marked = self.marked_window_idx
        if marked != sorted(marked):
            raise ValueError("marked_window_idx not sorted")
        lo, hi = w.start_idx, w.start_idx + n_windows
        if marked and (marked[0] < lo or marked[-1] >= hi):
            raise ValueError(f"marked windows [{marked[0]},{marked[-1]}] outside slice [{lo},{hi})")
        if self.attribution.window_idx != marked:
            raise ValueError("attribution.window_idx != marked_window_idx")
        return self

    def assert_close_anchor_inside(self, gap: int) -> None:
        """Margin guarantee (§2.4 of the plan): last marked + gap falls inside the slice."""
        if not self.marked_window_idx:
            return
        anchor = self.marked_window_idx[-1] + gap
        hi = self.windows.start_idx + len(self.windows.score)
        if anchor >= hi:
            raise ValueError(f"close anchor {anchor} outside slice (max window {hi - 1}); "
                             f"right margin must be >= gap={gap}")


class GuardrailCase(BaseModel):
    id: str
    title: str  # short human label for the button
    tests: str  # what this lie exercises (from the golden set)
    brief: str  # the tampered brief
    verdict: str  # the judge's real verdict (BLOCK)
    reasons: list[str]  # the judge's real reasons
    source: str  # "golden" | "pipeline"


class Guardrail(BaseModel):
    """data/demo_slice/guardrail_block.json"""
    synthetic_cases: bool  # the LIES are hand-planted (always true, by design)
    evidence_ref: str
    cases: list[GuardrailCase]


def validate_slice_dir(slice_dir) -> tuple[Mission, list[IndexEntry], dict[int, EventDetail], Guardrail]:
    """Load + validate a whole slice directory; raise with a precise message on mismatch."""
    import json
    from pathlib import Path

    d = Path(slice_dir)
    mission = Mission(**json.loads((d / "mission.json").read_text()))
    index = [IndexEntry(**e) for e in json.loads((d / "events_index.json").read_text())]
    guardrail = Guardrail(**json.loads((d / "guardrail_block.json").read_text()))

    events: dict[int, EventDetail] = {}
    for eid in mission.replayable_event_ids:
        ev = EventDetail(**json.loads((d / "events" / f"{eid}.json").read_text()))
        ev.assert_close_anchor_inside(mission.gap)
        events[eid] = ev

    ids = {e.event_id for e in index}
    if len(index) != mission.events_total:
        raise ValueError(f"index has {len(index)} events, mission says {mission.events_total}")
    missing = set(mission.replayable_event_ids) - ids
    if missing:
        raise ValueError(f"replayable ids {missing} not present in events_index")
    for e in index:
        if e.replayable != (e.event_id in events):
            raise ValueError(f"event {e.event_id}: replayable flag inconsistent with files")
    return mission, index, events, guardrail
