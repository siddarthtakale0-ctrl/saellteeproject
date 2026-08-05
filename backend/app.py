"""FastAPI backend for the mission-control demo.

Read-only over the demo slice; no database, no LLM calls, no external requests.
REST serves the data once; the SSE replay endpoint serves TIME: clock ticks plus
the anomaly moments decided by the real `replay()` state machine (§3.2 of the
plan). In production the same process serves the built frontend from
frontend/dist/.

Run: uvicorn backend.app:app --port 8000
"""
from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend import settings
from backend.loader import Slice, load_slice
from backend.replay_driver import agenda_for

app = FastAPI(title="ESA-ADB Trustworthy Agent — demo backend", docs_url="/api/docs",
              openapi_url="/api/openapi.json")
app.add_middleware(GZipMiddleware, minimum_size=2048)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"],
                   allow_headers=["*"])

SLICE: Slice = load_slice(settings.SLICE_DIR)


@app.get("/api/mission")
def mission() -> dict:
    return SLICE.mission.model_dump()


@app.get("/api/events")
def events() -> list[dict]:
    return [e.model_dump() for e in SLICE.index]


@app.get("/api/events/{event_id}")
def event(event_id: int) -> dict:
    entry = SLICE.index_entry(event_id)
    if entry is None:
        raise HTTPException(404, f"unknown event {event_id}")
    out = entry.model_dump()
    detail = SLICE.events.get(event_id)
    if detail is not None:
        out.update({"flag_text": detail.flag_text, "alert_md": detail.alert_md,
                    "brief": detail.brief, "reasons": detail.reasons,
                    "retrieval": detail.retrieval.model_dump(by_alias=True)})
    return out


@app.get("/api/events/{event_id}/telemetry")
def telemetry(event_id: int) -> dict:
    detail = SLICE.events.get(event_id)
    if detail is None:
        raise HTTPException(404, f"event {event_id} has no replay data in this slice")
    return {"event_id": event_id,
            "samples": detail.samples.model_dump(),
            "windows": detail.windows.model_dump(),
            "marked_window_idx": detail.marked_window_idx,
            "attribution": detail.attribution.model_dump()}


@app.get("/api/guardrail")
def guardrail() -> dict:
    return SLICE.guardrail.model_dump()


# ---------------------------------------------------------------------------
# SSE replay — the "other driver" seam (plan §3.2).
# ---------------------------------------------------------------------------
def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.get("/api/replay/{event_id}")
async def replay_stream(event_id: int, request: Request,
                        speed: float = settings.DEFAULT_SPEED,
                        from_idx: int | None = None) -> StreamingResponse:
    detail = SLICE.events.get(event_id)
    if detail is None:
        raise HTTPException(404, f"event {event_id} has no replay data in this slice")
    speed = max(1.0, min(float(speed), settings.MAX_SPEED))

    gap = SLICE.mission.gap
    period = SLICE.mission.sample_period_sec
    lo = detail.windows.start_idx
    hi = lo + len(detail.windows.score) - 1          # last window index in the slice
    agenda = agenda_for(detail.marked_window_idx, gap)  # the REAL machine's moments
    ts = detail.samples.timestamps

    def moment_payload(kind: str) -> dict:
        if kind == "open":
            return {"flag_text": detail.flag_text,
                    "window_idx": detail.marked_window_idx[0]}
        return {"verdict": detail.verdict, "reasons": detail.reasons,
                "brief": detail.brief, "alert_md": detail.alert_md,
                "window_idx": detail.marked_window_idx[-1] + gap}

    start = max(lo, min(from_idx, hi)) if from_idx is not None else lo
    windows_per_tick = speed * settings.TICK_SECONDS / period

    async def gen():
        # State snapshot first: a client seeking past the alarm must not miss it.
        open_now = any(m.kind == "open" and m.window_idx <= start for m in agenda) and \
            not any(m.kind == "close" and m.window_idx <= start for m in agenda)
        yield _sse("state", {"cursor": start, "open": open_now,
                             "flag_text": detail.flag_text if open_now else None,
                             "speed": speed, "from": lo, "to": hi})
        pending = [m for m in agenda if m.window_idx > start]
        cursor = float(start)
        try:
            while cursor < hi:
                await asyncio.sleep(settings.TICK_SECONDS)
                if await request.is_disconnected():
                    return
                cursor = min(cursor + windows_per_tick, float(hi))
                while pending and pending[0].window_idx <= int(cursor):
                    m = pending.pop(0)
                    yield _sse("anomaly_start" if m.kind == "open" else "anomaly_close",
                               moment_payload(m.kind))
                i = int(cursor) - lo
                yield _sse("tick", {"cursor": int(cursor),
                                    "mission_time": ts[min(i, len(ts) - 1)]})
            for m in pending:  # flush any moment at the very edge
                yield _sse("anomaly_start" if m.kind == "open" else "anomaly_close",
                           moment_payload(m.kind))
            yield _sse("done", {"cursor": hi})
        except asyncio.CancelledError:
            return
        except Exception as e:  # noqa: BLE001 -- surface a readable error to the client
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# Production: serve the built frontend (dev uses the Vite server + proxy instead).
if settings.FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=settings.FRONTEND_DIST, html=True),
              name="frontend")
