"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Lead, SearchHistoryItem, ScanTriggerResponse } from "@/lib/types";
import { fetchLeads, fetchSearchHistory, optOutLead, updateLeadStatus } from "@/lib/api";
import { useToast } from "@/lib/useToast";
import { MetricCards } from "@/components/MetricCards";
import { CoverageHistory } from "@/components/CoverageHistory";
import { FilterTabs, FilterTab } from "@/components/FilterTabs";
import { SearchInput } from "@/components/SearchInput";
import { LeadsTable } from "@/components/LeadsTable";
import { ScanTrigger } from "@/components/ScanTrigger";
import { ToastContainer } from "@/components/ToastContainer";

// How long to keep auto-polling after a scan is queued (ms)
const POLL_DURATION_MS = 5 * 60 * 1000; // 5 minutes
const POLL_INTERVAL_MS = 15_000;         // every 15 s

export default function DashboardPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [searchHistory, setSearchHistory] = useState<SearchHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<FilterTab>("ALL");
  const [search, setSearch] = useState("");

  // Controlled prefill for ScanTrigger
  const [prefillNiche, setPrefillNiche] = useState("");
  const [prefillCity, setPrefillCity] = useState("");

  // Polling machinery
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollDeadlineRef = useRef<number>(0);

  const { toasts, toast, dismiss } = useToast();

  // ── Data fetching ────────────────────────────────────────────────────────
  const loadLeads = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const fresh = await fetchLeads({ limit: 200 });
      setLeads(fresh);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load leads");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const hist = await fetchSearchHistory(30);
      setSearchHistory(hist);
    } catch {
      // Graceful fallback if backend is momentarily unreachable
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLeads();
    loadHistory();
  }, [loadLeads, loadHistory]);

  // ── Auto-refresh polling ─────────────────────────────────────────────────
  const startPolling = useCallback(() => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);

    pollDeadlineRef.current = Date.now() + POLL_DURATION_MS;

    pollTimerRef.current = setInterval(() => {
      if (Date.now() >= pollDeadlineRef.current) {
        clearInterval(pollTimerRef.current!);
        pollTimerRef.current = null;
        toast("Auto-refresh stopped. Scan window complete.", "info");
        return;
      }
      loadLeads(/* silent */ true);
      loadHistory();
    }, POLL_INTERVAL_MS);
  }, [loadLeads, loadHistory, toast]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, []);

  // ── Scan trigger callbacks ───────────────────────────────────────────────
  const handleScanQueued = useCallback(
    (result: ScanTriggerResponse, query: string, city: string) => {
      toast(
        `✅ Radar launched for "${query}" in "${city}" (${result.cells_queued} cell${result.cells_queued !== 1 ? "s" : ""} queued). Auto-refreshing…`,
        "success",
        6000
      );
      loadHistory();
      startPolling();
    },
    [toast, startPolling, loadHistory]
  );

  const handleScanError = useCallback(
    (message: string, isRateLimit?: boolean, niche?: string, city?: string) => {
      if (isRateLimit) {
        toast(
          `Daily limit reached for ${niche || "this niche"} in ${city || "this city"}. Check back tomorrow.`,
          "error",
          7000
        );
      } else {
        toast(`❌ Scan failed: ${message}`, "error", 6000);
      }
    },
    [toast]
  );

  // ── Lead action handlers ─────────────────────────────────────────────────
  const handleWhatsAppSent = useCallback(async (id: string) => {
    const updated = await updateLeadStatus(id, "CONTACTED_WHATSAPP");
    setLeads((prev) => prev.map((l) => (l.id === id ? updated : l)));
  }, []);

  const handleOptOut = useCallback(async (id: string) => {
    const updated = await optOutLead(id);
    setLeads((prev) => prev.map((l) => (l.id === id ? updated : l)));
  }, []);

  // ── Derived state ────────────────────────────────────────────────────────
  const counts = useMemo(
    () => ({
      ALL: leads.filter((l) => !l.opted_out).length,
      DIGITAL_GHOST: leads.filter((l) => l.category === "DIGITAL_GHOST" && !l.opted_out).length,
      DIGITAL_DINOSAUR: leads.filter((l) => l.category === "DIGITAL_DINOSAUR" && !l.opted_out).length,
      LAGGY_UX: leads.filter((l) => l.category === "LAGGY_UX" && !l.opted_out).length,
      AUTOMATION_CANDIDATE: leads.filter((l) => l.category === "AUTOMATION_CANDIDATE" && !l.opted_out).length,
      OPTED_OUT: leads.filter((l) => l.opted_out).length,
    }),
    [leads]
  );

  const filteredLeads = useMemo(() => {
    const q = search.trim().toLowerCase();
    return leads.filter((lead) => {
      if (activeTab === "OPTED_OUT") {
        if (!lead.opted_out) return false;
      } else {
        if (lead.opted_out) return false;
        if (activeTab !== "ALL" && lead.category !== activeTab) return false;
      }
      if (!q) return true;
      return (
        lead.business_name.toLowerCase().includes(q) ||
        lead.phone_number.includes(q)
      );
    });
  }, [leads, activeTab, search]);

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Lead Radar</h1>
          <p className="mt-1 text-sm text-gray-500">
            Autonomous SMB discovery, audit, &amp; outreach dashboard
          </p>
        </div>
        <button
          type="button"
          suppressHydrationWarning
          onClick={() => {
            loadLeads();
            loadHistory();
          }}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50 shadow-xs"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* ── Scan Trigger form ─────────────────────────────────────────────── */}
      <div className="mt-5">
        <ScanTrigger
          onScanQueued={handleScanQueued}
          onError={handleScanError}
          prefillQuery={prefillNiche}
          prefillCity={prefillCity}
        />
      </div>

      {/* ── Metric cards ─────────────────────────────────────────────────── */}
      <div className="mt-6">
        <MetricCards leads={leads.filter((l) => !l.opted_out)} />
      </div>

      {/* ── Coverage / Daily Lock History ─────────────────────────────────── */}
      <div className="mt-6">
        <CoverageHistory
          items={searchHistory}
          loading={historyLoading}
          onSelectNicheCity={(niche, city) => {
            setPrefillNiche(niche);
            setPrefillCity(city);
          }}
        />
      </div>

      {/* ── Filter tabs + local search ────────────────────────────────────── */}
      <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <FilterTabs active={activeTab} onChange={setActiveTab} counts={counts} />
        <SearchInput value={search} onChange={setSearch} />
      </div>

      {/* Error banner */}
      {error && (
        <div className="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          {error} — is the API running at http://localhost:8000?
        </div>
      )}

      {/* Leads table */}
      <div className="mt-4">
        {loading ? (
          <div className="rounded-xl border border-gray-200 bg-white py-16 text-center text-sm text-gray-400">
            Loading leads…
          </div>
        ) : (
          <LeadsTable
            leads={filteredLeads}
            onWhatsAppSent={handleWhatsAppSent}
            onOptOut={handleOptOut}
          />
        )}
      </div>

      {/* Toast notifications (fixed bottom-right) */}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </main>
  );
}
