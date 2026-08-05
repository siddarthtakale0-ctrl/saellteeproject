// "¿Y si el modelo mintiera?" — pre-recorded lies from the golden set, each with
// the judge's REAL verdict. The visitor never writes anything: pick a lie, watch
// the guardrail block it, sentence by sentence.
import { useState } from "react";

import { Guardrail } from "../api";

export default function GuardrailShowcase({
  guardrail,
  onClose,
}: {
  guardrail: Guardrail;
  onClose: () => void;
}) {
  const [selected, setSelected] = useState(0);
  const c = guardrail.cases[selected];

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-6" onClick={onClose}>
      <div
        className="w-full max-w-3xl rounded-lg border border-line bg-panel shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b border-line bg-panel-2 flex items-center">
          <div>
            <h2 className="text-sm font-bold">¿Y si el modelo mintiera?</h2>
            <p className="text-[11px] text-dim">
              Mentiras plantadas a mano (golden set del repo) · veredictos reales del juez LLM ·
              nada se genera en vivo
            </p>
          </div>
          <button onClick={onClose} className="ml-auto text-dim hover:text-ink text-xl leading-none">×</button>
        </div>

        <div className="flex flex-wrap gap-1.5 px-4 pt-3">
          {guardrail.cases.map((gc, i) => (
            <button
              key={gc.id}
              onClick={() => setSelected(i)}
              className={`text-[11px] px-2.5 py-1 rounded border transition-colors ${
                i === selected
                  ? "border-alarm text-alarm bg-alarm/10"
                  : "border-line text-dim hover:text-ink hover:border-dim"
              }`}
            >
              {gc.title}
            </button>
          ))}
        </div>

        <div className="p-4 grid gap-3">
          <div>
            <div className="text-[10px] font-bold text-dim tracking-wide mb-1">
              EL BRIEF TRUCADO <span className="font-normal">({c.tests})</span>
            </div>
            <p className="text-[12.5px] leading-relaxed rounded border border-line bg-panel-2 p-3 font-mono">
              {c.brief}
            </p>
          </div>
          <div>
            <div className="text-[10px] font-bold tracking-wide mb-1 flex items-center gap-2">
              <span className="text-alarm">VEREDICTO DEL JUEZ:</span>
              <span className="px-2 py-0.5 rounded border border-alarm/50 bg-alarm/15 text-alarm font-bold">
                {c.verdict}
              </span>
              <span className="text-dim font-normal">— el aviso baja con las tablas; la prosa se retiene</span>
            </div>
            <ul className="grid gap-1.5">
              {c.reasons.map((r, i) => (
                <li key={i} className="text-[12px] leading-relaxed rounded border border-alarm/30 bg-alarm/5 p-2.5">
                  {r}
                </li>
              ))}
            </ul>
          </div>
          <p className="text-[10.5px] text-dim">
            Cada veredicto es la respuesta congelada del juez (LLM-as-judge) para ese brief,
            auditado contra la evidencia del evento {guardrail.evidence_ref.replace("event_", "")}.
            Sobre los 120 eventos reales el generador nunca necesitó un BLOCK: 120/120 limpios.
          </p>
        </div>
      </div>
    </div>
  );
}
