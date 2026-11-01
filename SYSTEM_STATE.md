# Klados Architectural Audit & System State

This file documents the exact hardcoded values, rules, and logic currently implemented in the Klados codebase (`backend/`, `frontend/`, and root scripts). Limits marked *(env)* are read from `backend/app/core/config.py` settings.

## 1. Scraping Velocities & Anti-Ban Safeguards

*   **Sleep Intervals & Delays**:
    *   **Google Maps Extraction**: During missing detail enrichment, human pacing is mimicked by pausing randomly between **3.0s and 7.0s** before navigating to individual place URLs. When scrolling the feed, it pauses exactly **1200ms** per page down.
    *   **Auditing Delay**: The worker paces individual audits within a batch by sleeping randomly between `AUDIT_DELAY_MIN_S` (**3s**) and `AUDIT_DELAY_MAX_S` (**7s**) *(env)*.
*   **Camoufox Parameters & Headers**:
    *   **Google Maps Crawler**: Instantiates `AsyncCamoufox(headless=camoufox_headless_mode(), geoip=True, locale="en-IN")`, retrying the launch up to 3 times.
    *   **Site Auditor**: Uses stronger humanization: `AsyncCamoufox(headless=..., geoip=True, humanize=True, os=["windows"])`. `SiteAuditor` shares **one browser per cell**, launched lazily on the first lead with a website and relaunched if it dies; each site gets a fresh page (its own context).
*   **Google Block Cooldown**: If Maps answers with a CAPTCHA or consent wall, `extract_places` raises `MapsBlockedError`. The worker releases the cell, records the run as `BLOCKED`, and sets the Redis key `maps_blocked` for `MAPS_BLOCK_COOLDOWN_S` (**3600 s**) *(env)*. Every job checks it before touching Maps and backs off; `POST /api/scrape/trigger` returns **503** with `Retry-After` meanwhile.
*   **WSLg X11 Namespace Workaround**:
    *   Because WSLg mounts `/tmp/.X11-unix` as a read-only `tmpfs`, `Xvfb` (which Camoufox relies on) cannot create its socket file.
    *   `run_camoufox.sh` intercepts execution and runs `unshare --user --map-root-user --mount`. Inside this isolated mount namespace, it creates a private writable directory in `$XDG_RUNTIME_DIR` and bind-mounts it over `/tmp/.X11-unix` so `Xvfb` functions normally natively within Linux. The worker is invoked as `./run_camoufox.sh python -m app.worker`.

## 2. Quotas & Limits

*   **Daily Global Limit**: `DAILY_LIMIT = 40` *(env)*.
*   **Per-Cell & Search Limits**:
    *   Maximum **20 leads** per H3 cell (`MAX_LEADS_PER_CELL = 20`) *(env)*.
    *   Manual scan triggers are strictly capped at maximum **6 H3 cells**.
    *   RQ job timeout: **3600 s** per cell.
*   **Redis Key Management & Reset**:
    *   **Worker Tracker**: `leads_collected_today` tracks daily global scrapes. It is reset at **midnight UTC** via an absolute TTL calculation. If Redis can't be read, the worker **fails closed** and treats the limit as reached.
    *   **Coverage**: `seen_cells:{city}:{niche}` sets (lowercased) record scanned cells; every write refreshes a **30-day TTL** (`SEEN_CELLS_TTL_S`).
    *   **Locking**: The API maintains a **24-hour rolling lock** per target in the PostgreSQL `SearchHistory` table. Targets are matched on canonical keys (`normalize_city_key` + `niche_key`: case, punctuation, `&`→`and`, plurals), so `"Gyms"`/`"gym"` share one lock, coverage set and history row.
*   **Limit Reached Behavior**:
    *   **API Response**: Returns `429 Too Many Requests` with a `Retry-After` header and exception string: `"Daily limit reached for '{query}' in '{city}'. Locked until {unlock_time}... Check back tomorrow."`. The dashboard shows this message verbatim.
    *   **Worker Behavior**: If `daily_count >= DAILY_LIMIT` before or during a cell, the worker stops, returns status `"daily_limit_reached"`, **removes the cell from the seen set** so a later run redoes it, and **does not expand** into neighbours.

