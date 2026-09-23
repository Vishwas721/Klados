"use client";

import { useState, useRef } from "react";
import { Radar, Loader2, MapPin, Search } from "lucide-react";
import { triggerScan } from "@/lib/api";
import { ScanTriggerResponse } from "@/lib/types";

interface ScanTriggerProps {
  onScanQueued: (result: ScanTriggerResponse) => void;
  onError: (message: string) => void;
}

export function ScanTrigger({ onScanQueued, onError }: ScanTriggerProps) {
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("");
  const [loading, setLoading] = useState(false);
  const queryRef = useRef<HTMLInputElement>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const q = query.trim();
    const c = city.trim();
    if (!q) {
      queryRef.current?.focus();
      return;
    }
    const resolvedCity = c || "Bengaluru";

    setLoading(true);
    try {
      const result = await triggerScan(q, resolvedCity, 2);
      onScanQueued(result);
      // Keep values so the user can run a variation without retyping
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to trigger scan");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3 rounded-2xl border border-indigo-100 bg-gradient-to-br from-indigo-50 to-white p-4 shadow-sm sm:flex-row sm:items-end"
    >
      {/* Header label — visible only on larger screens inline */}
      <div className="flex items-center gap-2 sm:hidden">
        <Radar className="h-4 w-4 text-indigo-600" />
        <span className="text-sm font-semibold text-indigo-700">Run Radar Scan</span>
      </div>

      {/* Niche / query input */}
      <div className="flex-1">
        <label
          htmlFor="scan-query"
          className="mb-1 block text-xs font-medium text-gray-500 uppercase tracking-wide"
        >
          Niche
        </label>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            ref={queryRef}
            id="scan-query"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. dental clinic"
            disabled={loading}
            className="w-full rounded-xl border border-gray-200 bg-white py-2 pl-9 pr-3 text-sm placeholder-gray-400 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:opacity-50"
          />
        </div>
      </div>

      {/* City input */}
      <div className="flex-1 sm:max-w-[200px]">
        <label
          htmlFor="scan-city"
          className="mb-1 block text-xs font-medium text-gray-500 uppercase tracking-wide"
        >
          City / Zone
        </label>
        <div className="relative">
          <MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            id="scan-city"
            type="text"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder="Bengaluru (default)"
            disabled={loading}
            className="w-full rounded-xl border border-gray-200 bg-white py-2 pl-9 pr-3 text-sm placeholder-gray-400 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:opacity-50"
          />
        </div>
      </div>

      {/* Submit button */}
      <button
        type="submit"
        disabled={loading || !query.trim()}
        className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:cursor-not-allowed disabled:opacity-50 sm:self-end"
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Radar className="h-4 w-4" />
        )}
        {loading ? "Queueing…" : "Run Radar"}
      </button>
    </form>
  );
}
