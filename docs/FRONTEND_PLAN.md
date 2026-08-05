# Plan — Frontend "sala de control" para el Trustworthy Anomaly Agent

**Objetivo:** una demo web donde un evaluador técnico (ESA o dominio) ve en <2 minutos
los canales de telemetría en streaming, la alarma saltando cuando empieza una anomalía,
y el informe auditado apareciendo cuando el evento cierra — sin configurar nada.

**Decisiones cerradas (2026-08-05):**

| # | Decisión | Elección |
|---|---|---|
| 1 | Datos | **Demo slice autocontenido y committeado** (excepción documentada a la regla de caché) |
| 2 | Arquitectura | **Backend real** FastAPI + SSE que corre `replay()` de verdad |
| 3 | Stack frontend | Vite + React + TS + Tailwind v4 + uPlot; FastAPI sirve los estáticos |
| 4 | Experiencia | Timeline global + replay por evento, **autoplay guiado** al abrir |
| 5 | LLM | Caché committeada por defecto; toggle "live" si hay `GROQ_API_KEY` |
| 6 | Público | Evaluador técnico / técnico del dominio |

---

## 1. Principio arquitectónico

La costura ya existe: `src/m4_report/pipeline.py::replay(flagged_stream, on_open, on_close)`
es una máquina de estados sin lookahead diseñada para que batch y directo difieran solo
en el driver. El backend del frontend **es otro driver**: alimenta `replay()` con las
ventanas marcadas del slice y convierte `on_open`/`on_close` en eventos SSE. No se toca
ningún módulo [1]-[4]; el frontend consume SOLO sus salidas, igual que ellos consumen
solo las salidas del detector.

```
data/demo_slice/*.json  (committeado, construido offline por scripts/build_demo_slice.py)
        │
        ▼
backend/  FastAPI ── REST (misión, eventos, telemetría) ──► frontend/ (React SPA)
          └─ SSE /api/replay/{event}: driver de replay()
             on_open  → evento "anomaly_start"  (START flag literal)
             on_close → evento "anomaly_close"  (alerta auditada + veredicto)
             ticks    → evento "telemetry"      (bloques de muestras + score + p)
```

**Regla de los conectores:** el backend lee artefactos (JSON del slice) y llama a
`replay()`, `start_flag()`, `render_flag()`; nunca importa internals del detector ni
recalcula nada en caliente. El frontend habla solo REST+SSE; nunca lee ficheros del repo.

## 2. El demo slice (fase 0 — la única dependencia externa)

`scripts/build_demo_slice.py` se ejecuta **una vez en la máquina que tiene el dataset y
los artefactos completos** (la de Adolfo) y escribe `data/demo_slice/`:

| Fichero | Contenido | Tamaño estimado |
|---|---|---|
| `mission.json` | canales, rango temporal, α*, stats de cabecera (F0.5, 0 FA, 120/120) | <5 KB |
| `events_index.json` | los 120 contextos M3 + veredicto + START flag de cada uno (para el minimapa) | ~200 KB |
| `events/{id}.json` | por evento sliced (4-6 eventos, el 33 incluido): telemetría 11 canales con margen antes/después (downsampleada a ≤5k puntos/canal), score por ventana, p-value, atribución canal×ventana (heatmap), índices de ventanas marcadas | 1-3 MB c/u |
| `guardrail_block.json` | el caso BLOCK forzado: brief sucio + razones del juez (precomputado con la caché LLM) | <5 KB |

Excepción a la regla de caché documentada en `.gitignore` (como la del LLM): sin el
slice, la demo web de un clon limpio no muestra nada — el coste no es tiempo, es 3,8 GB
de Zenodo, que es una dependencia externa a efectos prácticos.

**Selección de eventos:** el 33 (el ejemplo canónico), 1-2 de alta prioridad con
localization "confident", 1 "diffuse" (el sistema diciendo "no sé dónde"), y si existe
alguno con veredicto FLAG, incluirlo.

**Mientras el slice real no exista:** el mismo script tiene un modo `--synthetic` que
genera un slice sintético con el mismo schema (senoides + una anomalía inyectada) para
poder desarrollar y testear backend+frontend en cualquier máquina. El slice real lo
sustituye sin cambiar una línea.

## 3. Backend (`backend/`)

FastAPI, Python 3.9 (el del proyecto), sin base de datos: el slice se carga en memoria
al arrancar.

