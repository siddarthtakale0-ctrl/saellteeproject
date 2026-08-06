// Which channels are to blame, and how much. One horizontal bar per channel = its
// average share of the blame over the marked windows seen so far. Far clearer than a
// thousand-column heatmap: you read "CH18 → 31%" at a glance.
import { useMemo } from "react";

import { Telemetry } from "../api";

export default function AttributionStrip({
  telemetry,
  cursor,
}: {
  telemetry: Telemetry;
  cursor: number;
}) {
  const { attribution } = telemetry;
  const nWin = attribution.window_idx.length;

  const revealedCols = useMemo(() => {
    let n = 0;
    while (n < nWin && attribution.window_idx[n] <= cursor) n++;
    return n;
  }, [attribution, cursor, nWin]);

  const bars = useMemo(() => {
    const nCh = attribution.channels.length;
    const sum = new Array(nCh).fill(0);
    for (let c = 0; c < revealedCols; c++)
      for (let r = 0; r < nCh; r++) sum[r] += attribution.matrix[c][r];
    return attribution.channels
      .map((ch, r) => ({ ch, pct: revealedCols ? sum[r] / revealedCols : 0 }))
      .filter((b) => b.pct >= 1)
      .sort((a, b) => b.pct - a.pct);
  }, [attribution, revealedCols]);

  if (nWin === 0) return null;
  return (
    <div className="flex items-start gap-2 border-t border-line pt-2 mt-1">
      <div className="w-24 shrink-0 pr-1 hud-label text-right leading-tight pt-0.5">
        Blame
        <br />
        <span className="normal-case tracking-normal" style={{ fontSize: 9 }}>
          whole event · %
        </span>
      </div>
      <div className="grow">
        {revealedCols === 0 ? (
          <div className="text-[10px] text-dim py-2 font-mono">(appears when the anomaly fires)</div>
        ) : (
          <div className="flex flex-col gap-1">
            {bars.map((b) => (
              <div key={b.ch} className="flex items-center gap-2">
                <span className="w-16 shrink-0 text-[11px] text-right text-ink font-mono">
                  {b.ch.replace("channel_", "CH ")}
                </span>
                <div className="grow h-4 bg-panel-2 overflow-hidden">
                  <div
                    className="h-full bg-alarm/70"
                    style={{ width: `${Math.min(100, b.pct)}%` }}
                  />
                </div>
                <span className="w-9 shrink-0 text-[11px] text-dim tabular-nums text-right font-mono">
                  {b.pct.toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
