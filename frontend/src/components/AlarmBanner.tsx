// The instant alarm: the moment the system opens an anomaly. Plain language up
// front; the raw one-line alert (the ~100 bytes that would actually downlink) is
// kept small. Ground-station styling: sharp corners, pulsing red.
const INTENSITY: Record<string, string> = { high: "high", moderate: "moderate", low: "low" };

export default function AlarmBanner({ flagText }: { flagText: string }) {
  const channels = (flagText.match(/ch ([\d,]+)/)?.[1] ?? "")
    .split(",")
    .filter(Boolean)
    .join(", ");
  const intensityRaw = flagText.match(/intensity (\w+)/)?.[1] ?? "";
  const intensity = INTENSITY[intensityRaw] ?? intensityRaw;

  return (
    <div className="alarm-banner pulse-red mx-4 mt-3 border border-alarm/60 bg-alarm/10 px-4 py-2.5">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-alarm font-bold text-sm tracking-widest shrink-0 font-mono">
          ⬤ ALARM
        </span>
        <span className="text-ink text-[13px] grow">
          Anomaly detected · first channels to trip: <b>{channels || "n/a"}</b>
          {intensity && <> · {intensity} intensity</>}
        </span>
        <span className="hud-label shrink-0 text-right leading-tight">
          instant alert
          <br />
          no waiting · no AI
        </span>
      </div>
      <div className="mt-1 text-[10px] text-dim leading-snug">
        These are the channels that tripped <b className="text-ink">first</b> (live, no
        look-ahead). The channels to blame <b className="text-ink">over the whole event</b>{" "}
        appear in the closing report, and they can differ.
      </div>
    </div>
  );
}
