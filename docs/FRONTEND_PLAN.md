# Plan — Frontend "sala de control" para el Trustworthy Anomaly Agent

**Objetivo:** una demo web donde un evaluador técnico (ESA o dominio) ve en <2 minutos
los canales de telemetría en streaming, la alarma saltando cuando empieza una anomalía,
y el informe auditado apareciendo cuando el evento cierra — sin configurar nada.

**Decisiones cerradas (2026-08-05):**

| # | Decisión | Elección |
|---|---|---|
| 1 | Datos | **Demo slice autocontenido y committeado** (nueva categoría en la regla de caché, ver §2.3) |
| 2 | Arquitectura | **Backend real** FastAPI + SSE; `replay()` real decide los momentos |
| 3 | Stack frontend | Vite + React + TS + Tailwind v4 + uPlot + Zustand; FastAPI sirve los estáticos |
| 4 | Experiencia | Timeline global + replay por evento, **autoplay guiado** al abrir |
| 5 | LLM | **Nada de LLM en vivo**: todo precomputado; guardarraíl con mentiras pregrabadas (§3.3) |
| 6 | Público | Evaluador técnico / técnico del dominio |

> **v2 (2026-08-05):** revisado adversarialmente contra el código. Cambios mayores frente
> a v1: el slice necesita re-cómputo con el modelo (no solo leer artefactos) §2.2; el
> driver SSE ejecuta `replay()` entero y pacea la emisión (no lo alimenta incrementalmente)
> §3.2; el endpoint "brief live" se sustituye por "audita tu brief" §3.3; sin cap de
> downsampling y bookkeeping explícito de índices §2.4; cirugía de `.gitignore` + licencia §2.3.
>
> **v3 (2026-08-05):** segunda revisión independiente. Añadido: `audit-brief` requiere
> desactivar el modo cache-first y una caché de auditoría aparte no canónica §3.3;
> insumos del builder completados (`alpha_choice.npz`, JSONs de M3; p_test es local al
> tercio 3 y hay que mapearlo a global) §2.2; política de margen sin eventos vecinos §2.4;
> `anomaly_close` anclado en `last+gap` §3.2; schema pydantic + golden test del evento 33
> como entregables de fase 0 §5; límites del endpoint público (tamaño, rate, timeout) §3.3.
>
> **v4 (2026-08-05):** decisión del usuario — el visitante no escribe. Fuera el endpoint
> `audit-brief` y todo su contrato runtime; el GuardrailShowcase pasa a mentiras
> pregrabadas del golden set, precomputadas en el slice. La demo ya no necesita
> `GROQ_API_KEY` en ningún despliegue y el backend es 100 % solo-lectura §3.3.
>
> **v5 (2026-08-05):** pasada final de flujo de datos. El SSE deja de retransmitir
> telemetría (REST la sirve una vez; SSE = reloj + momentos) §3.2; margen mínimo = gap,
> garantizado seguro por construcción de los eventos §2.4; gzip + bootstrap de `sys.path`
> + índice ligero para no-sliced §3.2-fin.

---

## 1. Principio arquitectónico

La costura ya existe: `src/m4_report/pipeline.py::replay(flagged_stream, on_open, on_close)`
es una máquina de estados sin lookahead diseñada para que batch y directo difieran solo
en el driver (`pipeline.py:6-8`). El backend del frontend **es otro driver**: los momentos
de la demo (alarma, cierre) los decide `replay()` real, nunca el frontend. No se toca
ningún módulo [1]-[5]; el frontend consume SOLO sus salidas.

```
data/demo_slice/*.json  (committeado, construido offline por scripts/build_demo_slice.py)
        │
        ▼
backend/  FastAPI ── REST (misión, eventos, telemetría) ──► frontend/ (React SPA)
          └─ SSE /api/replay/{event}: agenda de momentos calculada por replay()
             on_open  → evento "anomaly_start"  (START flag literal)
             on_close → evento "anomaly_close"  (alerta auditada + veredicto)
             ticks    → evento "telemetry"      (bloques de muestras + score + p)
```

**Regla de los conectores:** el backend lee el slice y llama a `replay()` y a las
funciones puras `start_flag()`/`render_flag()` (`alert.py:36-59`); nunca importa
internals del detector ni recalcula detección/atribución en caliente. El frontend habla
solo REST+SSE; nunca lee ficheros del repo.

