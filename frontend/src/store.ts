// Zustand store. The single client-side state: the REPLAY DATA comes once via
// REST; the SSE stream carries only time (ticks) and the moments decided by the
// backend's real replay() state machine. The charts reveal up to the cursor.
import { create } from "zustand";

import {
  EventDetail,
  IndexEntry,
  Mission,
  Telemetry,
  fetchEvent,
  fetchEvents,
  fetchMission,
  fetchTelemetry,
  openReplay,
} from "./api";

export type Phase = "idle" | "watching" | "alarm" | "closed";

interface ClosePayload {
  verdict: string;
  reasons: string[];
  brief: string | null;
  alert_md: string;
}

interface State {
  mission: Mission | null;
  eventsIndex: IndexEntry[];
  error: string | null;

  currentEventId: number | null;
  detail: EventDetail | null;
  telemetry: Telemetry | null;

  cursor: number; // global window index of the mission clock
  missionTime: string | null;
  playing: boolean;
  speed: number;
  phase: Phase;
  flagText: string | null;
  report: ClosePayload | null;
  done: boolean;

  boot: () => Promise<void>;
  selectEvent: (id: number, autoplay?: boolean) => Promise<void>;
  play: () => void;
  pause: () => void;
  restart: () => void;
  setSpeed: (s: number) => void;
}

let closeStream: (() => void) | null = null;

export const useStore = create<State>((set, get) => {
  const stopStream = () => {
    closeStream?.();
    closeStream = null;
  };

  const startStream = (fromIdx: number | null) => {
    const { currentEventId, speed } = get();
    if (currentEventId === null) return;
    stopStream();
    closeStream = openReplay(currentEventId, speed, fromIdx, {
      onState: (d) =>
        set({
          cursor: d.cursor,
          phase: d.open ? "alarm" : get().phase === "closed" ? "closed" : "watching",
          flagText: d.open ? d.flag_text : get().flagText,
        }),
      onTick: (d) => set({ cursor: d.cursor, missionTime: d.mission_time }),
      onStart: (d) => set({ phase: "alarm", flagText: d.flag_text }),
      onClose: (d) =>
        set({ phase: "closed", report: d, flagText: get().flagText }),
      onDone: () => set({ playing: false, done: true }),
      onError: (msg) => set({ error: msg, playing: false }),
    });
    set({ playing: true, done: false });
  };

  return {
    mission: null,
    eventsIndex: [],
    error: null,
    currentEventId: null,
    detail: null,
    telemetry: null,
    cursor: 0,
    missionTime: null,
    playing: false,
    speed: 3600,
    phase: "idle",
    flagText: null,
    report: null,
    done: false,

    boot: async () => {
      try {
        const [mission, eventsIndex] = await Promise.all([
          fetchMission(),
          fetchEvents(),
        ]);
        set({ mission, eventsIndex });
        await get().selectEvent(mission.autoplay_event_id, true);
      } catch (e) {
        set({ error: String(e) });
      }
    },

    selectEvent: async (id, autoplay = true) => {
      stopStream();
      set({
        currentEventId: id,
        detail: null,
        telemetry: null,
        phase: "watching",
        flagText: null,
        report: null,
        playing: false,
        done: false,
        missionTime: null,
      });
      try {
        const [detail, telemetry] = await Promise.all([fetchEvent(id), fetchTelemetry(id)]);
        set({ detail, telemetry, cursor: telemetry.windows.start_idx });
        if (autoplay) startStream(null);
      } catch (e) {
        set({ error: String(e) });
      }
    },

    play: () => {
      const { telemetry, cursor, done } = get();
      if (!telemetry) return;
      startStream(done ? null : cursor);
      if (done) set({ phase: "watching", flagText: null, report: null });
    },
    pause: () => {
      stopStream();
      set({ playing: false });
    },
    restart: () => {
      set({ phase: "watching", flagText: null, report: null, done: false });
      const t = get().telemetry;
      if (t) set({ cursor: t.windows.start_idx });
      startStream(null);
    },
    setSpeed: (s) => {
      set({ speed: s });
      if (get().playing) startStream(get().cursor);
    },
  };
});
