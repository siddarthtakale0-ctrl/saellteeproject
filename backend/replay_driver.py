"""The backend as "another driver" of the pipeline's streaming state machine.

`replay()` (src/m4_report/pipeline.py) is the no-lookahead state machine that
decides WHEN an anomaly event opens and closes. Here it runs to completion over
the sliced event's marked window indices (microseconds — it only consumes
indices), and its callbacks record the AGENDA of moments. The SSE generator then
paces emission against that agenda; the moments are decided by the real machine,
never by the frontend (docs/FRONTEND_PLAN.md §3.2).

Close anchor honesty: on a single-event stream `on_close` fires via the
end-of-stream flush, but the machine would OBSERVE the close only once the quiet
gap has elapsed — so the close moment is anchored at `last + gap`.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.bootstrap import ensure_src_on_path

ensure_src_on_path()

from m4_report.pipeline import replay  # noqa: E402  (the real state machine)


@dataclass(frozen=True)
class Moment:
    kind: str        # "open" | "close"
    window_idx: int  # global window index at which the moment fires


def agenda_for(marked_window_idx: list[int], gap: int) -> list[Moment]:
    """Run the real replay() over the event's marked indices; return its moments."""
    moments: list[Moment] = []

    def on_open(first_idx: int) -> None:
        moments.append(Moment("open", first_idx))

    def on_close(first_idx: int, last_idx: int) -> None:
        moments.append(Moment("close", last_idx + gap))

    replay(iter(marked_window_idx), on_open, on_close, gap=gap)
    return moments
