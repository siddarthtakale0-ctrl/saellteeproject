// Attribution heatmap: channel x marked-window blame (%), revealed with the cursor.
// One canvas, columns = the event's marked windows, rows = the 11 channels.
import { useEffect, useMemo, useRef } from "react";

import { Telemetry } from "../api";

export default function AttributionStrip({
  telemetry,
  cursor,
}: {
  telemetry: Telemetry;
  cursor: number;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const { attribution } = telemetry;
  const nWin = attribution.window_idx.length;
  const nCh = attribution.channels.length;

  const revealedCols = useMemo(() => {
    let n = 0;
    while (n < nWin && attribution.window_idx[n] <= cursor) n++;
    return n;
  }, [attribution, cursor, nWin]);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || nWin === 0) return;
    const W = canvas.clientWidth;
    const H = canvas.clientHeight;
    canvas.width = W * devicePixelRatio;
    canvas.height = H * devicePixelRatio;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(devicePixelRatio, devicePixelRatio);
    ctx.clearRect(0, 0, W, H);

    const cw = W / nWin;
    const chH = H / nCh;
    for (let c = 0; c < revealedCols; c++) {
      for (let r = 0; r < nCh; r++) {
        const v = attribution.matrix[c][r] / 100; // pct share -> 0..1
        if (v <= 0.005) continue;
        ctx.fillStyle = `rgba(255, 77, 94, ${Math.min(1, 0.08 + v * 1.6)})`;
        ctx.fillRect(c * cw, r * chH, Math.max(cw, 0.5), chH - 0.5);
      }
    }
  }, [attribution, revealedCols, nWin, nCh]);

  if (nWin === 0) return null;
  return (
    <div className="flex items-stretch gap-2">
      <div className="w-24 shrink-0 flex items-center justify-end pr-1 font-mono text-[10px] text-dim">
        atribución M3
      </div>
      <div className="grow relative h-[52px]">
        <canvas ref={ref} className="w-full h-full rounded-sm bg-panel" />
        {revealedCols === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-[10px] text-dim">
            (se pinta cuando el detector marca ventanas)
          </div>
        )}
      </div>
    </div>
  );
}
