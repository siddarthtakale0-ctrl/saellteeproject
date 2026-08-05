"""Backend success-tests over the committed slice (synthetic or real — schema-equal).

Covers: slice validation, the replay agenda produced by the REAL state machine,
every REST endpoint, and the SSE replay end-to-end (state -> anomaly_start ->
anomaly_close -> done, in order, with the close anchored at last+gap).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from backend import settings  # noqa: E402
from backend.loader import load_slice  # noqa: E402
from backend.replay_driver import agenda_for  # noqa: E402


@pytest.fixture(scope="session")
def slice_():
    return load_slice(settings.SLICE_DIR)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from backend.app import app
    with TestClient(app) as c:
        yield c


# --- slice ----------------------------------------------------------------
def test_slice_validates_and_is_coherent(slice_):
    m = slice_.mission
    assert m.events_total == len(slice_.index)
    assert set(m.replayable_event_ids) == set(slice_.events)
    assert m.autoplay_event_id in slice_.events
    for detail in slice_.events.values():
        detail.assert_close_anchor_inside(m.gap)  # margin guarantee (§2.4)


def test_guardrail_cases_are_block_with_reasons(slice_):
    assert slice_.guardrail.cases, "guardrail showcase is empty"
    for case in slice_.guardrail.cases:
        assert case.verdict == "BLOCK"
        assert case.reasons, f"case {case.id} has no judge reasons"
        assert case.brief.strip()


# --- replay agenda (the REAL machine decides the moments) ------------------
def test_agenda_one_open_one_close_per_event(slice_):
    gap = slice_.mission.gap
    for eid, detail in slice_.events.items():
        agenda = agenda_for(detail.marked_window_idx, gap)
        kinds = [m.kind for m in agenda]
        assert kinds == ["open", "close"], f"event {eid}: agenda {kinds}"
        assert agenda[0].window_idx == detail.marked_window_idx[0]
        assert agenda[1].window_idx == detail.marked_window_idx[-1] + gap


def test_agenda_internal_gaps_do_not_split_events(slice_):
    """A sliced event's marked indices may have small holes (< gap): still ONE event."""
    gap = slice_.mission.gap
    for detail in slice_.events.values():
        marked = detail.marked_window_idx
        diffs = [b - a for a, b in zip(marked, marked[1:])]
        assert all(d <= gap for d in diffs), "slice contains a multi-event stream"


def test_agenda_splits_when_gap_exceeded(slice_):
    gap = slice_.mission.gap
    stream = [10, 11, 12, 12 + gap + 1, 12 + gap + 2]  # two events by contract
    agenda = agenda_for(stream, gap)
    assert [m.kind for m in agenda] == ["open", "close", "open", "close"]


# --- REST ------------------------------------------------------------------
def test_mission_endpoint(client, slice_):
    r = client.get("/api/mission")
    assert r.status_code == 200
    body = r.json()
    assert body["events_total"] == slice_.mission.events_total
    assert body["headline"]["false_alarms"]["scope"]


def test_events_endpoints(client, slice_):
    r = client.get("/api/events")
    assert r.status_code == 200 and len(r.json()) == slice_.mission.events_total

    rep = slice_.mission.autoplay_event_id
    r = client.get(f"/api/events/{rep}")
    assert r.status_code == 200
    body = r.json()
    assert body["replayable"] and body["alert_md"] and body["flag_text"]

    non_rep = next(e.event_id for e in slice_.index if not e.replayable)
    body = client.get(f"/api/events/{non_rep}").json()
    assert not body["replayable"] and "alert_md" not in body

    assert client.get("/api/events/99999").status_code == 404


def test_telemetry_endpoint_alignment(client, slice_):
    eid = slice_.mission.autoplay_event_id
    r = client.get(f"/api/events/{eid}/telemetry")
    assert r.status_code == 200
    t = r.json()
    n = len(t["samples"]["timestamps"])
    assert t["windows"]["start_idx"] == t["samples"]["start_idx"]
    assert len(t["windows"]["score"]) == len(t["windows"]["p"]) <= n
    assert len(t["attribution"]["matrix"]) == len(t["marked_window_idx"])
    for vals in t["samples"]["channels"].values():
        assert len(vals) == n

    non_rep = next(e.event_id for e in slice_.index if not e.replayable)
    assert client.get(f"/api/events/{non_rep}/telemetry").status_code == 404


def test_guardrail_endpoint(client):
    r = client.get("/api/guardrail")
    assert r.status_code == 200
    assert all(c["verdict"] == "BLOCK" for c in r.json()["cases"])


# --- SSE replay end-to-end -------------------------------------------------
def _read_sse(client, url: str, max_events: int = 500) -> list[tuple[str, str]]:
    events, event_name = [], None
    with client.stream("GET", url) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        for line in r.iter_lines():
            if line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: ") and event_name:
                events.append((event_name, line[6:]))
                if event_name in ("done", "error") or len(events) >= max_events:
                    return events
    return events


def test_replay_sse_full_run(client, slice_):
    import json as j
    eid = slice_.mission.autoplay_event_id
    detail = slice_.events[eid]
    events = _read_sse(client, f"/api/replay/{eid}?speed={settings.MAX_SPEED}")
    names = [n for n, _ in events]

    assert names[0] == "state"
    assert names[-1] == "done"
    assert names.count("anomaly_start") == 1 and names.count("anomaly_close") == 1
    assert names.index("anomaly_start") < names.index("anomaly_close")

    start = j.loads(dict(events)["anomaly_start"])
    close = j.loads(dict(events)["anomaly_close"])
    assert start["flag_text"] == detail.flag_text
    assert close["verdict"] == detail.verdict
    assert close["window_idx"] == detail.marked_window_idx[-1] + slice_.mission.gap


def test_replay_sse_seek_past_alarm_gets_open_state(client, slice_):
    import json as j
    eid = slice_.mission.autoplay_event_id
    detail = slice_.events[eid]
    mid = (detail.marked_window_idx[0] + detail.marked_window_idx[-1]) // 2
    events = _read_sse(client, f"/api/replay/{eid}?speed={settings.MAX_SPEED}&from_idx={mid}")
    state = j.loads(events[0][1])
    assert state["open"] is True and state["flag_text"] == detail.flag_text
    names = [n for n, _ in events]
    assert names.count("anomaly_start") == 0  # already open: no spurious re-open
    assert names.count("anomaly_close") == 1 and names[-1] == "done"


def test_replay_sse_unknown_event(client):
    assert client.get("/api/replay/99999").status_code == 404
