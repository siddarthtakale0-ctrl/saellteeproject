// Clear event picker: one labelled button per replayable event. No cryptic dots.
// Selecting loads the event paused at the start; the user then hits Run.
// Ground-station styling: sharp corners, monospace, amber active state.
import { IndexEntry } from "../api";

export default function EventSelector({
  events,
  currentId,
  onSelect,
}: {
  events: IndexEntry[];
  currentId: number | null;
  onSelect: (id: number) => void;
}) {
  const replayable = events.filter((e) => e.replayable);
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="hud-label">Event</span>
      {replayable.map((e) => {
        const hours = Math.round(e.context.duration_sec / 3600);
        const active = e.event_id === currentId;
        return (
          <button
            key={e.event_id}
            onClick={() => onSelect(e.event_id)}
            className={`px-3 py-1.5 border text-sm font-mono transition-colors ${
              active
                ? "border-accent bg-accent/15 text-accent font-semibold"
                : "border-line text-ink hover:border-accent/60 hover:text-accent"
            }`}
          >
            {e.event_id}
            <span className="text-dim font-normal"> · {hours}h</span>
          </button>
        );
      })}
    </div>
  );
}
