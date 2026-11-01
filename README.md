# Klados

Finds local Indian businesses on Google Maps, audits their websites, and turns
them into outreach-ready leads for website and automation work.

Each business is bucketed by what it most needs:

| Category | Meaning | Pitch |
| --- | --- | --- |
| `DIGITAL_GHOST` | No website, or the listed one doesn't resolve | Build a site |
| `DIGITAL_DINOSAUR` | No HTTPS, or not mobile responsive | Modernize |
| `LAGGY_UX` | TTFB > 1.8 s, load > 4.5 s, or no load within 15 s | Speed fix |
| `AUTOMATION_CANDIDATE` | Healthy site | Add booking / chat automation |

The dashboard lists leads with their tech stack and missing chat/booking, and
sends a tailored WhatsApp pitch in one click (with a DPDP opt-out footer).

## How it works

```
Dashboard (Next.js :3000) ──► API (FastAPI :8000) ──► Redis queue ──► Worker (RQ)
                                    │                                   │
                                    └────────── PostgreSQL ◄────────────┤
                                                                        ├─ Google Maps via Camoufox
                                                                        ├─ Site audit via Camoufox
                                                                        └─ Ollama (llama3:8b), optional
```

1. **Scan**: pick a niche and city. The API takes the next 6 unscanned H3
   cells (resolution 9) from the city's grid, nearest the centre first, and
   queues one job per cell. A niche/city pair then locks for 24 h.
2. **Discover**: the worker searches Maps around the cell's centre, scrolls
   the results, and opens each place for its phone number and website.
3. **Audit**: each new business's site is loaded in a stealth browser and
   classified; the HTML is fingerprinted for platform, chat widgets and
   booking embeds. Ollama adds an "operational bottleneck" note for healthy
   sites when it's running.
4. **Expand**: a cell with fewer than 10 new leads spills into up to 2
   unscanned neighbours (max depth 2). Once a city's whole grid is covered
   for a niche, the pair is marked exhausted and the worker moves on to a
   random fresh target.

Guardrails: at most 40 new leads per day (`DAILY_LIMIT`), 20 per cell, and a
3–7 s random pause between audits.

## Running it

Prerequisites: Docker, Node 20+, Python 3.11+. On Windows the worker runs in
WSL (Camoufox needs Xvfb there); see `backend/run_camoufox.sh`.

```bash
./start.sh        # Linux / WSL / Git Bash (re-launches itself in WSL)
start.bat         # Windows
```

Both start Postgres and Redis in Docker, apply migrations, then run the
worker, the API and the dashboard. Logs go to `logs/`.

To run everything in containers instead: `./start_radar.sh` (or
`start_radar.bat`), i.e. `docker compose up --build -d`.

If ports 5433 or 6379 are taken by another project, override them for both
Docker and the backend:

```bash
POSTGRES_PORT=5434 REDIS_PORT=6380 ./start.sh
```

## Configuration

Backend settings (`backend/app/core/config.py`) come from environment
variables or `backend/.env`:

| Variable | Default |
| --- | --- |
| `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` | `localhost` / `5433` / `leads_db` |
| `REDIS_HOST` / `REDIS_PORT` | `localhost` / `6379` |
| `DAILY_LIMIT` | `40` |
| `MAX_LEADS_PER_CELL` | `20` |
| `AUDIT_DELAY_MIN_S` / `AUDIT_DELAY_MAX_S` | `3` / `7` |
| `OLLAMA_URL` / `OLLAMA_MODEL` | `http://localhost:11434/api/generate` / `llama3:8b` |
| `CORS_ORIGINS` | `["http://localhost:3000","http://127.0.0.1:3000"]` |

Frontend: `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`).

Cities and niches are configured in
`backend/app/services/discovery/targets.py`. A city must have a bounding box
there before it can be scanned.

## Development

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest              # unit tests: no browser, DB or Redis needed

alembic revision --autogenerate -m "..."   # after changing models.py
```

```bash
cd frontend
npm install
npm run lint && npx tsc --noEmit
```

## Layout

```
backend/
  app/main.py                      API
  app/worker.py                    RQ job: discover → dedupe → audit → save → expand
  app/services/discovery/          Maps extractor, H3 grid, coverage, targets
  app/services/auditor/            site audit, tech detection, Ollama classifier
  alembic/                         migrations
  tests/
frontend/src/                      Next.js dashboard
SYSTEM_STATE.md                    detailed rules, thresholds and known limits
```
