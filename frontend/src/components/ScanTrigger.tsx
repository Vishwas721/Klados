"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { Radar, Loader2, MapPin, Search, Dices, AlertTriangle } from "lucide-react";
import { triggerScan, ApiError, fetchExhaustedCampaigns } from "@/lib/api";
import { ScanTriggerResponse } from "@/lib/types";

interface ScanTriggerProps {
  onScanQueued: (result: ScanTriggerResponse, query: string, city: string) => void;
  onError: (message: string, isRateLimit?: boolean, niche?: string, city?: string) => void;
  prefillQuery?: string;
  prefillCity?: string;
}

const RANDOM_NICHES = [
  "Gyms & Fitness Centers",
  "Dental Clinics",
  "Unisex Salons & Spas",
  "Interior Designers",
  "Car Detailing & Wash",
  "Boutique Specialty Cafes",
  "Plumbing & Sanitaryware",
  "Multi-brand Auto Mechanics",
  "Modular Kitchen Designers",
  "Physiotherapy Clinics",
  "Pet Care & Veterinary",
  "Wedding Photographers",
  "Diagnostic Laboratories",
  "Architects & Civil Engineers",
  "Ayurvedic Wellness Centers",
];

const RANDOM_CITIES = [
  "Bengaluru",
  "Mysuru",
  "Mangaluru",
  "Hubballi",
  "Belagavi",
  "Mumbai",
  "Pune",
  "Hyderabad",
  "Chennai",
  "Delhi",
];

export function ScanTrigger({
  onScanQueued,
  onError,
  prefillQuery = "",
  prefillCity = "",
}: ScanTriggerProps) {
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("");
  const [loading, setLoading] = useState(false);
  const queryRef = useRef<HTMLInputElement>(null);

  const [exhaustedCombos, setExhaustedCombos] = useState<{city: string, niche: string, last_scraped_at: string}[]>([]);

  useEffect(() => {
    fetchExhaustedCampaigns().then(setExhaustedCombos).catch(console.error);
  }, []);

  useEffect(() => {
    if (prefillQuery) setQuery(prefillQuery);
    if (prefillCity) setCity(prefillCity);
    if (prefillQuery || prefillCity) {
      queryRef.current?.focus();
    }
  }, [prefillQuery, prefillCity]);

  const handleSurpriseMe = () => {
    let availableCombos = [];
    for (const c of RANDOM_CITIES) {
      for (const n of RANDOM_NICHES) {
        if (!exhaustedCombos.some(e => e.city.toLowerCase() === c.toLowerCase() && e.niche.toLowerCase() === n.toLowerCase())) {
          availableCombos.push({ city: c, niche: n });
        }
      }
    }
    
    if (availableCombos.length > 0) {
      const choice = availableCombos[Math.floor(Math.random() * availableCombos.length)];
      setQuery(choice.niche);
      setCity(choice.city);
    } else {
      const randomNiche = RANDOM_NICHES[Math.floor(Math.random() * RANDOM_NICHES.length)];
      const randomCity = RANDOM_CITIES[Math.floor(Math.random() * RANDOM_CITIES.length)];
      setQuery(randomNiche);
      setCity(randomCity);
    }
  };

  const resolvedCity = city.trim() || "Bengaluru";
  
  const isExhausted = useMemo(() => {
    return exhaustedCombos.some(e => e.city.toLowerCase() === resolvedCity.toLowerCase() && e.niche.toLowerCase() === query.trim().toLowerCase());
  }, [exhaustedCombos, resolvedCity, query]);

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
      if (err instanceof ApiError && err.status === 429) {
        // Daily execution lock hit
        onError(
          `Daily limit reached for "${q}" in "${resolvedCity}". Check back tomorrow.`,
          true,
          q,
          resolvedCity
        );
      } else {
        onError(err instanceof Error ? err.message : "Failed to trigger scan", false, q, resolvedCity);
      }
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
            disabled={loading}
            className="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 shadow-xs"
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
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Dental Clinics, Gyms, Salons"
              disabled={loading}
              className="w-full rounded-xl border border-gray-200 bg-white py-2 pl-9 pr-3 text-sm placeholder-gray-400 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:opacity-50"
            />
          </div>
        </div>

        {/* City input */}
        <div className="flex-1 sm:max-w-[200px]">
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
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="Bengaluru (default)"
              disabled={loading}
              className="w-full rounded-xl border border-gray-200 bg-white py-2 pl-9 pr-3 text-sm placeholder-gray-400 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:opacity-50"
            />
          </div>
        </div>

        {/* Surprise Me button on desktop */}
        <button
          type="button"
          onClick={handleSurpriseMe}
          disabled={loading}
          title="Fill with a random niche &amp; city combination"
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
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Radar className="h-4 w-4" />
          )}
          {loading ? "Queueing…" : "Run Radar"}
        </button>
      </form>

      {isExhausted && (
        <div className="text-sm text-red-600 flex items-center gap-2 px-2">
          <AlertTriangle className="h-4 w-4" />
          <span>This combination has been fully scraped. Please try a different city or niche.</span>
        </div>
      )}

      {exhaustedCombos.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
            <MapPin className="h-4 w-4 text-gray-400" />
            Fully Scraped Combos
          </h3>
          <div className="flex flex-wrap gap-2">
            {exhaustedCombos.map((combo, idx) => (
              <span key={idx} className="inline-flex items-center rounded-md bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                {combo.city}: {combo.niche}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
