// Header: title, mission clock, the two headline figures (same scope, labeled),
// and the synthetic-data badge when the slice is not built from real telemetry.
// Ground-station styling: monospace clock readout, amber accent, hairline rules.
import { Mission } from "../api";

export default function MissionHeader({
  mission,
  missionTime,
  speed,
}: {
  mission: Mission;
  missionTime: string | null;
  speed: number;
}) {
  return (
    <header className="flex flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2.5 border-b border-line bg-panel">
      <div>
        <h1 className="text-base font-bold tracking-wide font-mono">
          MISSION CONTROL <span className="text-accent">· Trustworthy Anomaly Agent</span>
        </h1>
        <p className="text-[11px] text-dim">Real satellite telemetry (ESA-ADB), watched live</p>
      </div>

      <div
        className="tnum text-[13px] px-3 py-1 border border-line bg-panel-2"
        title="satellite clock (accelerated)"
      >
        <span className="hud-label mr-2">CLK</span>
        {missionTime ? missionTime.replace("T", " ") : "--:--:--"}
        <span className="text-accent ml-2">×{Math.round(speed / 18)}</span>
      </div>

      <div className="flex gap-5 ml-auto items-center">
        <Figure
          value={`${mission.headline.false_alarms.value}`}
          label={`false alarms in ${groupDigits(mission.headline.false_alarms.normal_windows)} normal windows`}
          scope={mission.headline.false_alarms.scope}
        />
        <Figure
          value={`${mission.headline.briefs.passed}/${mission.headline.briefs.total}`}
          label="correct reports"
          scope={mission.headline.briefs.scope}
        />
        {mission.synthetic && (
          <span
            className="text-[10px] font-bold font-mono px-2 py-1 bg-amber-500/15 text-amber-400 border border-amber-500/40"
            title={mission.about.note}
          >
            SYNTHETIC DATA
          </span>
        )}
      </div>
    </header>
  );
}

// Intl-free digit grouping: some headless environments ship a broken default
// locale that makes toLocaleString throw.
function groupDigits(n: number): string {
  return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function Figure({ value, label, scope }: { value: string; label: string; scope: string }) {
  return (
    <div className="text-right" title={scope}>
      <div className="text-lg font-bold text-ok leading-none tnum">{value}</div>
      <div className="text-[10px] text-dim max-w-52 leading-tight">{label}</div>
    </div>
  );
}
