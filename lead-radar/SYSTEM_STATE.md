# Lead Radar Architectural Audit & System State

This file documents the exact hardcoded values, rules, and logic currently implemented in the Lead Radar codebase (`backend/`, `frontend/`, and root scripts) as of the current state.

## 1. Scraping Velocities & Anti-Ban Safeguards

*   **Sleep Intervals & Delays**:
    *   **Google Maps Extraction**: During missing detail enrichment, human pacing is mimicked by pausing randomly between **3.0s and 7.0s** before navigating to individual place URLs. When scrolling the feed, it pauses exactly **1200ms** per page down.
    *   **Auditing Delay**: The worker paces individual audits within a batch by sleeping randomly between `AUDIT_DELAY_MIN_S` (**3s**) and `AUDIT_DELAY_MAX_S` (**7s**).
*   **Camoufox Parameters & Headers**:
    *   **Google Maps Crawler**: Instantiates `AsyncCamoufox(headless=camoufox_headless_mode(), geoip=True, locale="en-IN")`.
    *   **Site Auditor**: Uses stronger humanization: `AsyncCamoufox(headless=..., geoip=True, humanize=True, os=["windows"])`.
*   **WSLg X11 Namespace Workaround**:
    *   Because WSLg mounts `/tmp/.X11-unix` as a read-only `tmpfs`, `Xvfb` (which Camoufox relies on) cannot create its socket file.
    *   `run_camoufox.sh` intercepts execution and runs `unshare --user --map-root-user --mount`. Inside this isolated mount namespace, it creates a private writable directory in `$XDG_RUNTIME_DIR` and bind-mounts it over `/tmp/.X11-unix` so `Xvfb` functions normally natively within Linux. The worker is invoked as `./run_camoufox.sh python -m app.worker`.

## 2. Quotas & Limits

*   **Daily Global Limit**: `DAILY_LIMIT = 50` (configurable via env var).
*   **Per-Cell & Search Limits**:
    *   Maximum **20 leads** per H3 cell (`MAX_LEADS_PER_CELL = 20`).
    *   Manual scan triggers are strictly capped at maximum **6 H3 cells**.
*   **Redis Key Management & Reset**:
    *   **Worker Tracker**: `leads_collected_today` tracks daily global scrapes. It is reset at **midnight UTC** via an absolute TTL calculation.
    *   **Locking**: The API maintains a **24-hour rolling lock** per `(niche, city)` pair in the PostgreSQL `SearchHistory` table.
*   **Limit Reached Behavior**:
    *   **API Response**: Returns `429 Too Many Requests` with a `Retry-After` header and exception string: `"Daily limit reached for '{query}' in '{city}'. Locked until {unlock_time}... Check back tomorrow."`.
    *   **Worker Behavior**: If `daily_count >= DAILY_LIMIT` is hit during a batch, the worker logs a warning, halts processing mid-batch, and returns status `"daily_limit_reached"`.
    *   **Frontend UI Guard**: `ScanTrigger.tsx` catches the `429` error, displays an error message, and disables inputs and buttons (`disabled={loading}`) during submission.

## 3. Search, Grid & Geographic Coverage

*   **Geographic Indexing**: Uses **H3 resolution level 9**.
*   **Coverage Priorities & Bounding Boxes**:
    *   **Priority 1 (Karnataka - 12 zones)**: `bengaluru_central`, `bengaluru_south`, `bengaluru_east`, `bengaluru_north`, `mysuru`, `mangaluru`, `hubballi_dharwad`, `belagavi`, `shivamogga`, `davanagere`, `tumakuru`, `udupi_manipal`.
    *   **Priority 2 (National Hubs - 7 cities)**: `hyderabad`, `pune`, `chennai`, `mumbai`, `ahmedabad`, `coimbatore`, `kochi`.
*   **Niche Categories**: **131 distinct supported keywords** spanning Fitness, Retail, Personal Care, Home & Decor, Healthcare, Automotive, and Events.
*   **Selection Mechanism**: Targets are selected using a strict sequential `itertools.cycle` cartesian product of the cities and niches, prioritizing Karnataka first. A `"random"` sampling mode is also available.
*   **Auto-Expansion / Spillover**: If a cell yields **< 10 leads**, the worker initiates "Smart Spatial Expansion". It resolves immediate neighbors via `h3.k_ring(hex_id, k=1)` (or `grid_disk`), filters out previously visited cells via the Redis `seen_cells:{city}:{query}` cache, and enqueues up to **2 unvisited adjacent cells** for scraping, stopping at `MAX_EXPANSION_DEPTH = 2`.

## 4. Data Pipeline & Deduplication Logic

*   **Pre-Flight Deduplication SQL**: Before auditing, the worker issues a `SELECT id FROM leads` check. A lead is considered duplicate if:
    *   The `place_id` strictly matches.
    *   The `phone_number` strictly matches.
    *   The `business_name` (lowercased) AND `city` (lowercased) match.