**Restricción de nombres (por los hacks de `sys.path`):** importar `pipeline.py` mete
`src/` y `src/m3_attribution/` en `sys.path`, exponiendo como módulos top-level `config`
y todos los de `m3_attribution/`: `aggregate`, `attribute`, `baseline`, `channels`,
`context`, `evaluate`, `visualize`. Prohibido usar esos nombres para módulos de
`backend/` (usar p. ej. `backend/settings.py`, nunca `backend/config.py`).

## 2. El demo slice (fase 0 — la única dependencia externa)

### 2.1 Qué contiene

| Fichero | Contenido | Tamaño estimado |
|---|---|---|
| `mission.json` | canales, rango temporal cubierto, α*, cifras de cabecera **con su ámbito explícito** (§2.5) | <5 KB |
| `events_index.json` | los 120 eventos: contexto M3 + veredicto + **record verbatim de `m4_start_windows`** (input de `start_flag()`, no solo el flag renderizado) | ~250 KB |
| `events/{id}.json` | por evento sliced (4-6, el 33 incluido): telemetría 11 canales a **resolución completa** con margen antes/después, timestamps ISO + índice global de muestra, score y p por ventana, **matriz de atribución (n_ventanas_marcadas × 11)**, índices globales de ventanas marcadas, **dict de retrieval completo** (vecinos + similitud + novelty) y **`alert_md` re-renderizado** | 1-5 MB c/u |
| `guardrail_block.json` | 2-4 briefs con mentiras plantadas (del golden set de `src/m4_report/evals/`, incl. el brief sucio de `pipeline.py:186-188`) + veredicto BLOCK del juez con razones, **etiquetados como sintéticos** | <20 KB |

### 2.2 Qué necesita el builder (esto es re-cómputo, no solo lectura)

Verificado contra el código: dos de las piezas **no existen en ningún artefacto** y hay
que recomputarlas en la máquina del autor. `build_demo_slice.py` necesita:

1. **Heatmap de atribución por ventana** — `m3_events.json` solo guarda el agregado por
   evento (`aggregate.py:86` suma sobre ventanas) y `m4_start_windows.json` solo la
   primera ventana. El builder carga `model.pkl` + `m3_baseline.npy` + test CSV y
   re-ejecuta `attribute_many` sobre las ventanas marcadas de los eventos sliced.
2. **Retrieval + alerta renderizada** — `m4_alerts.json` excluye `alert_md`
   (`pipeline.py:153`) y el retrieval no se cachea por evento. El builder re-ejecuta
   `retrieve()` (necesita `m4_anomaly_corpus.json`/`labels.csv`) y `render_alert()`.
   Los briefs salen de `m4_alerts.json`; las llamadas LLM son cache-hit garantizado.
3. **Series y bandas** — test CSV (telemetría + timestamps), `scores_continuous.npy`,
   `p_test.npy`, `split.npz` (para los márgenes fuera del evento).
4. **Índices marcados y α*** — `alpha_choice.npz` (junto a `split.npz` + `p_test.npy`
   es lo que carga `marked_global_indices()`, `aggregate.py:44-53`). ⚠️ `p_test.npy`
   está indexado **local al tercio 3**: el builder debe mapearlo a índices globales vía
   `split.npz:window_third == 2`, como hace `aggregate.py:49-53` — nunca asumir que p
   y score comparten eje directamente.
5. **Los JSONs de M3/M4 como insumos** — `m3_events.json`, `m3_event_contexts.json`
   (record completo, con `shared_relations` y `localization`: lo necesitan `retrieve()`,
   `render_alert()` y `evidence_block()`) y `m4_start_windows.json`.
6. **`guardrail_block.json`** — para cada caso de mentira elegido (golden set + brief
   sucio del pipeline), reconstruye el evidence byte-idéntico y **asserta cache-hit** en
   la llamada al juez (si hay miss, el builder falla ruidosamente en vez de pedir API
   key en silencio; los casos del golden set ya fueron juzgados en los evals, así que
   deberían estar cacheados).

**Golden test del builder:** el `alert_md` re-renderizado del evento 33 debe ser
byte-idéntico a la sección "Moment 2" de `docs/m4_alert_example.md` — verificación
gratuita de que el re-cómputo reproduce el pipeline original.

Modo `--synthetic`: genera un slice con el mismo schema (senoides + anomalía inyectada)
para desarrollar backend+frontend sin dataset. El slice real lo sustituye sin cambiar código.