## 3. Search, Grid & Geographic Coverage

*   **Geographic Indexing**: Uses **H3 resolution level 9** (~0.1 km² per cell; Bengaluru's box is ~7,800 cells).
*   **Cell Order**: `generate_city_cells()` returns cells sorted by grid distance from the bounding-box centre (ties broken by cell ID), so scans start where business density is highest.
*   **City Names**: Normalized by `normalize_city_key()`: `"Bengaluru Central"`, `"bengaluru-central"` and `"bengaluru_central"` are the same key.
*   **Coverage Priorities & Bounding Boxes** (`targets.py`):
    *   **Priority 1 (Karnataka - 12 zones)**: `bengaluru_central`, `bengaluru_south`, `bengaluru_east`, `bengaluru_north`, `mysuru`, `mangaluru`, `hubballi_dharwad`, `belagavi`, `shivamogga`, `davanagere`, `tumakuru`, `udupi_manipal`. Plus a whole-city `bengaluru` box.
    *   **Priority 2 (National Hubs - 7 cities)**: `hyderabad`, `pune`, `chennai`, `mumbai`, `ahmedabad`, `coimbatore`, `kochi`.
    *   Exposed to the dashboard through `GET /api/targets`.
*   **Niche Categories**: **108 keywords** (`BUSINESS_NICHES`) spanning Fitness, Retail, Personal Care, Home & Decor, Healthcare, Automotive, and Events. Free-text niches are also accepted.
*   **Manual Scan Selection**: `POST /api/scrape/trigger` takes the **next 6 not-yet-scanned cells** (centre-out) for the niche/city, marks them seen, and queues one job each. If none remain it returns **409**.
*   **Auto-Expansion / Spillover**: If a cell yields **< 10 new leads** (`EXPANSION_THRESHOLD`), the worker takes its immediate ring (`h3.grid_ring(hex_id, 1)`), keeps neighbours that are inside the city grid and not yet seen, and enqueues up to **2** of them, stopping at `MAX_EXPANSION_DEPTH = 2`.
*   **Exhaustion & Macro Expansion**: Only when **every cell of the city grid** has been seen for the niche does the worker set `CampaignTracker.is_exhausted`, then (if daily budget remains) jump to a random non-exhausted target and queue its first 6 unseen cells. Exhaustion **expires**: flags older than the 30-day coverage TTL are cleared (when listing exhausted targets and before a macro jump), and a scan that finds unscanned cells clears the flag.

## 4. Data Pipeline & Deduplication Logic

*   **Pre-Flight Deduplication SQL**: Before auditing, the worker issues a `SELECT id FROM leads` check. A lead is considered duplicate if:
    *   The `place_id` strictly matches.
    *   The stored phone, stripped of spaces, dashes and `+91`, **ends with the same last 10 digits**.
    *   The `business_name` AND `city` match (case-insensitive) **and a `place_id` is missing on either side**. Two places with different `place_id`s are different businesses, so chain branches are kept as separate leads unless they share a phone number.
*   **Post-Flight Deduplication**: Insertion uses an **untargeted** PostgreSQL `ON CONFLICT DO NOTHING`, so a clash on either the unique `place_id` index or `uq_leads_phone_business` `(phone_number, business_name)` is skipped.
*   **Phone Normalization** (`phones.py`, libphonenumber): numbers are typed with the real Indian numbering plan. Mobiles (and ranges shared by mobiles and landlines) are stored as 10 digits; landlines keep their trunk `0` (e.g. `08041234567`); toll-free, premium and invalid numbers are dropped, and leads without a phone are not saved. Migration `b3e1f9a2c4d6` relabelled 8 existing landlines.
*   **Search History**: Updated after **every** cell (status `COMPLETED`, or `BLOCKED` when Google refused the search), so runs that find nothing don't stay `RUNNING`.
*   **PostgreSQL Schema Specs**:
    *   Primary `leads` table includes standard identification columns + technical flags (`latitude`, `longitude`, `ttfb_ms`, `dom_load_time_ms`, `detected_tech`, `llm_audit_summary`, `lacks_chat_widget`, `lacks_booking_flow`).
    *   **Custom Enums**:
        *   `lead_category`: `"DIGITAL_GHOST"`, `"DIGITAL_DINOSAUR"`, `"LAGGY_UX"`, `"AUTOMATION_CANDIDATE"`.
        *   `outreach_status`: `"PENDING"`, `"AUDITED"`, `"CONTACTED_WHATSAPP"`, `"CONTACTED_EMAIL"`, `"RESPONDED"`, `"CONVERTED"`, `"OPTED_OUT"`.
    *   `campaign_tracker`: `(city, niche)` unique, `is_exhausted`, `last_scraped_at`.
*   **DPDP Act Compliance Fields**:
    *   `origin_source_url`: Captures the exact Maps search string (Text).
    *   `extraction_timestamp`: Timestamped via database `func.now()`.
    *   `opted_out`: Boolean flag default `False`. Opted-out leads stay in the table so dedup never re-collects them.

## 5. Lead Auditing & Classification Rules

Buckets are assigned in a strict fallback chain (`classify_site()` in `site_auditor.py`):

1.  **DIGITAL_GHOST**: The business has no website (`website_url` is None), **or** navigation fails with a DNS / connection / TLS error (`NS_ERROR_UNKNOWN_HOST`, `NS_ERROR_CONNECTION_REFUSED`, `SSL_ERROR`…). `llm_audit_summary` then reads e.g. `"Website unreachable (NS_ERROR_UNKNOWN_HOST)"`.
2.  **DIGITAL_DINOSAUR**:
    *   Missing SSL: the **final URL after redirects** does not begin with `https://`.
    *   OR lacks mobile responsiveness (missing `<meta name='viewport'>` tag in DOM).
3.  **LAGGY_UX**:
    *   Page navigation times out after **15000 ms** (`NAV_TIMEOUT_MS`).
    *   OR DOM Content Loaded (`dom_load_time_ms`) > **4500 ms**.
    *   OR Time to First Byte (`ttfb_ms`) > **1800 ms**.
    *   If the Navigation Timing entry is missing, load time falls back to wall-clock time around `page.goto`.
4.  **AUTOMATION_CANDIDATE**: Passes all above conditions.

*   **Tech, Chat & Booking Detection** (`tech_detector.py`): For every site that loads (and timed-out pages' partial HTML), the HTML is matched against signatures: platforms/libraries (WordPress, Wix, Shopify, GoDaddy Builder, Webflow, Next.js, Google Analytics, Meta Pixel…), chat widgets (Tawk.to, Intercom, Crisp, Freshchat, Interakt, WATI, WhatsApp links…) and booking embeds (Practo, Calendly, Zoho Bookings, Setmore, Fresha…). Matches fill `detected_tech`; any chat/booking match sets `lacks_chat_widget` / `lacks_booking_flow` to `False`.
*   **Ollama Integration** (AUTOMATION_CANDIDATE only): Passes the first 2000 chars of body text to `OLLAMA_URL` *(env, default `http://localhost:11434/api/generate`)* with `OLLAMA_MODEL` *(env, default `llama3:8b`)*. Its `operational_bottleneck` becomes `llm_audit_summary`; its booking/chat answers can only add to what the HTML showed.
    *   **Fallback Handling**: If Ollama times out (30s), refuses the connection, or returns bad JSON, the error is swallowed and `{has_online_booking: False, has_chat_widget: False, operational_bottleneck: "unknown"}` is used.
*   **Worker Fallback**: Any other audit exception saves the lead as `DIGITAL_GHOST` (no website) or `LAGGY_UX` with `"Audit failed: <first line of error>"`. RQ's `JobTimeoutException` is re-raised, not treated as an audit failure.

## 6. Environment & Startup Orchestration

*   **Single `docker-compose.yml`** at the repo root (project name `klados`): `postgres`, `redis`, `api`, `worker`, `frontend`. Containers are named `klados_*`. Volumes are pinned to `backend_postgres_data` / `backend_redis_data`, the names from the old `lead-radar/backend` layout, so existing data carries over. Host ports default to **5434** / **6380** (krama owns 5433 / 6379) and can be overridden with `POSTGRES_PORT` / `REDIS_PORT`. Every published port, and uvicorn / Next.js in the start scripts, binds to **127.0.0.1** only.
*   **`start.sh` Orchestration**:
    *   **WSL Bounce**: Detects if executed in Git Bash (MINGW64/CYGWIN) and actively bounces the script to execute natively via `wsl -e bash "$WSL_PATH/start.sh"`.
    *   **Docker Dependency**: Brings up only PostgreSQL and Redis via `docker compose up -d postgres redis`.
    *   **Dependencies**: `pip install -r requirements.txt` runs on every start, so new dependencies reach an existing venv.
    *   **Migrations**: `alembic upgrade head` before starting services. The Docker `api` image does the same on boot.
    *   **Backgrounding**: Uses Linux standard backgrounding `&` and redirect (`> logs/worker.log 2>&1 &`) to run `uvicorn` and `app.worker` simultaneously.
    *   **Foreground**: Keeps the Next.js `npm run dev` running in the terminal foreground.
    *   **Termination Trap**: Maps a `trap cleanup SIGINT SIGTERM EXIT` function to cleanly kill captured background PIDs (`kill "$pid"`) and stop docker containers upon `Ctrl+C`.
*   **`start.bat`**: Same steps in separate windows; resolves its WSL path with `wslpath` and runs Python tools as `python -m …` using `backend/.venv-windows` when present.
*   **API Endpoints**: `GET /api/leads` (validated `category`/`status`, limit ≤ 1000), `GET /api/leads/stats`, `PATCH /api/leads/:id/status`, `POST /api/leads/:id/opt-out`, `POST /api/scrape/trigger`, `GET /api/search-history`, `GET /api/campaigns/exhausted`, `GET /api/targets`, `GET /health`. The API enqueues `app.worker.process_h3_cell` by dotted path and never imports the browser stack. **Auth**: when `API_KEY` is set *(env)*, every `/api` request needs a matching `X-API-Key` header (the dashboard sends `NEXT_PUBLIC_API_KEY`); `/health` stays open.
*   **Frontend Integration**:
    *   **API base URL**: `NEXT_PUBLIC_API_BASE_URL`, default `http://localhost:8000`.
    *   **Counts**: Metric cards and filter tabs use `/api/leads/stats`; the table loads the latest 500 leads.
    *   **WhatsApp Linking**: `toWhatsAppNumber()` returns null for landlines (stored with a leading `0`), strips an existing `91`, requires 10 digits and prefixes `91`: `https://wa.me/91XXXXXXXXXX?text=...`. Landlines get a `landline` tag and a tap-to-call link instead.
    *   **Templates**: Tailored pitch paragraphs for Ghost (separate copy for an unreachable website), Dinosaur (names the missing HTTPS vs mobile support), Laggy UX (load time in seconds), and Automation Candidates (names the missing booking and/or chat), using the lead's own city.
    *   **Opt-out footer**: `\n\nSource: Public Google Maps listing. Reply STOP to opt out.`

## 7. Known Technical Debt & Fragile Points

Resolved:

*   `seen_cells` sets always get a TTL (legacy keys migrated); the daily counter fails closed; phone dedup tolerates formatting differences; missing navigation timing falls back to wall-clock time.
*   One shared browser per cell instead of one per audit.
*   Google blocks are detected, the cell is released, and scraping pauses for a cooldown.
*   Landlines and mobiles are told apart with libphonenumber; landlines get no WhatsApp link.
*   Chain branches with their own `place_id` are separate leads.
*   Targets are matched on canonical city/niche keys.
*   Exhaustion expires with its coverage record.
*   Services bind to localhost only, and an optional API key closes cross-site requests to the local API.

Still open, by design or low impact:

1.  **India-only numbers**: Phone parsing assumes region `IN` and WhatsApp links use `91`, which matches the current India-only city list.
2.  **Spelling variants**: `niche_key` folds case, punctuation, `&` and plurals, but not synonyms or spelling differences (`"coaching centre"` vs `"coaching centers"` are separate targets).
3.  **API key is visible to the browser**: `NEXT_PUBLIC_API_KEY` is embedded in the dashboard bundle. Fine for a single-user local tool; a multi-user deployment would need real login.
4.  **Consent walls pause scraping**: A consent interstitial is treated like a CAPTCHA (cooldown) rather than clicked through. These are rare for Indian geo-IP.