*   **Post-Flight Deduplication**: Database insertion utilizes PostgreSQL `ON CONFLICT DO NOTHING`. It relies on a unique index for `place_id` and a unique constraint `uq_leads_phone_business` for `(phone_number, business_name)`.
*   **PostgreSQL Schema Specs**:
    *   Primary `leads` table includes standard identification columns + technical flags (`latitude`, `longitude`, `ttfb_ms`, `dom_load_time_ms`, `detected_tech`, `llm_audit_summary`, `lacks_chat_widget`, `lacks_booking_flow`).
    *   **Custom Enums**:
        *   `lead_category`: `"DIGITAL_GHOST"`, `"DIGITAL_DINOSAUR"`, `"LAGGY_UX"`, `"AUTOMATION_CANDIDATE"`.
        *   `outreach_status`: `"PENDING"`, `"AUDITED"`, `"CONTACTED_WHATSAPP"`, `"CONTACTED_EMAIL"`, `"RESPONDED"`, `"CONVERTED"`, `"OPTED_OUT"`.
*   **DPDP Act Compliance Fields**:
    *   `origin_source_url`: Captures the exact Maps search string (Text).
    *   `extraction_timestamp`: Timestamped via database `func.now()`.
    *   `opted_out`: Boolean flag default `False`.

## 5. Lead Auditing & Classification Rules

Buckets are assigned in a strict fallback chain based on the following precise thresholds:

1.  **DIGITAL_GHOST**: The business has no website (`website_url` is None).
2.  **DIGITAL_DINOSAUR**:
    *   Missing SSL (`has_ssl=False`, URL does not begin with `https://`).
    *   OR lacks mobile responsiveness (missing `<meta name='viewport'>` tag in DOM).
3.  **LAGGY_UX**:
    *   Page navigation strictly fails or times out after **15000 ms** (`NAV_TIMEOUT_MS`).
    *   OR DOM Content Loaded (`dom_load_time_ms`) > **4500 ms**.
    *   OR Time to First Byte (`ttfb_ms`) > **1800 ms**.
4.  **AUTOMATION_CANDIDATE**: Passes all above conditions.
    *   **Ollama Integration**: Passes body text to local Ollama via HTTP POST (`http://localhost:11434/api/generate`).
    *   **Model**: `llama3:8b`.
    *   **Prompt**: "You are auditing a small business's website to find operational gaps that automation could fix..."
    *   **Fallback Handling**: If Ollama timeouts (30s limit), connection refuses, or returns bad JSON, the script swallows the error to prevent crash and returns `{has_online_booking: False, has_chat_widget: False, operational_bottleneck: "unknown"}`.

## 6. Environment & Startup Orchestration

*   **`start.sh` Orchestration**:
    *   **WSL Bounce**: Detects if executed in Git Bash (MINGW64/CYGWIN) and actively bounces the script to execute natively via `wsl -e bash "$WSL_PATH/start.sh"`.
    *   **Docker Dependency**: Brings up PostgreSQL and Redis via `docker compose up -d`.
    *   **Backgrounding**: Uses Linux standard backgrounding `&` and redirect (`> logs/worker.log 2>&1 &`) to run `uvicorn` and `app.worker` simultaneously.
    *   **Foreground**: Keeps the Next.js `npm run dev` running in the terminal foreground.
    *   **Termination Trap**: Maps a `trap cleanup SIGINT SIGTERM EXIT` function to cleanly kill captured background PIDs (`kill "$pid"`) and stop docker containers upon `Ctrl+C`.
*   **Frontend Integration**:
    *   **Endpoints Consumed**: `GET /api/leads`, `PATCH /api/leads/:id/status`, `POST /api/leads/:id/opt-out`, `POST /api/scrape/trigger`, `GET /api/search-history`.
    *   **WhatsApp Linking**: Formats wa.me links with hardcoded country code: `https://wa.me/91${cleanPhone}?text=${encodedMessage}`.
    *   **Templates**: Tailored pitch paragraphs for Ghost, Dinosaur, Laggy UX, and Automation Candidates.
    *   **Opt-out footer**: `\n\nSource: Public Google Maps listing. Reply STOP to opt out.`

## 7. Known Technical Debt & Fragile Points

1.  **Redis Memory Leak (Unbounded Set Growth)**: The `seen_cells:{city}:{query}` Redis sets (used to track visited cells during smart expansion and prevent loops) do not have a TTL configured (`r.expire()`). They will persist permanently and slowly leak Redis memory.
2.  **Swallowed Exception in Redis Counter**: In `increment_leads_collected_today`, if Redis fails or disconnects, the exception is caught and the function returns `0`. This breaks the daily limit guard, meaning the worker could scrape infinitely if Redis goes offline midway.
3.  **Hardcoded WhatsApp Prefix**: The frontend hardcodes the `91` India country code into WhatsApp deep links (`wa.me/91...`). If geographic priority expands globally, outreach links will break for non-Indian phone numbers.
4.  **Incomplete Pre-Flight Deduplication**: `is_duplicate_lead` strict-matches `phone_number` directly against the database text. It misses scenarios where formats differ slightly (e.g., missing spaces or standardizing prefixes), causing redundant audits.
5.  **JS Navigation Timing Vulnerability**: `site_auditor.py` extracts performance using `metrics = await page.evaluate(...) or {}`. If a site's framework aggressively rewrites performance timeline logs, `ttfb_ms` defaults to `0.0`, resulting in a false-positive healthy performance score.
