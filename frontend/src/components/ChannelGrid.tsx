// The 11 telemetry channels + the detector score band, revealed up to the mission
// clock. Full series arrive once via REST; the SSE cursor only decides how much is
// visible. Attributed channels light up when the event opens (M3's dominant set).
import { useEffect, useMemo, useRef } from "react";
import uPlot from "uplot";

import { Telemetry } from "../api";
import { Phase } from "../store";

const H_CH = 22;
const H_SCORE = 54;

function toEpoch(ts: string[]): number[] {
  return ts.map((t) => new Date(t).getTime() / 1000);
}

interface Props {
  telemetry: Telemetry;
  cursor: number; // global window index
  phase: Phase;
  dominant: string[];
  alphaStar: number;
}

export default function ChannelGrid({ telemetry, cursor, phase, dominant }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const plotsRef = useRef<uPlot[]>([]);
  const lastN = useRef(-1);

  const epochs = useMemo(() => toEpoch(telemetry.samples.timestamps), [telemetry]);
  const chNames = useMemo(() => Object.keys(telemetry.samples.channels), [telemetry]);
  const markedSet = useMemo(() => new Set(telemetry.marked_window_idx), [telemetry]);

  const revealed = Math.max(
    2,
    Math.min(cursor - telemetry.samples.start_idx + 1, epochs.length),
  );

  // build plots once per telemetry payload
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    plotsRef.current.forEach((p) => p.destroy());
    plotsRef.current = [];
    wrap.innerHTML = "";
    lastN.current = -1;

    const width = wrap.clientWidth || 800;
    const sync = uPlot.sync("mission");

    const mkAxes = (isLast: boolean): uPlot.Axis[] => [
      {
        stroke: "#7b8ba1",
        grid: { stroke: "#1a2333", width: 1 },
        ticks: { stroke: "#223047" },
        font: "10px ui-monospace",
        show: isLast,
      },
      { show: false },
    ];

    chNames.forEach((name, i) => {
      const row = document.createElement("div");
      row.className = "flex items-stretch gap-2";
      const label = document.createElement("div");
      label.className =
        "w-24 shrink-0 flex items-center justify-end pr-1 text-[11px] font-mono transition-colors";
      label.textContent = name.replace("channel_", "CH ");
      label.dataset.channel = name;
      const cell = document.createElement("div");
      cell.className = "grow";
      row.append(label, cell);
      wrap.append(row);

      const plot = new uPlot(
        {
          width: width - 104,
          height: H_CH,
          cursor: { sync: { key: sync.key }, y: false },
          legend: { show: false },
          scales: { x: { time: true } },
          axes: mkAxes(false),
          series: [
            {},
            {
              stroke: "#ffb454",
              width: 1,
              points: { show: false },
            },
          ],
        },
        [[epochs[0]], [null]] as uPlot.AlignedData,
        cell,
      );
      plotsRef.current.push(plot);
      void i;
    });

    // score band with marked-window shading
    const row = document.createElement("div");
    row.className = "flex items-stretch gap-2 mt-1 border-t border-line pt-1";
    const label = document.createElement("div");
    label.className =
      "w-24 shrink-0 flex flex-col items-end justify-center pr-1 text-[11px] font-mono text-dim text-right leading-tight uppercase tracking-wider";
    label.innerHTML =
      "Rarity<br/><span style='font-size:9px;text-transform:none;letter-spacing:0'>red = anomaly</span>";
    const cell = document.createElement("div");
    cell.className = "grow";
    row.append(label, cell);
    wrap.append(row);

    const scorePlot = new uPlot(
      {
        width: width - 104,
        height: H_SCORE,
        cursor: { sync: { key: sync.key }, y: false },
        legend: { show: false },
        scales: { x: { time: true } },
        axes: mkAxes(true),
        series: [
          {},
          { stroke: "#9aa8bb", width: 1, points: { show: false } },
          { stroke: "#ff5343", width: 1.6, points: { show: false } },
        ],
      },
      [[epochs[0]], [null], [null]] as uPlot.AlignedData,
      cell,
    );
    plotsRef.current.push(scorePlot);

    return () => {
      plotsRef.current.forEach((p) => p.destroy());
      plotsRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [telemetry]);

  // reveal on cursor move
  useEffect(() => {
    if (revealed === lastN.current || plotsRef.current.length === 0) return;
    lastN.current = revealed;
    const x = epochs.slice(0, revealed);

    chNames.forEach((name, i) => {
      const y = telemetry.samples.channels[name].slice(0, revealed);
      plotsRef.current[i]?.setData([x, y] as uPlot.AlignedData);
    });

    const nW = Math.min(revealed, telemetry.windows.score.length);
    const base = telemetry.windows.start_idx;
    const normal: (number | null)[] = new Array(nW);
    const flagged: (number | null)[] = new Array(nW);
    for (let w = 0; w < nW; w++) {
      const s = telemetry.windows.score[w];
      const isMarked = markedSet.has(base + w);
      normal[w] = isMarked ? null : s;
      flagged[w] = isMarked ? s : null;
    }
    plotsRef.current[chNames.length]?.setData([
      x.slice(0, nW),
      normal,
      flagged,
    ] as uPlot.AlignedData);
  }, [revealed, epochs, chNames, telemetry, markedSet]);

  // highlight attributed channels during/after the alarm
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const active = phase === "alarm" || phase === "closed";
    wrap.querySelectorAll<HTMLElement>("[data-channel]").forEach((el) => {
      const isDom = dominant.includes(el.dataset.channel!);
      el.style.color = active && isDom ? "#ff8a94" : active ? "#4a5a70" : "#7b8ba1";
      el.style.fontWeight = active && isDom ? "700" : "400";
    });
    plotsRef.current.forEach((p, i) => {
      if (i >= chNames.length) return;
      const isDom = dominant.includes(chNames[i]);
      const dimmed = active && !isDom;
      (p.root as HTMLElement).style.opacity = dimmed ? "0.35" : "1";
    });
  }, [phase, dominant, chNames]);

  return <div ref={wrapRef} className="flex flex-col gap-[3px]" />;
}
