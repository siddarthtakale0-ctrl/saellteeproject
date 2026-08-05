# La demo web, explicada — qué es, cómo funciona y qué te queda por hacer

> Guía rápida de la "sala de control" añadida en la rama
> `claude/adb-trustworthy-frontend-3htioq`. El plan completo con las decisiones de
> diseño está en [`FRONTEND_PLAN.md`](FRONTEND_PLAN.md); esto es la versión de 5 minutos.

---

## 1. Qué es

Una web donde un evaluador ve el sistema **funcionar** sin leer código, en 2 minutos:

1. Al abrir, los 11 canales de telemetría se reproducen con reloj acelerado.
2. Cuando la máquina de estados del pipeline abre un evento, **salta la alarma**: banner
   rojo con el START flag literal (determinista, ~100 bytes, sin LLM) y los canales
   señalados por la atribución se iluminan; el resto se atenúa.
3. Cuando vuelve la calma (gap de 100 ventanas), el evento cierra y aparece el
   **informe auditado**: tabla de hechos verbatim, vecinos del archivo (RAG) y el brief
   con su sello PASS del juez.
4. Un botón — *"¿Y si el modelo mintiera?"* — abre el showcase del guardarraíl:
   mentiras plantadas a mano (del golden set del repo) con el **veredicto BLOCK real**
   del juez y sus razones frase a frase.

Nadie configura nada, nadie escribe nada, y no hace falta ni dataset ni API key.

## 2. Cómo funciona (las tres piezas)

```
data/demo_slice/          los DATOS, congelados (committeados en el repo)
        │
        ▼
backend/  (FastAPI)       sirve los datos por REST y corre el replay por SSE
        │
        ▼
frontend/ (React SPA)     pinta, revela y anima — nunca decide nada
```

- **El slice** (`data/demo_slice/`): telemetría de los eventos reproducibles, scores,
  p-values, heatmap de atribución, informes renderizados y los casos del guardarraíl.
  Su contrato es `backend/slice_schema.py` — si un slice no valida, el backend no arranca.
- **El backend** (`backend/`): de solo lectura, sin base de datos, sin llamadas al LLM.
  Lo importante: el endpoint SSE `/api/replay/{id}` ejecuta **el `replay()` real de
  `src/m4_report/pipeline.py`** sobre las ventanas marcadas del evento y emite sus
  momentos (alarma/cierre) al ritmo del reloj comprimido. Es decir: la alarma que ves
  la decide tu máquina de estados, no el frontend — el backend es literalmente "otro
  driver", que era el claim de diseño del pipeline.
- **El frontend** (`frontend/`): Vite + React + TypeScript + Tailwind + uPlot. Carga
  las series una vez por REST y las va **revelando** hasta donde marca el reloj que
  llega por SSE. Solo habla HTTP; jamás lee ficheros del repo.

**El punto clave de honestidad:** hoy el slice committeado es **SINTÉTICO** (señales
generadas, sin un byte del dataset). La web lo declara con un badge ámbar "DATOS
SINTÉTICOS". Lo único real incluso ahora son los casos del guardarraíl: briefs del
golden set + veredictos congelados del juez, ambos ya committeados en el repo.

## 3. Probarla (en cualquier máquina, ya mismo)

```bash
git checkout claude/adb-trustworthy-frontend-3htioq
pip install -r backend/requirements.txt   # en tu venv del proyecto
make demo                                  # -> http://localhost:8000
```

`make demo` construye el frontend si hace falta (necesita node/npm) y levanta un solo
proceso que sirve API + web. Tests del backend: `make backend-test` (12 tests).

Para desarrollo con recarga: `make backend-dev` en una terminal y `make frontend-dev`
en otra (Vite en :5173 con proxy a :8000).

## 4. Lo que te queda por hacer desde tu PC (el del dataset)

Una sola tarea: **sustituir el slice sintético por el real**. Son ~10 minutos.

