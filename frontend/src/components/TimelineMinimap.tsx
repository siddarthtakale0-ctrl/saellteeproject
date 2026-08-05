// The mission's evaluated range with every event as a mark. Color encodes
// priority, shape encodes localization; replayable events are clickable.
import { useMemo } from "react";

import { IndexEntry, Mission } from "../api";

export default function TimelineMinimap({
  mission,
  events,
  currentId,
  onSelect,
}: {
  mission: Mission;
  events: IndexEntry[];
  currentId: number | null;
  onSelect: (id: number) => void;
}) {
  const t0 = useMemo(() => new Date(mission.time_range.start).getTime(), [mission]);
  const t1 = useMemo(() => new Date(mission.time_range.end).getTime(), [mission]);
  const maxPrio = useMemo(
    () => Math.max(...events.map((e) => e.context.priority), 1e-9),
    [events],
  );

  return (
    <div className="rounded border border-line bg-panel px-3 py-2">
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="text-[11px] font-bold tracking-wide">LÍNEA DE MISIÓN</span>
        <span className="text-[10px] text-dim">
          {mission.events_total} eventos · tramo evaluado · click = replay
        </span>
      </div>
      <div className="relative h-9 rounded bg-panel-2 border border-line/60">
        {events.map((e) => {
          const x = ((new Date(e.context.start).getTime() - t0) / (t1 - t0)) * 100;
          const heat = e.context.priority / maxPrio;
          const isCur = e.event_id === currentId;
          const diffuse = e.context.localization === "diffuse";
          return (
            <button
              key={e.event_id}
              onClick={() => e.replayable && onSelect(e.event_id)}
              disabled={!e.replayable}
              title={`#${e.event_id} · ${e.context.start.replace("T", " ")} · prio ${e.context.priority.toFixed(2)} · ${e.context.localization}${e.replayable ? "" : " · (sin datos de replay en el slice)"}`}
              className={`absolute top-1/2 -translate-y-1/2 -translate-x-1/2 transition-transform ${
                e.replayable ? "cursor-pointer hover:scale-150" : "cursor-default"
              } ${isCur ? "scale-150" : ""}`}
              style={{ left: `${Math.max(1, Math.min(99, x))}%` }}
            >
              <span
                className={`block ${diffuse ? "rounded-none rotate-45" : "rounded-full"} ${
                  isCur ? "ring-2 ring-accent" : ""
                }`}
                style={{
                  width: e.replayable ? 10 : 6,
                  height: e.replayable ? 10 : 6,
                  background: `rgba(255, ${Math.round(160 - heat * 120)}, 80, ${0.45 + heat * 0.55})`,
                }}
              />
            </button>
          );
        })}
      </div>
      <div className="flex justify-between text-[9px] font-mono text-dim mt-1">
        <span>{mission.time_range.start.slice(0, 10)}</span>
        <span>● grande = reproducible · ◆ = localización difusa · color = prioridad</span>
        <span>{mission.time_range.end.slice(0, 10)}</span>
      </div>
    </div>
  );
}
