// Mission-control layout. Pick an event, hit Run, watch the 11 sensors replay
// under a fast clock; the alarm fires when the system opens the anomaly, the
// culprit channels light up, and the written report appears when it closes.
// Plain language, one job per area, no internal jargon. Ground-station styling:
// amber phosphor, monospace labels, hairline instrument cards.
import { useEffect } from "react";

import AlarmBanner from "./components/AlarmBanner";
import AttributionStrip from "./components/AttributionStrip";
import ChannelGrid from "./components/ChannelGrid";
import EventReport from "./components/EventReport";
import EventSelector from "./components/EventSelector";
import MissionHeader from "./components/MissionHeader";
import PlaybackControls from "./components/PlaybackControls";
import Reveal from "./components/Reveal";
import { useStore } from "./store";

const PHASE: Record<string, { text: string; cls: string; dot: string }> = {
  watching: { text: "WATCHING", cls: "text-dim", dot: "bg-dim" },
  alarm: { text: "ANOMALY IN COURSE", cls: "text-alarm font-bold", dot: "bg-alarm animate-pulse" },
  closed: { text: "EVENT CLOSED", cls: "text-ok font-semibold", dot: "bg-ok" },
  idle: { text: "READY", cls: "text-dim", dot: "bg-dim" },
};

export default function App() {
  const s = useStore();

  useEffect(() => {
    void useStore.getState().boot();
  }, []);

  if (s.error) {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <div className="hudcard max-w-md p-4 text-sm border-alarm/50">
          <b className="text-alarm">Error:</b> {s.error}
          <p className="text-dim text-xs mt-2">
            Is the server running? <code className="text-accent">make demo</code>
          </p>
        </div>
      </div>
    );
  }
  if (!s.mission) {
    return (
      <div className="h-full flex items-center justify-center text-dim text-sm animate-pulse font-mono">
        Booting…
      </div>
    );
  }

  const dominant = s.detail?.context.dominant_channels ?? [];
  const ph = PHASE[s.phase] ?? PHASE.idle;

  return (
    <div className="h-full flex flex-col">
      <MissionHeader mission={s.mission} missionTime={s.missionTime} speed={s.speed} />

      <Reveal show={s.phase === "alarm" && !!s.flagText}>
        <AlarmBanner flagText={s.flagText ?? ""} />
      </Reveal>

      {/* control bar: pick an event · current state · playback */}
      <div className="flex items-center gap-4 flex-wrap px-4 py-2.5 border-b border-line bg-panel">
        <EventSelector
          events={s.eventsIndex}
          currentId={s.currentEventId}
          onSelect={(id) => void s.selectEvent(id, false)}
        />
        <div className="ml-auto flex items-center gap-4">
          <div className="flex items-center gap-2 text-[13px] font-mono">
            <span className={`inline-block w-2.5 h-2.5 ${ph.dot}`} />
            <span className={ph.cls}>{ph.text}</span>
          </div>
          <PlaybackControls />
        </div>
      </div>

      <main className="grow flex gap-4 p-4 min-h-0">
        {/* left: the sensors + what we derive from them */}
        <section className="grow min-w-0 flex flex-col gap-2">
          <h2 className="font-mono text-[11px] uppercase tracking-[0.12em] font-semibold text-ink">
            Telemetry · the satellite's 11 sensors
            <span className="text-dim font-normal normal-case tracking-normal">
              {" "}
              (one line per sensor, drawn as the clock advances)
            </span>
          </h2>
          <div className="hudcard grow overflow-y-auto p-3">
            {s.telemetry ? (
              <>
                <ChannelGrid
                  telemetry={s.telemetry}
                  cursor={s.cursor}
                  phase={s.phase}
                  dominant={dominant}
                  alphaStar={s.mission.alpha_star}
                />
                <div className="mt-2">
                  <AttributionStrip telemetry={s.telemetry} cursor={s.cursor} />
                </div>
              </>
            ) : (
              <div className="h-full flex items-center justify-center text-dim text-sm animate-pulse font-mono">
                Loading telemetry…
              </div>
            )}
          </div>
        </section>

        {/* right: the report (only after the event closes) */}
        <aside className="w-[440px] shrink-0 flex flex-col gap-3 min-h-0 overflow-y-auto">
          {s.phase === "closed" && s.report ? (
            <div className="reveal-in">
              <EventReport report={s.report} detail={s.detail} />
            </div>
          ) : (
            <div className="reveal-in hudcard p-4 text-[13px] text-dim leading-relaxed">
              <b className="text-ink">What you're watching.</b> The satellite's 11 sensors
              replay under a fast clock. When the system detects an anomaly, the{" "}
              <span className="text-alarm font-semibold">alarm</span> fires and names the
              channels that <b className="text-ink">trip first</b>. As the event unfolds the
              culprit channels light up with their share of the blame. When it ends, the{" "}
              <b className="text-ink">written report</b> names the channels to blame{" "}
              <b className="text-ink">over the whole event</b>, which can differ from the
              first few.
              <div className="mt-3 text-dim">
                Pick an event above and hit <b className="text-accent font-mono">▶ RUN</b>.
              </div>
            </div>
          )}

          <div className="hudcard p-3 text-[11px] text-dim leading-relaxed">
            <b className="text-ink">In one line.</b> The detector matches ESA's published
            baseline (F0.5 = {s.mission.about.f05}). What we add on top: a calibrated
            confidence, knowing which channel is to blame, and a written report whose
            figures the model never invents. Real ESA-ADB data (excerpt).
          </div>
        </aside>
      </main>
    </div>
  );
}