```bash
# 1. En tu Mac, con el proyecto como siempre (dataset en data/ESA-Mission2/,
#    artefactos en data/cached/ ya generados por el notebook):
git checkout claude/adb-trustworthy-frontend-3htioq
source .venv/bin/activate
pip install -r backend/requirements.txt    # añade fastapi/pydantic a tu venv

# 2. Construir el slice real:
make slice-real          # = python scripts/build_demo_slice.py
```

Qué hace ese comando (y qué debe salir):

- Elige los eventos: el **33** (el canónico), los 2 de mayor prioridad, y uno con
  localización "diffuse" si existe. (¿Quieres otros? `python scripts/build_demo_slice.py
  --events 33 12 87`.)
- Recomputa lo que ningún artefacto guarda: la atribución ventana a ventana (con
  `model.pkl`) y el retrieval + informe renderizado de cada evento sliced.
- **Golden test:** el informe re-renderizado del evento 33 debe salir *byte-idéntico*
  a `docs/m4_alert_example.md`. Si difiere, el script falla — eso significaría que el
  re-cómputo no reproduce tu pipeline, y hay que mirarlo, no ignorarlo.
- **Cache-hit assert:** los veredictos del guardarraíl deben encontrarse en la caché
  LLM committeada. Si hay un miss, falla ruidosamente (nunca pide API key en silencio).
- Valida todo contra el schema y escribe `data/demo_slice/` (~10-30 MB).

```bash
# 3. Verificar en local:
make backend-test        # los 12 tests corren igual sobre el slice real
make demo                # abrir localhost:8000 -> el badge ambar YA NO debe aparecer
                         # y el autoplay debe ser el evento 33

# 4. Committear y subir (el .gitignore ya permite exactamente estos ficheros):
git add data/demo_slice/
git commit -m "data: slice real de demo (extractos ESA-ADB M2, CC BY 3.0 IGO, ver NOTICE)"
git push origin claude/adb-trustworthy-frontend-3htioq
```

No hay que tocar ni una línea de código: frontend y backend no distinguen un slice del
otro (mismo schema). El badge desaparece solo porque `mission.json` pasa a
`"synthetic": false`.

### Si algo falla en el paso 2

- *"No module named fastapi/pydantic"* → falta el paso `pip install -r backend/requirements.txt`.
- *Falta un fichero en `data/cached/`* → ese artefacto no está generado; ejecuta el
  notebook completo una vez (Run All) y reintenta.
- *Golden test failed* → el entorno recomputa distinto de cuando horneaste el notebook
  (¿versiones de numpy/pandas cambiadas?). No committees ese slice; cuéntamelo.

## 5. Después (opcional, cuando el slice real esté subido)

- **Enseñarla**: `make demo` y compartir pantalla, o desplegarla (un contenedor con
  `pip install + make demo` sirve; es un solo proceso sin estado).
- **Abrir PR a `main`** cuando la des por buena — la rama está lista y auto-contenida.
- **README**: la sección "Web demo" ya existe; si quieres, añadimos un GIF/screenshot
  del momento de la alarma (queda muy bien arriba del todo).

## 6. Mapa de ficheros añadidos

| Ruta | Qué es |
|---|---|
| `docs/FRONTEND_PLAN.md` | El plan cerrado (2 revisiones adversariales + pasada de flujo) |
| `backend/slice_schema.py` | El contrato del slice (pydantic, con invariantes de alineación) |
| `scripts/build_demo_slice.py` | El builder: `--synthetic` (cualquier máquina) / real (tu Mac) |
| `data/demo_slice/` | El slice committeado (hoy sintético; lo sustituyes tú) |
| `backend/` | FastAPI: REST + SSE con el `replay()` real · 12 tests en `backend/tests/` |
| `frontend/` | La SPA (Vite + React + TS + Tailwind v4 + uPlot) |
| `Makefile` | `demo` · `slice-real` · `backend-test` · `backend-dev` · `frontend-dev` |
