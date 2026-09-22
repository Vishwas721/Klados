"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Lead } from "@/lib/types";
import { fetchLeads, optOutLead, updateLeadStatus } from "@/lib/api";
import { MetricCards } from "@/components/MetricCards";
import { FilterTabs, FilterTab } from "@/components/FilterTabs";
import { SearchInput } from "@/components/SearchInput";
import { LeadsTable } from "@/components/LeadsTable";

export default function DashboardPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<FilterTab>("ALL");
  const [search, setSearch] = useState("");

  const loadLeads = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setLeads(await fetchLeads({ limit: 200 }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load leads");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLeads();
  }, [loadLeads]);

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
    const query = search.trim().toLowerCase();
    return leads.filter((lead) => {
      if (activeTab === "OPTED_OUT") {
        if (!lead.opted_out) return false;
      } else {
        if (lead.opted_out) return false;
        if (activeTab !== "ALL" && lead.category !== activeTab) return false;
      }
      if (!query) return true;
      return (
        lead.business_name.toLowerCase().includes(query) || lead.phone_number.includes(query)
      );
    });
  }, [leads, activeTab, search]);

  const handleWhatsAppSent = useCallback(async (id: string) => {
    const updated = await updateLeadStatus(id, "CONTACTED_WHATSAPP");
    setLeads((prev) => prev.map((l) => (l.id === id ? updated : l)));
  }, []);

  const handleOptOut = useCallback(async (id: string) => {
    const updated = await optOutLead(id);
    setLeads((prev) => prev.map((l) => (l.id === id ? updated : l)));
  }, []);

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Lead Radar</h1>
          <p className="mt-1 text-sm text-gray-500">Daily outreach dashboard for audited leads</p>
        </div>
        <button
          type="button"
          onClick={loadLeads}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      <div className="mt-6">
        <MetricCards leads={leads.filter((l) => !l.opted_out)} />
      </div>

      <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <FilterTabs active={activeTab} onChange={setActiveTab} counts={counts} />
        <SearchInput value={search} onChange={setSearch} />
      </div>

      {error && (
        <div className="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          {error} — is the API running at http://localhost:8000?
        </div>
      )}

      <div className="mt-4">
        {loading ? (
          <div className="rounded-xl border border-gray-200 bg-white py-16 text-center text-sm text-gray-400">
            Loading leads...
          </div>
        ) : (
          <LeadsTable leads={filteredLeads} onWhatsAppSent={handleWhatsAppSent} onOptOut={handleOptOut} />
        )}
      </div>
    </main>
  );
}
