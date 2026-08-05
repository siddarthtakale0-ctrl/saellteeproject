// Play/pause/restart + compressed-clock speed. Pausing closes the SSE stream;
// resuming reopens it with from_idx (the server re-runs the agenda and
// suppresses emission up to the cursor — the state machine never starts mid-event).
import { useStore } from "../store";

const SPEEDS = [900, 3600, 10800, 36000]; // mission-seconds per real second

export default function PlaybackControls() {
  const { playing, speed, done, play, pause, restart, setSpeed } = useStore();

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => (playing ? pause() : play())}
        className="w-9 h-9 rounded border border-line bg-panel-2 hover:border-accent hover:text-accent transition-colors text-sm"
        title={playing ? "Pausa" : done ? "Repetir" : "Reproducir"}
      >
        {playing ? "⏸" : "▶"}
      </button>
      <button
        onClick={restart}
        className="w-9 h-9 rounded border border-line bg-panel-2 hover:border-accent hover:text-accent transition-colors text-sm"
        title="Desde el principio"
      >
        ⟲
      </button>
      <div className="flex rounded border border-line overflow-hidden">
        {SPEEDS.map((s) => (
          <button
            key={s}
            onClick={() => setSpeed(s)}
            className={`px-2 py-1.5 text-[11px] font-mono transition-colors ${
              speed === s ? "bg-accent/20 text-accent" : "bg-panel-2 text-dim hover:text-ink"
            }`}
          >
            ×{Math.round(s / 18)}
          </button>
        ))}
      </div>
    </div>
  );
}
