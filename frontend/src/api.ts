// API client. The frontend speaks ONLY REST + SSE; it never reads repo files.
// Types mirror backend/slice_schema.py (the single contract).

export interface Mission {
  synthetic: boolean;
  channels: string[];
  window_size: number;
  gap: number;
  alpha_star: number;
  sample_period_sec: number;
  time_range: { start: string; end: string };
  headline: {
    false_alarms: { value: number; normal_windows: number; scope: string };
    briefs: { passed: number; total: number; scope: string };
  };
  about: { f05: number; f05_scope: string; note: string };
  events_total: number;
  replayable_event_ids: number[];
  autoplay_event_id: number;
}

export interface EventContext {
  event_id: number;
  start: string;
  end: string;
  duration_sec: number;
  n_windows: number;
  m2_confidence: number;
  intensity: number;
  priority: number;
  top_channels: [string, number][];
  dominant_channels: string[];
  localization: string;
  shared_relations: Record<string, unknown>;
  window_span: [number, number];
}

export interface IndexEntry {
  event_id: number;
  verdict: string;
  replayable: boolean;
  context: EventContext;
  start_record: { window_idx: number; t: string; intensity_label: string };
}

export interface Neighbor {
  id: string;
  sim: number;
  channels: string[];
  class: string;
  category: string;
  locality: string;
}

export interface EventDetail extends IndexEntry {
  flag_text?: string;
  alert_md?: string;
  brief?: string | null;
  reasons?: string[];
  retrieval?: { neighbors: Neighbor[]; max_sim: number; novelty: number };
}

export interface Telemetry {
  event_id: number;
  samples: { start_idx: number; timestamps: string[]; channels: Record<string, number[]> };
  windows: { start_idx: number; score: number[]; p: (number | null)[] };
  marked_window_idx: number[];
  attribution: { window_idx: number[]; channels: string[]; matrix: number[][] };
}

export interface GuardrailCase {
  id: string;
  title: string;
  tests: string;
  brief: string;
  verdict: string;
  reasons: string[];
  source: string;
}

export interface Guardrail {
  synthetic_cases: boolean;
  evidence_ref: string;
  cases: GuardrailCase[];
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return r.json() as Promise<T>;
}

export const fetchMission = () => get<Mission>("/api/mission");
export const fetchEvents = () => get<IndexEntry[]>("/api/events");
export const fetchEvent = (id: number) => get<EventDetail>(`/api/events/${id}`);
export const fetchTelemetry = (id: number) => get<Telemetry>(`/api/events/${id}/telemetry`);
export const fetchGuardrail = () => get<Guardrail>("/api/guardrail");

// --- SSE replay -----------------------------------------------------------
export interface ReplayHandlers {
  onState?: (d: { cursor: number; open: boolean; flag_text: string | null; from: number; to: number }) => void;
  onTick?: (d: { cursor: number; mission_time: string }) => void;
  onStart?: (d: { flag_text: string; window_idx: number }) => void;
  onClose?: (d: { verdict: string; reasons: string[]; brief: string | null; alert_md: string; window_idx: number }) => void;
  onDone?: () => void;
  onError?: (msg: string) => void;
}

export function openReplay(
  eventId: number,
  speed: number,
  fromIdx: number | null,
  h: ReplayHandlers,
): () => void {
  const qs = new URLSearchParams({ speed: String(speed) });
  if (fromIdx !== null) qs.set("from_idx", String(fromIdx));
  const es = new EventSource(`/api/replay/${eventId}?${qs}`);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const on = (name: string, fn?: (d: any) => void) =>
    es.addEventListener(name, (e) => fn?.(JSON.parse((e as MessageEvent).data)));
  on("state", h.onState);
  on("tick", h.onTick);
  on("anomaly_start", h.onStart);
  on("anomaly_close", h.onClose);
  es.addEventListener("done", () => {
    es.close(); // explicit terminal event: without this EventSource would reconnect
    h.onDone?.();
  });
  es.addEventListener("error", (e) => {
    const msg = (e as MessageEvent).data;
    if (typeof msg === "string") h.onError?.(JSON.parse(msg).message);
  });
  es.onerror = () => {
    /* transport hiccup: EventSource auto-reconnects; the server re-sends `state` */
  };
  return () => es.close();
}