| Endpoint | Devuelve |
|---|---|
| `GET /api/mission` | `mission.json` |
| `GET /api/events` | índice de los 120 (contexto resumido + veredicto + qué ids tienen replay) |
| `GET /api/events/{id}` | contexto completo + START flag + alerta de cierre renderizada |
| `GET /api/events/{id}/telemetry` | series + scores + p + atribución del slice |
| `GET /api/replay/{id}?speed=` (SSE) | el stream: `telemetry` (bloques), `anomaly_start`, `anomaly_close` |
| `GET /api/guardrail/block` | el caso BLOCK para el showcase |
| `POST /api/events/{id}/brief/live` | (solo si hay `GROQ_API_KEY`) regenera brief en vivo: generador → precheck → juez; devuelve brief + veredicto + latencias |

El SSE del replay: un generador asíncrono recorre las ventanas del evento con un reloj
comprimido (parámetro `speed`), alimenta `replay()` con los índices marcados según
aparecen, y los callbacks meten los momentos en la cola SSE. Pausable/reanudable desde
el cliente cerrando/reabriendo el stream con `?from=`.

Producción de un solo proceso: `uvicorn backend.app:app` sirve también `frontend/dist/`.

## 4. Frontend (`frontend/`)

Vite + React + TypeScript + Tailwind v4. Gráficas con **uPlot** (canvas, series largas,
cursor sincronizado entre las 11 gráficas). Estado con Zustand (ligero, suficiente).

Componentes principales:

- **`MissionHeader`** — reloj de misión + velocidad + las 3 cifras ancla (F0.5 · 0 FA · 120/120).
- **`ChannelGrid`** — las 11 gráficas apiladas, cursor sincronizado; banda del score/p
  debajo; al abrir un evento, canales atribuidos destacados y el resto atenuado; overlay
  del span del evento.
- **`TimelineMinimap`** — la misión entera con los 120 eventos (color = prioridad;
  forma = confident/diffuse); los sliced son clicables → cargan su replay.
- **`AlarmBanner`** — el START flag literal con etiqueta "determinista · ~100 bytes · sin LLM".
- **`EventReport`** — panel de cierre: tabla de hechos verbatim, vecinos RAG con
  similitud, brief con sello PASS/FLAG/BLOCK, métrica de downlink. Si BLOCK: prosa
  retenida + razones del juez.
- **`GuardrailShowcase`** — botón "¿Y si el modelo mintiera?": brief sucio vs razones
  del juez, frase a frase.
- **`PlaybackControls`** — play/pausa/velocidad/saltar al siguiente momento.

### Guion de los 2 minutos (autoplay al abrir, sin configuración)

| t | Qué pasa |
|---|---|
| 0:00 | Canales pintándose en tiempo comprimido; minimapa y cifras ancla visibles |
| ~0:15 | `anomaly_start` del evento 33 → banner rojo con el flag literal; canales atribuidos se iluminan; barras de atribución en vivo |
| ~0:45 | `anomaly_close` → panel del informe: hechos, vecinos, brief PASS, downlink |
| ~1:15 | CTA al GuardrailShowcase → el caso BLOCK con las razones del juez |
| 1:30+ | Exploración libre: clicar otros eventos del minimapa, cambiar velocidad |

El autoplay es el backend corriendo `replay()` por SSE — no una animación grabada.

## 5. Fases de construcción

| Fase | Entregable | Verificación |
|---|---|---|
| 0 | `scripts/build_demo_slice.py` (+ `--synthetic`) y schema del slice | slice sintético generado y validado contra schema |
| 1 | Backend FastAPI completo sobre el slice + tests de endpoints | `pytest backend/tests` verde con slice sintético |
| 2 | Frontend: shell, ChannelGrid, TimelineMinimap, carga estática de un evento | build limpio, evento navegable sin replay |
| 3 | Replay SSE end-to-end: autoplay, AlarmBanner, EventReport | los dos momentos se disparan desde `replay()` real |
| 4 | GuardrailShowcase, toggle LLM live, pulido del guion de 2 min | recorrido completo cronometrado |
| 5 | Integración: FastAPI sirve `dist/`, README (sección demo web), instrucciones de regenerar el slice real | clon limpio → `make demo` → navegador |

**Bloqueante único:** el slice real (fase 0) requiere la máquina con el dataset. Todo lo
demás se desarrolla contra el slice sintético y no se bloquea.

## 6. Anti-scope

- No se toca ningún módulo [1]-[5] existente (solo se importan sus funciones puras).
- No hay auth, ni base de datos, ni multiusuario, ni despliegue cloud en el MVP.
- No se recalcula detección/atribución en caliente: todo sale del slice precomputado;
  lo único opcionalmente vivo es el brief (con key).
- El frontend nunca inventa números: cada cifra visible es trazable a un campo del slice
  (misma disciplina de carriles que M4).
