// Moment 2 of M4: the closing alert. Facts table verbatim, RAG neighbors, the
// audited brief with its verdict seal. If BLOCK: prose withheld + judge reasons.
import { AlertMarkdown } from "../markdown";

interface Report {
  verdict: string;
  reasons: string[];
  brief: string | null;
  alert_md: string;
}

const SEAL: Record<string, { cls: string; label: string }> = {
  PASS: { cls: "bg-ok/15 text-ok border-ok/50", label: "PASS · juez + precheck" },
  FLAG: { cls: "bg-amber-500/15 text-amber-400 border-amber-500/50", label: "FLAG · aprobado con nota" },
  BLOCK: { cls: "bg-alarm/15 text-alarm border-alarm/50", label: "BLOCK · prosa retenida" },
};

export default function EventReport({
  report,
  onShowGuardrail,
}: {
  report: Report;
  onShowGuardrail: () => void;
}) {
  const seal = SEAL[report.verdict] ?? SEAL.PASS;
  return (
    <div className="rounded border border-line bg-panel overflow-hidden">
      <div className="flex items-center gap-3 px-3 py-2 border-b border-line bg-panel-2">
        <span className="text-xs font-bold tracking-wide">INFORME DE CIERRE</span>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${seal.cls}`}>
          {seal.label}
        </span>
        <button
          onClick={onShowGuardrail}
          className="ml-auto text-[11px] px-2.5 py-1 rounded border border-accent/50 text-accent hover:bg-accent/10 transition-colors"
        >
          ¿Y si el modelo mintiera? →
        </button>
      </div>
      <div className="p-3 max-h-[420px] overflow-y-auto">
        {report.verdict === "BLOCK" && (
          <div className="mb-2 text-[11px] text-alarm">
            El brief fue retenido por el guardarraíl. Razones del juez:{" "}
            {report.reasons.join(" · ")}
          </div>
        )}
        <AlertMarkdown md={report.alert_md} />
      </div>
    </div>
  );
}
