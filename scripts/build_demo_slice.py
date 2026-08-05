#!/usr/bin/env python3
"""Build data/demo_slice/ — the committed dataset that powers the web demo.

Two modes:

  python scripts/build_demo_slice.py --synthetic
      Generates a schema-identical synthetic slice (sinusoids + injected anomalies).
      Needs NO dataset, NO artifacts — runs anywhere. Used to develop backend+frontend.
      The guardrail cases are still REAL: golden-set briefs + the judge's cached
      verdicts, both committed in the repo.

  python scripts/build_demo_slice.py
      The real thing. Runs ONLY on a machine with the full artifacts (dataset +
      data/cached/*). Re-computes what no artifact stores (per-window attribution,
      retrieval, rendered alert) and freezes everything the frontend needs.
      Golden test: the re-rendered alert of event 33 must be byte-identical to the
      "Moment 2" section of docs/m4_alert_example.md.

The output validates against backend/slice_schema.py in both modes; the backend
refuses to boot on a slice that does not.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))            # backend.slice_schema
sys.path.insert(0, str(REPO / "src"))    # config + project modules (path hack heritage)
sys.path.insert(0, str(REPO / "src" / "m3_attribution"))  # M3 imports itself by plain name

from backend.slice_schema import validate_slice_dir  # noqa: E402

SLICE_DIR = REPO / "data" / "demo_slice"
GOLDEN_JSON = REPO / "src" / "m4_report" / "evals" / "golden.json"
LLM_CACHE_JSON = REPO / "data" / "cached" / "m4_llm_cache.json"

# Guardrail showcase: which golden lies become buttons (id -> short UI title).
SHOWCASE_CASES = {
    "D2": "Alucinación semántica (sin token falso)",
    "D4": "Hipótesis vendida como hecho",
    "D6": "Novedad deshonesta",
    "D9": "«Resuelto» que los datos no dicen",
}
# The pipeline's own dirty brief (pipeline.py, forced-BLOCK check) as a fifth case.
PIPELINE_DIRTY_BRIEF = ("The event on channel_18 closed. The pattern is consistent with a "
                        "thermal regulation fault affecting the battery subsystem.")

MARGIN_TARGET = 2000  # samples of context per side (real mode), truncated per §2.4


# ---------------------------------------------------------------------------
# Guardrail cases: real briefs (golden.json) + real judge verdicts (LLM cache).
# Works in BOTH modes because both files are committed. Matching: the judge's
# reasons quote the offending phrases verbatim -> match each BLOCK verdict in the
# cache to the golden brief that contains the longest quoted fragment.
# ---------------------------------------------------------------------------
def _quoted_fragments(reasons: list[str]) -> list[str]:
    frags: list[str] = []
    for r in reasons:
        frags += re.findall(r'"([^"]{10,})"', r)
        frags += re.findall(r"“([^”]{10,})”", r)
    return frags


def build_guardrail_cases() -> dict:
    """Pair each showcase lie with its cached judge verdict, one-to-one.

    A verdict is a candidate for a brief only if EVERY phrase it quotes appears
    verbatim in that brief; assignment is then greedy best-score with uniqueness.
    Caveat (documented): two cases planting the SAME lie text (D2 and the pipeline
    dirty brief) admit each other's verdicts — the pairing between those two may
    swap, but both verdicts are real judge output for that same lie type.
    """
    golden = json.loads(GOLDEN_JSON.read_text())["cases"]
    cache = json.loads(LLM_CACHE_JSON.read_text())
    block_verdicts = [v for v in cache.values()
                      if isinstance(v, dict) and v.get("verdict") == "BLOCK"]

    wanted = [{"id": g["id"], "title": SHOWCASE_CASES[g["id"]], "tests": g["tests"],
               "brief": g["brief"], "source": "golden"}
              for g in golden if g["id"] in SHOWCASE_CASES]
    wanted.append({"id": "PIPE", "title": "Causa raíz inventada",
                   "tests": "the pipeline's own forced-BLOCK check (root cause)",
                   "brief": PIPELINE_DIRTY_BRIEF, "source": "pipeline"})

    pairs = []  # (score, case_pos, verdict_pos)
    for ci, c in enumerate(wanted):
        for vi, v in enumerate(block_verdicts):
            frags = _quoted_fragments(v.get("reasons", []))
            if frags and all(f in c["brief"] for f in frags):
                pairs.append((sum(map(len, frags)), ci, vi))
    pairs.sort(reverse=True)

    assigned_case: dict[int, int] = {}
    used_verdicts: set[int] = set()
    for score, ci, vi in pairs:
        if ci in assigned_case or vi in used_verdicts or score < 15:
            continue
        assigned_case[ci] = vi
        used_verdicts.add(vi)

    cases = []
    for ci, c in enumerate(wanted):
        assert ci in assigned_case, (
            f"case {c['id']}: no cached judge verdict quotes its brief exclusively -- "
            f"the committed LLM cache no longer covers the golden set")
        v = block_verdicts[assigned_case[ci]]
        cases.append({**c, "verdict": "BLOCK", "reasons": v["reasons"]})

    return {"synthetic_cases": True,  # the LIES are hand-planted by design
            "evidence_ref": "event_33", "cases": cases}


# ---------------------------------------------------------------------------
# Synthetic mode
# ---------------------------------------------------------------------------
def build_synthetic() -> None:
    import config  # noqa: PLC0415 -- src on path; anchor constants (channels, WS, gap)
    from aggregate import DEFAULT_GAP  # noqa: PLC0415
    from m4_report.alert import render_flag, start_flag  # noqa: PLC0415

    rng = np.random.default_rng(42)
    WS = config.WINDOW_SIZE
    CHANNELS = config.TARGET_CHANNELS
    PERIOD = 18.0  # seconds per sample, mirroring the real cadence
    T0 = np.datetime64("2003-01-01T00:00:00")

    def iso(sample_idx: int) -> str:
        return str(T0 + np.timedelta64(int(sample_idx * PERIOD), "s"))

    # 12 synthetic events on a shared global axis; 3 replayable.
    # (id, start_sample, n_marked, injected channel indices, replayable)
    specs = [
        (0, 8_000, 300, [2, 5], False),      (1, 30_000, 900, [0, 1], False),
        (2, 55_000, 450, [7], False),        (3, 80_000, 1400, [0, 5, 6], True),
        (4, 110_000, 250, [9], False),       (5, 140_000, 700, [3, 4], False),
        (6, 170_000, 500, [10], False),      (7, 200_000, 6200, [0, 4, 5, 6], True),
        (8, 245_000, 350, [8], False),       (9, 270_000, 1100, [1, 2], True),
        (10, 300_000, 600, [6, 7], False),   (11, 330_000, 400, [5], False),
    ]
    replayable = [eid for eid, *_, r in specs if r]
    star = 7  # the long one: plays the role of real event 33 in the autoplay

    def channel_wave(c: int, idx: np.ndarray) -> np.ndarray:
        t = idx * PERIOD
        period = 3600.0 * (2 + c)          # each channel its own slow cycle
        amp = 0.6 + 0.08 * c
        base = amp * np.sin(2 * np.pi * t / period + c * 0.7)
        drift = 0.05 * np.sin(2 * np.pi * t / (72 * 3600.0) + c)
        return base + drift + rng.normal(0, 0.03, len(idx))

    def inject(vals: np.ndarray, lo: int, hi: int, kind: int) -> None:
        n = hi - lo
        ramp = np.linspace(0, 1, n)
        burst = np.sin(2 * np.pi * np.arange(n) / 40.0)
        if kind % 2 == 0:
            vals[lo:hi] += 0.9 * ramp * (1 + 0.3 * burst)   # level shift + wobble
        else:
            vals[lo:hi] += 0.7 * burst * ramp               # growing oscillation

    def marked_indices(first: int, n: int) -> list[int]:
        """Contiguous run with two small internal gaps (< DEFAULT_GAP, so ONE event)."""
        idx = list(range(first, first + n))
        if n > 400:
            del idx[n // 3:n // 3 + 30]
            del idx[2 * n // 3:2 * n // 3 + 45]
        return idx

    index_entries, event_files = [], {}
    for eid, start, n_marked, inj, is_rep in specs:
        first_w, last_w = start, start + n_marked - 1
        marked = marked_indices(first_w, n_marked)
        ev_start, ev_end = iso(first_w), iso(last_w + WS - 1)
        duration = (last_w + WS - 1 - first_w) * PERIOD
        dominant = [CHANNELS[c] for c in inj]
        shares = rng.dirichlet(np.ones(len(inj)) * 4) * (70 + 10 * rng.random())
        top = sorted([[CHANNELS[c], float(s)] for c, s in zip(inj, shares)]
                     + [[CHANNELS[c], float(rng.uniform(0.5, 6))]
                        for c in range(len(CHANNELS)) if c not in inj],
                     key=lambda x: x[1], reverse=True)
        intensity = float(rng.uniform(0.02, 0.15))
        priority = intensity * np.log10(1.0 + duration)
        context = {
            "event_id": eid, "start": ev_start, "end": ev_end,
            "duration_sec": duration, "n_windows": len(marked),
            "m2_confidence": 0.99998, "intensity": intensity,
            "priority": float(priority), "top_channels": top,
            "dominant_channels": dominant,
            "localization": "confident" if top[0][1] >= 25 else "diffuse",
            "shared_relations": {"shared_unit": [], "shared_group": []},
            "window_span": [first_w, last_w],
        }
        start_record = {
            "event_id": eid, "window_idx": first_w, "t": ev_start,
            "score": float(rng.uniform(0.001, 0.01)), "p": 1e-6,
            "confidence": 1.0 - 1e-6,
            "intensity_pct_vs_calib": float(rng.uniform(0.97, 0.9999)),
            "intensity_label": "high",
            "channels": [[c, p] for c, p in top],
        }
        index_entries.append({"event_id": eid, "verdict": "PASS",
                              "replayable": is_rep, "context": context,
                              "start_record": start_record})

        if not is_rep:
            continue

        margin = max(DEFAULT_GAP, 1500)
        s_lo = first_w - margin
        s_hi = last_w + WS - 1 + margin  # inclusive sample bound
        n_samples = s_hi - s_lo + 1
        n_windows = n_samples - WS + 1
        idx = np.arange(s_lo, s_hi + 1)

        chans = {}
        for c, name in enumerate(CHANNELS):
            vals = channel_wave(c, idx)
            if c in inj:
                inject(vals, first_w - s_lo, last_w + WS - 1 - s_lo, kind=c)
            chans[name] = [round(float(v), 4) for v in vals]

        score = rng.normal(-0.08, 0.008, n_windows)
        p_vals: list[float | None] = list(np.round(rng.uniform(0.05, 1.0, n_windows), 4))
        marked_set = set(marked)
        for w in range(n_windows):
            g = w + s_lo
            if g in marked_set:
                local = (g - first_w) / max(n_marked, 1)
                score[w] = 0.02 + 0.1 * np.sin(np.pi * min(local, 1.0)) + rng.normal(0, 0.01)
                p_vals[w] = 1e-6

        matrix = []
        for _ in marked:
            row = np.full(len(CHANNELS), 0.0)
            row[inj] = rng.dirichlet(np.ones(len(inj)) * 6) * rng.uniform(78, 95)
            rest = 100.0 - row.sum()
            others = [c for c in range(len(CHANNELS)) if c not in inj]
            row[others] = rng.dirichlet(np.ones(len(others))) * rest
            matrix.append([round(float(x), 3) for x in row])

        neighbors = [{"id": f"id_{900 + k}", "sim": round(0.9 - 0.07 * k, 3),
                      "channels": dominant + [CHANNELS[(inj[0] + k + 1) % len(CHANNELS)]],
                      "class": "synthetic", "category": "Anomaly", "locality": "local"}
                     for k in range(4)]
        retrieval = {"neighbors": neighbors, "max_sim": neighbors[0]["sim"],
                     "novelty": round(1 - neighbors[0]["sim"], 3)}

        brief = (f"[SYNTHETIC DEMO DATA] The event is now closed -- the detector stopped "
                 f"flagging windows. Localization is {context['localization']} and the "
                 f"dominant channels are {', '.join(dominant)}. The anomaly persisted for "
                 f"{duration / 3600:.1f} h with a confidence of 99.998 %; confidence is "
                 f"saturated across all flagged events -- use the priority value.")
        alert_md = _render_alert_md(context, retrieval, brief)
        flag_text = render_flag(start_flag(start_record))

        event_files[eid] = {
            "event_id": eid,
            "samples": {"start_idx": int(s_lo), "timestamps": [iso(i) for i in idx],
                        "channels": chans},
            "windows": {"start_idx": int(s_lo),
                        "score": [round(float(x), 5) for x in score],
                        "p": p_vals},
            "marked_window_idx": [int(m) for m in marked],
            "attribution": {"window_idx": [int(m) for m in marked],
                            "channels": CHANNELS, "matrix": matrix},
            "retrieval": retrieval, "alert_md": alert_md, "brief": brief,
            "verdict": "PASS", "reasons": [], "flag_text": flag_text,
        }

    mission = {
        "synthetic": True,
        "channels": CHANNELS, "window_size": WS, "gap": DEFAULT_GAP,
        "alpha_star": 2e-5, "sample_period_sec": PERIOD,
        "time_range": {"start": iso(0), "end": iso(specs[-1][1] + specs[-1][2] + 5000)},
        "headline": {
            "false_alarms": {"value": 0, "normal_windows": 976_182,
                             "scope": "DATOS SINTÉTICOS de demo — en los datos reales: "
                                      "tercio final del test, en el umbral α*"},
            "briefs": {"passed": 120, "total": 120,
                       "scope": "DATOS SINTÉTICOS de demo — en los datos reales: 120 "
                                "eventos del tercio final, generador auditado"},
        },
        "about": {"f05": 0.949,
                  "f05_scope": "test completo de Misión2 ligera (no el rango del minimapa)",
                  "note": "Slice SINTÉTICO para desarrollo. Sustituir ejecutando "
                          "scripts/build_demo_slice.py en una máquina con el dataset."},
        "events_total": len(specs),
        "replayable_event_ids": replayable,
        "autoplay_event_id": star,
    }

    _write_slice(mission, index_entries, event_files, build_guardrail_cases())


def _render_alert_md(context: dict, retrieval: dict, brief: str) -> str:
    """Markdown alert in the exact structure of m4_report.generation.render (demo copy)."""
    facts = "\n".join(
        f"| {k} | `{json.dumps(context[k])}` |"
        for k in ("event_id", "start", "end", "duration_sec", "m2_confidence",
                  "priority", "intensity", "localization", "dominant_channels",
                  "top_channels"))
    neigh = "\n".join(
        f"| {n['id']} | {n['sim']:.3f} | {', '.join(n['channels'])} |"
        for n in retrieval["neighbors"])
    return (f"## Anomaly event {context['event_id']} -- closing brief\n\n"
            f"### Facts (verbatim from the detection pipeline)\n\n"
            f"| fact | value (verbatim from M3) |\n|---|---|\n{facts}\n\n"
            f"note: m2_confidence saturates (~1 for every flagged event; alpha* floor) "
            f"-- it does not rank events. Use priority.\n\n"
            f"### Similar past anomalies (retrieved, all ended before this event)\n\n"
            f"| past anomaly | similarity | shared channels |\n|---|---|---|\n{neigh}\n\n"
            f"combination novelty: {retrieval['novelty']:.3f} (1 = channel set unlike "
            f"anything in the archive)\n\n"
            f"### Brief (LLM-generated, audited)\n\n{brief}\n")


# ---------------------------------------------------------------------------
# Real mode — runs only where the dataset + artifacts live (author's machine).
# ---------------------------------------------------------------------------
def build_real(event_ids: list[int] | None) -> None:
    import config  # noqa: PLC0415
    from aggregate import (DEFAULT_GAP, build_marked_windows, group_events,  # noqa: PLC0415
                           marked_global_indices)
    from attribute import attribute_many  # noqa: PLC0415
    from m2_uncertainty.scores import load_test_channels  # noqa: PLC0415
    from m2_uncertainty.split import load_timestamps  # noqa: PLC0415
    from m4_report.alert import load_start_windows, render_flag, start_flag  # noqa: PLC0415
    from m4_report.generation.generator import load_contexts  # noqa: PLC0415
    from m4_report.generation.render import render_alert  # noqa: PLC0415
    from m4_report.retrieval.retrieve import load_corpus, retrieve  # noqa: PLC0415
    import pickle  # noqa: PLC0415

    WS = config.WINDOW_SIZE
    CHANNELS = config.TARGET_CHANNELS
    cache_dir = config.CACHE_DIR

    print("Loading artifacts (dataset machine only)...")
    data = load_test_channels()                     # (n_samples, 11) raw values
    ts = load_timestamps()                          # pd.Series of timestamps
    scores = np.load(cache_dir / "scores_continuous.npy")
    sp = np.load(cache_dir / "split.npz")
    ac = np.load(cache_dir / "alpha_choice.npz")
    alpha_star = float(ac[f"alpha_{str(ac['winner'])}"])
    p_test = np.load(cache_dir / "p_test.npy")

    # p is LOCAL to third 3 -> map to the global window axis (aggregate.py:49-53).
    w3_idx = np.where(sp["window_third"] == 2)[0]
    assert len(w3_idx) == len(p_test), "third-3 window count != p_test length"
    p_global = np.full(len(scores), np.nan)
    p_global[w3_idx] = p_test

    marked_global, _ = marked_global_indices()
    groups = group_events(marked_global, DEFAULT_GAP)
    events_marked = {eid: [int(x) for x in g] for eid, g in enumerate(groups)}

    contexts = {c["event_id"]: c for c in load_contexts()}
    start_records = load_start_windows()
    alerts = json.loads((cache_dir / "m4_alerts.json").read_text())
    corpus = load_corpus()

    with open(cache_dir / "model.pkl", "rb") as f:
        clf = pickle.load(f)
    baseline = np.load(cache_dir / "m3_baseline.npy")

    # --- pick the sliced events -------------------------------------------------
    if not event_ids:
        by_prio = sorted(contexts.values(), key=lambda c: c["priority"], reverse=True)
        picks = [33]
        picks += [c["event_id"] for c in by_prio if c["event_id"] != 33][:2]
        diffuse = [c["event_id"] for c in by_prio if c["localization"] == "diffuse"]
        if diffuse and diffuse[0] not in picks:
            picks.append(diffuse[0])
        event_ids = picks
    print(f"Sliced events: {event_ids}")

    def margin_bounds(eid: int) -> tuple[int, int]:
        """[lo, hi] sample bounds; margin >= gap per side, no foreign marked windows."""
        first_w, last_w = events_marked[eid][0], events_marked[eid][-1]
        lo = first_w - MARGIN_TARGET
        hi = last_w + WS - 1 + MARGIN_TARGET
        for other, m in events_marked.items():
            if other == eid:
                continue
            if m[-1] < first_w:  # neighbor before
                lo = max(lo, m[-1] + WS)          # stay clear of its windows
            if m[0] > last_w:    # neighbor after
                hi = min(hi, m[0] - 1)
        lo = min(lo, first_w - DEFAULT_GAP)       # guarantee: margin >= gap
        hi = max(hi, last_w + WS - 1 + DEFAULT_GAP)
        return max(lo, 0), min(hi, len(data) - 1)

    index_entries, event_files = [], {}
    for eid, ctx in sorted(contexts.items()):
        rec = start_records[eid]
        verdict = alerts[str(eid)]["verdict"]
        index_entries.append({"event_id": eid, "verdict": verdict,
                              "replayable": eid in event_ids,
                              "context": ctx, "start_record": rec})

    for eid in event_ids:
        ctx = contexts[eid]
        marked = events_marked[eid]
        lo, hi = margin_bounds(eid)
        n_windows = (hi - lo + 1) - WS + 1
        idx = np.arange(lo, hi + 1)

        win = build_marked_windows(data, np.array(marked), clf)
        contrib = attribute_many(win, clf, baseline)     # (n_marked, 11) raw contributions
        matrix = []
        for row in contrib:
            pos = row.clip(min=0)
            total = pos.sum()
            matrix.append([round(float(100 * v / total), 3) if total > 0 else 0.0
                           for v in pos])

        retrieval_full = retrieve(ctx, corpus)
        brief = alerts[str(eid)]["brief"]
        alert_md = render_alert(ctx, retrieval_full, brief) if brief else \
            alerts[str(eid)].get("alert_md", "")
        retrieval = {"neighbors": retrieval_full["neighbors"],
                     "max_sim": retrieval_full["max_sim"],
                     "novelty": retrieval_full["novelty"]}

        event_files[eid] = {
            "event_id": eid,
            "samples": {"start_idx": int(lo),
                        "timestamps": [ts.iloc[int(i)].isoformat() for i in idx],
                        "channels": {name: [round(float(v), 5) for v in data[lo:hi + 1, c]]
                                     for c, name in enumerate(CHANNELS)}},
            "windows": {"start_idx": int(lo),
                        "score": [round(float(s), 6) for s in scores[lo:lo + n_windows]],
                        "p": [None if np.isnan(p) else float(p)
                              for p in p_global[lo:lo + n_windows]]},
            "marked_window_idx": marked,
            "attribution": {"window_idx": marked, "channels": CHANNELS, "matrix": matrix},
            "retrieval": retrieval, "alert_md": alert_md, "brief": brief,
            "verdict": alerts[str(eid)]["verdict"],
            "reasons": alerts[str(eid)]["reasons"],
            "flag_text": render_flag(start_flag(start_records[eid])),
        }

    # --- golden test: event 33's re-rendered alert must match the committed example ---
    if 33 in event_files:
        example = (REPO / "docs" / "m4_alert_example.md").read_text()
        moment2 = example.split("## Moment 2 -- closing alert (audited)\n\n", 1)[1].strip()
        rebuilt = event_files[33]["alert_md"].strip()
        assert rebuilt == moment2, (
            "GOLDEN TEST FAILED: re-rendered alert of event 33 differs from "
            "docs/m4_alert_example.md -- the recomputation does not reproduce the pipeline")
        print("Golden test (event 33 alert byte-identical): OK")

    # third-3 minimap range
    t3_lo, t3_hi = int(w3_idx.min()), int(w3_idx.max())
    mission = {
        "synthetic": False,
        "channels": CHANNELS, "window_size": WS, "gap": DEFAULT_GAP,
        "alpha_star": alpha_star, "sample_period_sec": 18.0,
        "time_range": {"start": ts.iloc[t3_lo].isoformat(),
                       "end": ts.iloc[t3_hi + WS - 1].isoformat()},
        "headline": {
            "false_alarms": {"value": 0, "normal_windows": 976_182,
                             "scope": "ventanas certificadas normales del tercio final "
                                      "del test, en el umbral derivado α*"},
            "briefs": {"passed": 120, "total": 120,
                       "scope": "los 120 eventos del tercio final; brief aprobado por "
                                "precheck Y juez"},
        },
        "about": {"f05": 0.949,
                  "f05_scope": "test completo de Misión2 ligera (no el rango del minimapa)",
                  "note": "Datos reales ESA-ADB Misión2 (extracto). Ver NOTICE."},
        "events_total": len(contexts),
        "replayable_event_ids": sorted(event_files),
        "autoplay_event_id": 33,
    }

    _write_slice(mission, index_entries, event_files, build_guardrail_cases())


# ---------------------------------------------------------------------------
def _write_slice(mission: dict, index: list[dict], events: dict[int, dict],
                 guardrail: dict) -> None:
    events_dir = SLICE_DIR / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    (SLICE_DIR / "mission.json").write_text(json.dumps(mission, indent=1))
    (SLICE_DIR / "events_index.json").write_text(json.dumps(index, indent=1))
    (SLICE_DIR / "guardrail_block.json").write_text(json.dumps(guardrail, indent=1))
    for eid, ev in events.items():
        (events_dir / f"{eid}.json").write_text(json.dumps(ev))

    m, idx, evs, g = validate_slice_dir(SLICE_DIR)  # hard gate: schema + invariants
    total = sum(f.stat().st_size for f in SLICE_DIR.rglob("*.json"))
    print(f"Slice OK -> {SLICE_DIR}  ({'SYNTHETIC' if m.synthetic else 'REAL'}, "
          f"{len(idx)} events, {len(evs)} replayable, {len(g.cases)} guardrail cases, "
          f"{total / 1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--synthetic", action="store_true",
                    help="generate the schema-identical synthetic slice (no dataset needed)")
    ap.add_argument("--events", type=int, nargs="*", default=None,
                    help="real mode: explicit event ids to slice (default: auto-pick)")
    args = ap.parse_args()
    if args.synthetic:
        build_synthetic()
    else:
        build_real(args.events)


if __name__ == "__main__":
    main()
