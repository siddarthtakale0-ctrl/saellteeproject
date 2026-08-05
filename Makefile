# Web demo shortcuts. `make demo` = the whole thing on http://localhost:8000
PY ?= python3

demo: slice frontend/dist
	$(PY) -m uvicorn backend.app:app --port 8000

# The committed slice ships with the repo; rebuild only if missing.
slice:
	@test -f data/demo_slice/mission.json || $(PY) scripts/build_demo_slice.py --synthetic

frontend/dist: frontend/package.json $(wildcard frontend/src/*) $(wildcard frontend/src/components/*)
	cd frontend && npm install && npm run build

# Dev: backend on :8000 + Vite on :5173 (proxies /api). Run in two terminals:
backend-dev:
	$(PY) -m uvicorn backend.app:app --port 8000 --reload
frontend-dev:
	cd frontend && npm run dev

backend-test:
	$(PY) -m pytest backend/tests -q

# Real slice (machine holding the dataset + artifacts only):
slice-real:
	$(PY) scripts/build_demo_slice.py

.PHONY: demo slice backend-dev frontend-dev backend-test slice-real
