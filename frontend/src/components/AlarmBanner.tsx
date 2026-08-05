// Moment 1 of M4: the literal START flag. Deterministic, ~100 bytes, no LLM —
// and the banner says so, because that IS the point.
export default function AlarmBanner({ flagText }: { flagText: string }) {
  return (
    <div className="alarm-banner pulse-red mx-4 mt-3 rounded border border-alarm/60 bg-alarm/10 px-4 py-2.5">
      <div className="flex items-center gap-3">
        <span className="text-alarm font-bold text-xs tracking-widest">⬤ ALARMA</span>
        <code className="font-mono text-[12px] text-ink grow break-all">{flagText}</code>
        <span className="text-[10px] text-dim shrink-0 text-right leading-tight">
          plantilla determinista
          <br />
          ~100 bytes · sin LLM
        </span>
      </div>
    </div>
  );
}
