// Mission-control layout. Autoplay starts on load: channels reveal with the
// compressed clock, the alarm banner fires on the machine's anomaly_start, the
// audited report slides in on anomaly_close, and the guardrail showcase is one
// click away. The 2-minute tour needs zero configuration.
import { useEffect } from "react";

import AlarmBanner from "./components/AlarmBanner";
import AttributionStrip from "./components/AttributionStrip";
import ChannelGrid from "./components/ChannelGrid";
import EventReport from "./components/EventReport";
import GuardrailShowcase from "./components/GuardrailShowcase";
import MissionHeader from "./components/MissionHeader";
import PlaybackControls from "./components/PlaybackControls";
import TimelineMinimap from "./components/TimelineMinimap";
import { useStore } from "./store";

export default function App() {
  const s = useStore();

  useEffect(() => {
    void useStore.getState().boot();
  }, []);

  if (s.error) {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <div className="max-w-md rounded border border-alarm/50 bg-alarm/10 p-4 text-sm">
          <b>Error:</b> {s.error}
          <p className="text-dim text-xs mt-2">
            ¿Está el backend arrancado? <code>make demo</code> o{" "}
            <code>uvicorn backend.app:app --port 8000</code>
          </p>
        </div>
      </div>
    );
  }
  if (!s.mission) {
    return (
      <div className="h-full flex items-center justify-center text-dim text-sm animate-pulse">
        Cargando el slice de misión…
      </div>
    );
  }

  const dominant = s.detail?.context.dominant_channels ?? [];

  return (
    <div className="h-full flex flex-col">
      <MissionHeader mission={s.mission} missionTime={s.missionTime} speed={s.speed} />

      {s.phase === "alarm" && s.flagText && <AlarmBanner flagText={s.flagText} />}

      <main className="grow flex gap-3 p-4 min-h-0">
        <section className="grow min-w-0 flex flex-col gap-2">
          <div className="flex items-center gap-3">
            <PlaybackControls />
            <div className="text-[11px] text-dim">
              {s.detail && (
                <>
                  evento <b className="text-ink">#{s.detail.event_id}</b> ·{" "}
                  {s.detail.context.localization} · prioridad{" "}
                  {s.detail.context.priority.toFixed(2)}
                  {s.phase === "watching" && " · vigilando telemetría…"}
                  {s.phase === "alarm" && (
                    <span className="text-alarm font-bold"> · EVENTO ABIERTO</span>
                  )}
                  {s.phase === "closed" && " · evento cerrado, informe emitido"}
                </>
              )}
            </div>
          </div>

          <div className="grow overflow-y-auto rounded border border-line bg-panel p-2">
            {s.telemetry ? (
              <>
                <ChannelGrid
                  telemetry={s.telemetry}
                  cursor={s.cursor}
                  phase={s.phase}
                  dominant={dominant}
                  alphaStar={s.mission.alpha_star}
                />
                <div className="mt-1">
                  <AttributionStrip telemetry={s.telemetry} cursor={s.cursor} />
                </div>
              </>
            ) : (
              <div className="h-full flex items-center justify-center text-dim text-sm animate-pulse">
                Cargando telemetría del evento…
              </div>
            )}
          </div>

          <TimelineMinimap
            mission={s.mission}
            events={s.eventsIndex}
            currentId={s.currentEventId}
            onSelect={(id) => void s.selectEvent(id)}
          />
        </section>

        <aside className="w-[440px] shrink-0 flex flex-col gap-3 min-h-0 overflow-y-auto">
          {s.phase === "closed" && s.report ? (
            <EventReport report={s.report} onShowGuardrail={() => s.setShowGuardrail(true)} />
          ) : (
            <div className="rounded border border-line bg-panel p-4 text-[12px] text-dim leading-relaxed">
              <b className="text-ink">Cómo leer esta pantalla.</b> Los 11 canales se
              reproducen con reloj comprimido. Cuando la máquina de estados del pipeline
              (<code>replay()</code>, sin lookahead) abre un evento, salta la{" "}
              <span className="text-alarm">alarma</span> con el flag determinista y se
              iluminan los canales señalados por la atribución. Al volver la calma
              (gap de {s.mission.gap} ventanas), el evento cierra y llega el{" "}
              <b className="text-ink">informe auditado</b>: tablas verbatim, vecinos del
              archivo y un brief que pasó dos guardarraíles (precheck léxico Y juez LLM).
              <div className="mt-3">
                <button
                  onClick={() => s.setShowGuardrail(true)}
                  className="text-[11px] px-2.5 py-1 rounded border border-accent/50 text-accent hover:bg-accent/10 transition-colors"
                >
                  ¿Y si el modelo mintiera? →
                </button>
              </div>
            </div>
          )}

          {s.detail?.retrieval && s.phase !== "closed" && (
            <div className="rounded border border-line bg-panel p-3">
              <div className="text-[10px] font-bold text-dim tracking-wide mb-1.5">
                ARCHIVO · anomalías pasadas similares (RAG determinista)
              </div>
              {s.detail.retrieval.neighbors.slice(0, 4).map((n) => (
                <div key={n.id} className="flex items-center gap-2 text-[11px] font-mono py-0.5">
                  <span className="text-accent">{n.id}</span>
                  <div className="grow h-1.5 rounded bg-panel-2 overflow-hidden">
                    <div className="h-full bg-accent/60" style={{ width: `${n.sim * 100}%` }} />
                  </div>
                  <span className="text-dim">{n.sim.toFixed(2)}</span>
                </div>
              ))}
              <div className="text-[10px] text-dim mt-1">
                novedad de la combinación: {s.detail.retrieval.novelty.toFixed(3)}
              </div>
            </div>
          )}

          <div className="rounded border border-line bg-panel p-3 text-[10.5px] text-dim leading-relaxed">
            <b className="text-ink text-[11px]">Sobre el sistema.</b>{" "}
            Detección F0.5 = {s.mission.about.f05} ({s.mission.about.f05_scope}) — reproduce
            el baseline publicado por ESA. La capa diferencial va encima: p-values
            conformales (α* = {s.mission.alpha_star}), atribución por contrafactual, y un
            LLM que solo redacta — las cifras nunca pasan por él. {s.mission.about.note}
          </div>
        </aside>
      </main>

      {s.showGuardrail && s.guardrail && (
        <GuardrailShowcase guardrail={s.guardrail} onClose={() => s.setShowGuardrail(false)} />
      )}
    </div>
  );
}
