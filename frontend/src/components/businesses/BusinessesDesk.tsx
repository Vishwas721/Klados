"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Search } from "lucide-react";
import { Lead, LeadCategory, LeadStats, ScanTriggerResponse, SearchHistoryItem } from "@/lib/types";
import { fetchLeads, fetchSearchHistory, optOutLead, updateLeadStatus } from "@/lib/api";
import { CATEGORY_META, CATEGORY_ORDER } from "@/lib/categories";
import { ToastVariant } from "@/lib/useToast";
import { ScanSentence } from "./ScanSentence";
import { CoverageStrip } from "./CoverageStrip";
import { BusinessCard } from "./BusinessCard";

const POLL_DURATION_MS = 5 * 60 * 1000;
const POLL_INTERVAL_MS = 15_000;
const PER_COLUMN = 60;

interface BusinessesDeskProps {
  stats: LeadStats | null;
  refreshKey: number;
  onChanged: () => void;
  toast: (message: string, variant?: ToastVariant, durationMs?: number) => void;
}

export function BusinessesDesk({ stats, refreshKey, onChanged, toast }: BusinessesDeskProps) {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [showOptedOut, setShowOptedOut] = useState(false);
  const [hideContacted, setHideContacted] = useState(false);
  const [expanded, setExpanded] = useState<Partial<Record<LeadCategory, boolean>>>({});
  const [prefill, setPrefill] = useState({ niche: "", city: "", nonce: 0 });
  const [scanTick, setScanTick] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [fresh, hist] = await Promise.all([fetchLeads({ limit: 1000 }), fetchSearchHistory(30)]);
      setLeads(fresh);
      setHistory(hist);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load businesses");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (refreshKey) load(true);
  }, [refreshKey, load]);

  useEffect(
    () => () => {
      if (pollRef.current) clearInterval(pollRef.current);
    },
    []
  );

  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    const deadline = Date.now() + POLL_DURATION_MS;
    pollRef.current = setInterval(() => {
      if (Date.now() >= deadline) {
        clearInterval(pollRef.current!);
        pollRef.current = null;
        return;
      }
      load(true);
      onChanged();
      setScanTick((t) => t + 1);
    }, POLL_INTERVAL_MS);
  }, [load, onChanged]);

  const onScanQueued = useCallback(
    (result: ScanTriggerResponse, q: string, city: string) => {
      toast(
        `Scanning “${q}” in ${city}: ${result.cells_queued} cells queued, ${result.cells_remaining.toLocaleString()} left. New businesses appear here as they're audited.`,
        "success",
        6000
      );
      load(true);
      startPolling();
    },
    [toast, load, startPolling]
  );

  const onScanError = useCallback(
    (message: string, isRateLimit?: boolean) => toast(isRateLimit ? message : `Scan failed: ${message}`, "error", 8000),
    [toast]
  );

  const onWhatsAppSent = useCallback(async (id: string) => {
    const updated = await updateLeadStatus(id, "CONTACTED_WHATSAPP");
    setLeads((prev) => prev.map((l) => (l.id === id ? updated : l)));
  }, []);

  const onOptOut = useCallback(
    async (id: string) => {
      const updated = await optOutLead(id);
      setLeads((prev) => prev.map((l) => (l.id === id ? updated : l)));
      onChanged();
    },
    [onChanged]
  );

  const columns = useMemo(() => {
    const q = query.trim().toLowerCase();
    const shown = leads.filter(
      (l) =>
        (showOptedOut ? l.opted_out : !l.opted_out) &&
        (!hideContacted || l.status === "AUDITED" || l.status === "PENDING") &&
        (!q || l.business_name.toLowerCase().includes(q) || l.phone_number.includes(q) || l.city.toLowerCase().includes(q))
    );
    return CATEGORY_ORDER.map((cat) => ({ cat, items: shown.filter((l) => l.category === cat) }));
  }, [leads, query, showOptedOut, hideContacted]);

  return (
    <section className="mt-8">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <ScanSentence onScanQueued={onScanQueued} onError={onScanError} prefill={prefill} refreshKey={scanTick} />
        <CoverageStrip
          items={history}
          onPick={(niche, city) => setPrefill((p) => ({ niche, city, nonce: p.nonce + 1 }))}
        />
      </div>

      {/* Board toolbar */}
      <div className="mt-8 flex flex-col gap-3 border-b border-line pb-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="font-serif text-2xl italic">
          The board{" "}
          <span className="font-sans text-sm not-italic text-muted">
            sorted by what each business needs most
            {stats?.opted_out ? ` · ${stats.opted_out} opted out` : ""}
          </span>
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <label className="relative flex-1 sm:w-56 sm:flex-none">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Name, phone, city"
              className="h-8 w-full rounded-full border border-line bg-card pl-8 pr-3 text-sm outline-none placeholder:text-faint focus:border-ink"
            />
          </label>
          <button
            type="button"
            onClick={() => setHideContacted((v) => !v)}
            aria-pressed={hideContacted}
            className={`h-8 rounded-full border px-3 text-xs transition ${
              hideContacted ? "border-ink bg-ink text-paper" : "border-line text-muted hover:text-ink"
            }`}
          >
            Not yet pitched
          </button>
          <button
            type="button"
            onClick={() => setShowOptedOut((v) => !v)}
            aria-pressed={showOptedOut}
            className={`h-8 rounded-full border px-3 text-xs transition ${
              showOptedOut ? "border-ink bg-ink text-paper" : "border-line text-muted hover:text-ink"
            }`}
          >
            Opted out
          </button>
        </div>
      </div>

      {error && (
        <p className="mt-4 rounded-xl border border-bad/40 px-4 py-3 text-sm text-bad">{error}. Is the API running?</p>
      )}

      <div className="mt-5 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        {columns.map(({ cat, items }) => {
          const meta = CATEGORY_META[cat];
          const total = showOptedOut ? items.length : stats?.by_category[cat] ?? items.length;
          const limit = expanded[cat] ? items.length : PER_COLUMN;
          return (
            <div key={cat} className="min-w-0">
              <header className="mb-3 border-t-[3px] pt-3" style={{ borderColor: meta.tone }}>
                <div className="flex items-baseline justify-between">
                  <h3 className="font-serif text-xl">{meta.label}</h3>
                  <span className="font-mono text-xs text-muted">{total.toLocaleString()}</span>
                </div>
                <p className="mt-0.5 text-xs text-muted">
                  {meta.problem} → <span className="text-ink">{meta.pitch}</span>
                </p>
              </header>
              {loading ? (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="h-24 animate-pulse rounded-xl bg-sunk" />
                  ))}
                </div>
              ) : items.length === 0 ? (
                <p className="rounded-xl border border-dashed border-line px-3 py-6 text-center text-xs text-faint">
                  Nothing here{query ? " for that search" : " yet"}.
                </p>
              ) : (
                <div className="scroll-quiet max-h-[72vh] space-y-2 overflow-y-auto pr-1">
                  {items.slice(0, limit).map((lead) => (
                    <BusinessCard key={lead.id} lead={lead} onWhatsAppSent={onWhatsAppSent} onOptOut={onOptOut} />
                  ))}
                  {items.length > limit && (
                    <button
                      type="button"
                      onClick={() => setExpanded((e) => ({ ...e, [cat]: true }))}
                      className="w-full rounded-xl border border-dashed border-line py-2 text-xs text-muted hover:text-ink"
                    >
                      Show {items.length - limit} more
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