### 2.3 Gobernanza: regla de caché, `.gitignore` y licencia

- **La regla se reformula, no se estira** (decisión del usuario, 2026-08-05). La regla
  actual ("solo si cuesta dinero o API key") diría NO al slice — el PRD retiró por ella
  el nivel "demo desde caches" (`PRD.md:70`). Se añade una **categoría nueva y explícita**
  al `.gitignore` y al README: *se committea lo necesario para ejecutar el frontend de
  demo, para que cualquiera pueda visualizar el sistema en poco tiempo sin dataset ni
  cómputo; contiene extractos del dataset (CC BY 3.0 IGO) con atribución en NOTICE*.
  La excepción queda escrita y justificada, como en su día la de la caché LLM.
- **Cirugía del `.gitignore`:** `/data/*` está excluido y git no re-incluye ficheros
  dentro de un directorio excluido — hay que desexcluir la cadena entera
  (`!/data/demo_slice/`, `/data/demo_slice/*`, `!/data/demo_slice/**/*.json`), igual que
  ya se hizo para `m4_llm_cache.json` (`.gitignore:203-207`).
- **Licencia:** el slice redistribuye extractos de telemetría. Actualizar la frase "the
  dataset is not redistributed here" del README (pasa a "…except a small demo slice,
  attributed under CC BY 3.0 IGO") y añadir la atribución en `NOTICE`.

### 2.4 Bookkeeping de índices y política de margen

Sin downsampling: el evento 33 (~31 h ≈ 6.200 muestras a ~18 s/muestra, más margen)
se pinta a resolución completa — trivial para uPlot en canvas. Todo el slice va keyed
por **índice global de muestra/ventana + timestamp ISO**: ventana global = índice de su
primera muestra (stride 1), así que score, heatmap y telemetría comparten eje (p se
mapea desde el tercio 3, §2.2.4) y el frontend alinea por índice, no por posición.

**Política de margen (los eventos vecinos están cerca — separación media <2 días):**
margen objetivo ~1.500-3.000 muestras por lado, **truncado para que nunca contenga
ventanas marcadas de otro evento**, con **mínimo garantizado = gap (100 ventanas) por
lado**. El mínimo es siempre satisfacible por construcción: dos eventos distintos están
separados por >gap ventanas sin marcar (`aggregate.py:69-76`, si no se fusionarían), así
que las gap ventanas adyacentes a un evento nunca contienen marcas ajenas — y el ancla
del `anomaly_close` (`last+gap`, §3.2) siempre cae dentro del slice. Si el margen cae
parcialmente fuera del tercio 3, p = null en ese tramo y el frontend no pinta la banda ahí.

Tamaño total estimado del slice committeado: **~10-30 MB** de JSON (agregado de §2.1).

### 2.5 Cifras de cabecera: pocas, coherentes y del mismo ámbito

Decisión del usuario: mejor menos cifras si ganan claridad. La cabecera lleva **solo dos
cifras, ambas del mismo ámbito** (el tramo evaluado que el minimapa muestra), formuladas
para que cualquiera las entienda sin contexto:

> **0 falsas alarmas** en 976.182 ventanas normales · **120/120 informes** aprobados por el juez

