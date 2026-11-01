"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { Radar, Loader2, MapPin, Search, Dices, AlertTriangle } from "lucide-react";
import { triggerScan, ApiError, fetchExhaustedCampaigns, fetchScanTargets } from "@/lib/api";
import { ExhaustedCampaign, ScanTargets, ScanTriggerResponse } from "@/lib/types";

interface ScanTriggerProps {
  onScanQueued: (result: ScanTriggerResponse, query: string, city: string) => void;
  onError: (message: string, isRateLimit?: boolean) => void;
  prefillQuery?: string;
  prefillCity?: string;
  /** Bump to re-fetch the exhausted-combo list (e.g. while a scan is running). */
  refreshKey?: number;
}

const DEFAULT_CITY = "Bengaluru";

function sameCombo(a: { city: string; niche: string }, city: string, niche: string): boolean {
  return a.city.toLowerCase() === city.toLowerCase() && a.niche.toLowerCase() === niche.toLowerCase();
}

export function ScanTrigger({
  onScanQueued,
  onError,
  prefillQuery = "",
  prefillCity = "",
  refreshKey = 0,
}: ScanTriggerProps) {
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("");
  const [loading, setLoading] = useState(false);
  const queryRef = useRef<HTMLInputElement>(null);

  const [targets, setTargets] = useState<ScanTargets>({ cities: [], niches: [] });
  const [exhaustedCombos, setExhaustedCombos] = useState<ExhaustedCampaign[]>([]);

  useEffect(() => {
    fetchScanTargets().then(setTargets).catch(console.error);
  }, []);

  useEffect(() => {
    fetchExhaustedCampaigns().then(setExhaustedCombos).catch(console.error);
  }, [refreshKey]);

  useEffect(() => {
    if (prefillQuery) setQuery(prefillQuery);
    if (prefillCity) setCity(prefillCity);
    if (prefillQuery || prefillCity) {
      queryRef.current?.focus();
    }
  }, [prefillQuery, prefillCity]);

  const handleSurpriseMe = () => {
    const { cities, niches } = targets;
    if (!cities.length || !niches.length) return;

    // Random sampling beats enumerating all ~2,000 combos; retry a few times
    // to dodge exhausted ones.
    for (let attempt = 0; attempt < 25; attempt++) {
      const c = cities[Math.floor(Math.random() * cities.length)];
      const n = niches[Math.floor(Math.random() * niches.length)];
      if (!exhaustedCombos.some((e) => sameCombo(e, c, n)) || attempt === 24) {
        setQuery(n);
        setCity(c);
        return;
      }
    }
  };

  const resolvedCity = city.trim() || DEFAULT_CITY;

  const isExhausted = useMemo(
    () => exhaustedCombos.some((e) => sameCombo(e, resolvedCity, query.trim())),
    [exhaustedCombos, resolvedCity, query]
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const q = query.trim();
    if (!q) {
      queryRef.current?.focus();
      return;
    }

    setLoading(true);
    try {
      // Safe IP limits: capped to max 6 H3 cells
      const result = await triggerScan(q, resolvedCity, 6);
      onScanQueued(result, q, resolvedCity);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to trigger scan";
      onError(message, err instanceof ApiError && err.status === 429);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-3 rounded-2xl border border-indigo-100 bg-gradient-to-br from-indigo-50/70 via-white to-indigo-50/30 p-4 shadow-sm sm:flex-row sm:items-end"
      >
        {/* Header label for mobile */}
        <div className="flex items-center justify-between sm:hidden">
          <div className="flex items-center gap-2">
            <Radar className="h-4 w-4 text-indigo-600" />
            <span className="text-sm font-semibold text-indigo-700">Run Radar Scan</span>
          </div>
          <button
            type="button"
            onClick={handleSurpriseMe}
            disabled={loading || !targets.cities.length}
            className="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 shadow-xs disabled:opacity-50"
          >
            <Dices className="h-3.5 w-3.5 text-indigo-600" />
            Surprise Me
          </button>
        </div>

        {/* Niche / query input */}
        <div className="flex-1">
          <div className="mb-1 flex items-center justify-between">
            <label
              htmlFor="scan-query"
              className="block text-xs font-semibold uppercase tracking-wider text-gray-500"
            >
              Niche / Industry
            </label>
          </div>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              ref={queryRef}
              id="scan-query"
              type="text"
              list="scan-niche-options"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Dental Clinics, Gyms, Salons"
              disabled={loading}
              className="w-full rounded-xl border border-gray-200 bg-white py-2 pl-9 pr-3 text-sm placeholder-gray-400 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:opacity-50"
            />
            <datalist id="scan-niche-options">
              {targets.niches.map((n) => (
                <option key={n} value={n} />
              ))}
            </datalist>
          </div>
        </div>

        {/* City input */}
        <div className="flex-1 sm:max-w-[220px]">
          <label
            htmlFor="scan-city"
            className="mb-1 block text-xs font-semibold uppercase tracking-wider text-gray-500"
          >
            Target City
          </label>
          <div className="relative">
            <MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              id="scan-city"
              type="text"
              list="scan-city-options"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder={`${DEFAULT_CITY} (default)`}
              disabled={loading}
              className="w-full rounded-xl border border-gray-200 bg-white py-2 pl-9 pr-3 text-sm placeholder-gray-400 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:opacity-50"
            />
            <datalist id="scan-city-options">
              {targets.cities.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </div>
        </div>

        {/* Surprise Me button on desktop */}
        <button
          type="button"
          onClick={handleSurpriseMe}
          disabled={loading || !targets.cities.length}
          title="Fill with a random niche & city combination"
          className="hidden sm:inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3.5 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 hover:text-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:opacity-50"
        >
          <Dices className="h-4 w-4 text-indigo-600" />
          <span>Surprise Me</span>
        </button>

        {/* Primary Submit button */}
        <button
          type="submit"
          disabled={loading || !query.trim() || isExhausted}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition-all hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:cursor-not-allowed disabled:opacity-50 sm:self-end"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radar className="h-4 w-4" />}
          {loading ? "Queueing…" : "Run Radar"}
        </button>
      </form>

      {isExhausted && (
        <div className="text-sm text-red-600 flex items-center gap-2 px-2">
          <AlertTriangle className="h-4 w-4" />
          <span>Every area of this city has been scanned for this niche. Try a different city or niche.</span>
        </div>
      )}

      {exhaustedCombos.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
            <MapPin className="h-4 w-4 text-gray-400" />
            Fully Scraped Combos
          </h3>
          <div className="flex flex-wrap gap-2">
            {exhaustedCombos.map((combo) => (
              <span
                key={`${combo.city}:${combo.niche}`}
                className="inline-flex items-center rounded-md bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600"
              >
                {combo.city}: {combo.niche}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
