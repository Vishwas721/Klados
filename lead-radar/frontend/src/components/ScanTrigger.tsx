"use client";

import { useState, useRef, useEffect } from "react";
import { Radar, Loader2, MapPin, Search, Dices } from "lucide-react";
import { triggerScan, ApiError } from "@/lib/api";
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

  useEffect(() => {
    if (prefillQuery) setQuery(prefillQuery);
    if (prefillCity) setCity(prefillCity);
    if (prefillQuery || prefillCity) {
      queryRef.current?.focus();
    }
  }, [prefillQuery, prefillCity]);

  const handleSurpriseMe = () => {
    const randomNiche = RANDOM_NICHES[Math.floor(Math.random() * RANDOM_NICHES.length)];
    const randomCity = RANDOM_CITIES[Math.floor(Math.random() * RANDOM_CITIES.length)];
    setQuery(randomNiche);
    setCity(randomCity);
  };

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
        disabled={loading || !query.trim()}
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
  );
}