El F0.5 = 0.949 (que se mide sobre el test completo, otro ámbito) sale de la cabecera y
se muestra en un panel "sobre el sistema" con su framing correcto ("reproduce el baseline
publicado por ESA"). El minimapa cubre **el tercio final** (donde viven los 120 eventos)
y lo declara en el eje. Nota: el scorecard real es 120 PASS / 0 FLAG / 0 BLOCK — el sello
FLAG solo aparecerá en el showcase sintético.

## 3. Backend (`backend/`)

FastAPI; slice cargado en memoria al arrancar; sin base de datos.

**Entorno:** un solo venv, el del proyecto (Python 3.9). FastAPI/uvicorn/starlette se
pinnean en versiones compatibles con 3.9 (3.9 es EOL: las últimas majors pueden exigir
≥3.10). Si el pin resultara inviable, la alternativa es un venv aparte para el backend —
pero entonces no puede importar `replay()`, así que se decide en fase 1, no sobre la marcha.

| Endpoint | Devuelve |
|---|---|
| `GET /api/mission` | `mission.json` |
| `GET /api/events` | índice de los 120 (resumen + veredicto + qué ids tienen replay) |
| `GET /api/events/{id}` | contexto completo + START flag (via `start_flag()` sobre el record del slice) + `alert_md` |
| `GET /api/events/{id}/telemetry` | series + scores + p + heatmap + índices marcados |
| `GET /api/replay/{id}?speed=&from=` (SSE) | el stream: `telemetry`, `anomaly_start`, `anomaly_close`, `done` |
| `GET /api/guardrail` | los casos de mentira pregrabados + veredictos del juez (§3.3) |

### 3.2 El driver SSE (corregido en v2)

`replay()` es síncrono y consume el stream entero — no se puede alimentar
incrementalmente desde un generador asíncrono sin plomería de threads. El diseño limpio:

1. Al abrir la petición, el backend ejecuta `replay()` **entero** sobre los índices
   marcados del evento (microsegundos) con callbacks que capturan la **agenda de
   momentos**. Matiz de honestidad: `on_open` llega en el índice real, pero el close de
   un stream de un solo evento llega por el *flush* de fin de stream — el momento en que
   la máquina lo "observaría" en directo es cuando se cumple el gap de silencio. Por eso
   el `anomaly_close` se ancla en **`last + gap`** (~100 ventanas ≈ 30 min de misión),
   no en `last`.
2. El generador asíncrono avanza el reloj comprimido y **pacea la emisión contra esa
   agenda**: al cruzar el `window_idx` de un momento, emite `anomaly_start`/
   `anomaly_close`. Los momentos siguen decididos por `replay()` real — el claim
   arquitectónico se mantiene — pero sin bloquear el event loop.
3. **El SSE no retransmite telemetría** (simplificación v5): las series completas ya
   viajan una vez por `GET /api/events/{id}/telemetry` (el frontend las necesita igual
   para zoom/scrub) y el ChannelGrid las *revela* client-side hasta la posición del
   reloj. El SSE emite solo señales pequeñas: `tick` (~1/s, posición del reloj de misión
   para sincronía), los momentos, `state`, `done`, `error`. Menos ancho de banda, cero
   duplicación de datos, misma honestidad: los momentos vienen del servidor.
4. **`?from=`** re-ejecuta la agenda desde el principio y suprime la emisión hasta
   `from` — la máquina de estados nunca arranca a mitad (su `on_open` en el primer
   índice visto haría un `anomaly_start` espurio). El primer mensaje tras un seek o una
   reconexión es un **snapshot de estado** (`state`: ¿hay evento abierto? ¿qué flag?)
   para que el cliente no se quede sin el banner si entra pasado el `anomaly_start`.
5. Eventos de control: **`done`** al acabar (sin él, `EventSource` reconecta solo y el
   replay entra en bucle; el cliente cierra al recibirlo) y **`error`** con mensaje
   legible ante fallos del servidor. El generador se cancela cuando el cliente
   desconecta (no se siguen paceando bloques a nadie).

**Dev:** `CORSMiddleware` en FastAPI + proxy de Vite (5173 → 8000) desde la fase 1; el
SSE cross-origin lo exige. **Producción:** un proceso, uvicorn sirve `frontend/dist/`.
**Además:** `GZipMiddleware` (el JSON de telemetría ~2 MB/evento comprime muy bien), y
un módulo de bootstrap (`backend/bootstrap.py`) que inserta `src/` en `sys.path` ANTES
de cualquier import de `pipeline`/`alert` — es el requisito de los hacks de path de §1.
`events_index.json` lleva contexto resumido + veredicto para los 120; el detalle
completo (alert_md, retrieval, heatmap) solo existe para los eventos sliced.

### 3.3 El guardarraíl: mentiras pregrabadas, sin escribir y sin LLM en vivo (v4)

Decisión del usuario (2026-08-05): **el visitante no escribe nada**. Queda descartado
el endpoint `audit-brief` (y con él su contrato runtime: toggle de caché, caché de
auditoría, rate limiting — toda esa superficie desaparece). Nota para el histórico:
"regenerar el brief en vivo" tampoco era viable — `llm.py` es cache-first siempre
(misma clave sha256 → respuesta canónica, `llm.py:61-62`) y en modo cache-first un miss
lanza `RuntimeError` aunque haya API key (`llm.py:63-68`).

En su lugar, el **GuardrailShowcase es interactivo pero pregrabado**: botones tipo
"prueba a colarle esta mentira al juez" con 2-4 casos fijos (afirmar causa raíz,
exagerar certeza, inventar un vecino…) sacados del **golden set existente** (18 briefs
etiquetados a mano, 11 con violaciones plantadas — `src/m4_report/evals/`). Al pulsar,
se muestra el brief trucado y el veredicto BLOCK real del juez con sus razones. Los
veredictos los precomputa el builder en la máquina del autor (cache-hits o llamadas
únicas con su key) y viajan en `guardrail_block.json` dentro del slice.

Consecuencias: la demo completa funciona **sin `GROQ_API_KEY` en ningún despliegue**,
no hay ningún endpoint público que llame a un LLM, y `m4_llm_cache.json` no se toca.
El backend queda 100 % de solo-lectura sobre el slice.

## 4. Frontend (`frontend/`)

Vite + React + TypeScript + Tailwind v4; uPlot (canvas, series largas, cursor
sincronizado entre las 11 gráficas); Zustand para el estado.

| Componente | Concepto del sistema que representa |
|---|---|
| `MissionHeader` | reloj de misión + velocidad + cifras ancla con su ámbito (§2.5) |
| `ChannelGrid` | telemetría (M1); banda score/p debajo (M1/M2); highlight de canales atribuidos + heatmap (M3); overlay del span del evento |
| `TimelineMinimap` | el tercio final con los 120 eventos (color = prioridad, forma = confident/diffuse); los sliced, clicables |
| `AlarmBanner` | momento 1 de M4: el START flag literal, "determinista · ~100 bytes · sin LLM" |
| `EventReport` | momento 2 de M4: hechos verbatim, vecinos RAG, brief con sello, downlink |
| `GuardrailShowcase` | "prueba a colarle esta mentira al juez": casos pregrabados + veredicto BLOCK con razones (§3.3) |
| `PlaybackControls` | play/pausa/velocidad/saltar al siguiente momento |

### Guion de los 2 minutos (autoplay al abrir)

| t | Qué pasa |
|---|---|
| 0:00 | Canales pintándose en tiempo comprimido; minimapa y cifras ancla visibles |
| ~0:15 | `anomaly_start` del evento 33 → banner rojo con el flag literal; canales atribuidos iluminados; heatmap de atribución creciendo |
| ~0:45 | `anomaly_close` → panel del informe: hechos, vecinos, brief PASS, downlink |
| ~1:15 | CTA al GuardrailShowcase → elige una mentira, mira al juez bloquearla con razones |
| 1:30+ | Exploración libre: otros eventos del minimapa, velocidad, pausa |

## 5. Fases de construcción

| Fase | Entregable | Verificación |
|---|---|---|
| 0 | **Schema del slice como modelos pydantic** (nombres/tipos/unidades exactos) + `scripts/build_demo_slice.py` (+ `--synthetic`) con los insumos de §2.2 y la política de margen §2.4; cirugía `.gitignore` + NOTICE/README (§2.3) | slice sintético validado contra schema; builder real: golden test del evento 33 (§2.2) + assert cache-hit del BLOCK |
| 1 | Backend FastAPI (pins py3.9) + CORS/proxy + tests de endpoints | `pytest backend/tests` verde con slice sintético |
| 2 | Frontend: shell, ChannelGrid, TimelineMinimap, carga estática de un evento | build limpio, evento navegable sin replay |
| 3 | Replay SSE end-to-end (§3.2): autoplay, AlarmBanner, EventReport, `done` | los momentos salen de la agenda de `replay()` real; reconexión no duplica |
| 4 | GuardrailShowcase con los casos pregrabados (§3.3) + pulido del guion de 2 min | recorrido completo cronometrado |
| 5 | Integración: uvicorn sirve `dist/`, README (sección demo web), instrucciones del slice real | clon limpio → `make demo` → navegador |

**Bloqueante único:** el slice real (fase 0) se genera en la máquina con el dataset y
los artefactos (la de Adolfo). Todo lo demás avanza contra el slice sintético.

## 6. Anti-scope

- No se toca ningún módulo [1]-[5] existente (solo imports de funciones puras + `replay()`).
- No hay auth, base de datos, multiusuario ni despliegue cloud en el MVP.
- No se recalcula nada en caliente ni hay ninguna llamada LLM en vivo: todo sale del
  slice; el backend es solo-lectura y la demo no necesita `GROQ_API_KEY`.
- El frontend nunca inventa números: cada cifra visible es trazable a un campo del slice
  (misma disciplina de carriles que M4), y cada cifra de cabecera lleva su ámbito.
