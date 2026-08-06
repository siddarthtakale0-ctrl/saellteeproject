// The closing report. A plain-language summary up front (duration, culprit channels,
// confidence, how familiar it is), then the written brief, and the raw verbatim tables
// folded away behind "technical detail" for whoever wants the audit trail.
// Ground-station styling: instrument card, monospace label header.
import { useState } from "react";

import { EventDetail } from "../api";
import { AlertMarkdown } from "../markdown";

interface Report {
  verdict: string;
  reasons: string[];
  brief: string | null;
  alert_md: string;
}

function familiarity(novelty: number | undefined): string | null {
  if (novelty == null) return null;
  if (novelty < 0.2) return "resembles anomalies that already happened";
  if (novelty < 0.35) return "partly resembles past anomalies";
  return "no clear precedent in the archive";
}

export default function EventReport({
  report,
  detail,
}: {
  report: Report;
  detail: EventDetail | null;
}) {
  const [showRaw, setShowRaw] = useState(false);
  const ctx = detail?.context;
  const hours = ctx ? Math.round(ctx.duration_sec / 3600) : null;
  const culprits = (ctx?.dominant_channels ?? [])
    .map((c) => c.replace("channel_", ""))
    .join(", ");
  const fam = familiarity(detail?.retrieval?.novelty);

  return (
    <div className="hudcard overflow-hidden">
      <div className="px-3 py-2 border-b border-line bg-panel-2">
        <span className="font-mono text-[11px] uppercase tracking-[0.12em] font-bold text-ink">
          EVENT REPORT
        </span>
      </div>
      <div className="p-3 max-h-[560px] overflow-y-auto text-[13px] leading-relaxed">
        {report.verdict === "BLOCK" && (
          <div className="mb-2 text-[12px] text-alarm">
            The report was withheld: a claim was not supported by the data
            ({report.reasons.join(" · ")}).
          </div>
        )}

        {ctx && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 mb-3">
            <dt className="hud-label">Lasted</dt>
            <dd className="text-ink tnum">{hours} hours</dd>
            <dt className="hud-label">Culprit channels (overall)</dt>
            <dd className="text-alarm font-semibold tnum">{culprits}</dd>
            <dt className="hud-label">Confidence</dt>
            <dd className="text-ink">maximum</dd>
            {fam && (
              <>
                <dt className="hud-label">Archive</dt>
                <dd className="text-ink">{fam}</dd>
              </>
            )}
          </dl>
        )}

        {report.brief && (
          <div className="mb-3">
            <div className="hud-label mb-1">The written report (all the model writes)</div>
            <p className="leading-relaxed text-ink/90">{report.brief}</p>
          </div>
        )}

        <button
          onClick={() => setShowRaw((v) => !v)}
          className="text-[11px] text-accent hover:underline font-mono"
        >
          {showRaw ? "▾ hide" : "▸ show"} technical detail (verbatim table + similar cases)
        </button>
        {showRaw && (
          <div className="mt-2 pt-2 border-t border-line">
            <AlertMarkdown md={report.alert_md} />
          </div>
        )}
      </div>
    </div>
  );
}
