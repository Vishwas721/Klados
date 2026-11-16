"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, Dices, Loader2 } from "lucide-react";
import { ApiError, fetchExhaustedCampaigns, fetchScanTargets, triggerScan } from "@/lib/api";
import { ExhaustedCampaign, ScanTargets, ScanTriggerResponse } from "@/lib/types";

interface ScanSentenceProps {
  onScanQueued: (result: ScanTriggerResponse, query: string, city: string) => void;
  onError: (message: string, isRateLimit?: boolean) => void;
  prefill: { niche: string; city: string; nonce: number };
  refreshKey: number;
}

const DEFAULT_CITY = "Bengaluru";

function sameCombo(a: { city: string; niche: string }, city: string, niche: string): boolean {
  return a.city.toLowerCase() === city.toLowerCase() && a.niche.toLowerCase() === niche.toLowerCase();
}

/** "Find [dentists] in [Bengaluru] →": the scan form, written as a sentence. */
export function ScanSentence({ onScanQueued, onError, prefill, refreshKey }: ScanSentenceProps) {
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("");
  const [loading, setLoading] = useState(false);
  const [targets, setTargets] = useState<ScanTargets>({ cities: [], niches: [] });
  const [exhausted, setExhausted] = useState<ExhaustedCampaign[]>([]);
  const queryRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchScanTargets().then(setTargets).catch(() => {});
  }, []);

  useEffect(() => {
    fetchExhaustedCampaigns().then(setExhausted).catch(() => {});
  }, [refreshKey]);

  useEffect(() => {
    if (!prefill.nonce) return;
    setQuery(prefill.niche);
    setCity(prefill.city);
    queryRef.current?.focus();
  }, [prefill]);

  const resolvedCity = city.trim() || DEFAULT_CITY;
  const isExhausted = useMemo(
    () => exhausted.some((e) => sameCombo(e, resolvedCity, query.trim())),
    [exhausted, resolvedCity, query]
  );

  const surprise = () => {
    const { cities, niches } = targets;
    if (!cities.length || !niches.length) return;
    for (let attempt = 0; attempt < 25; attempt++) {
      const c = cities[Math.floor(Math.random() * cities.length)];
      const n = niches[Math.floor(Math.random() * niches.length)];
      if (!exhausted.some((e) => sameCombo(e, c, n)) || attempt === 24) {
        setQuery(n);
        setCity(c);
        return;
      }
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    if (!q) {
      queryRef.current?.focus();
      return;
    }
    setLoading(true);
    try {
      onScanQueued(await triggerScan(q, resolvedCity, 6), q, resolvedCity);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to trigger scan", err instanceof ApiError && err.status === 429);
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    "min-w-0 border-b-2 border-line bg-transparent px-1 font-serif italic text-ink outline-none transition placeholder:text-faint focus:border-signal";

  return (
    <form onSubmit={submit} className="rounded-2xl border border-line bg-card p-5 sm:p-6">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">New scan · Google Maps</p>
      <div className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-3 text-2xl sm:text-3xl">
        <span className="font-serif">Find</span>
        <input
          ref={queryRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          list="scan-niches"
          placeholder="dental clinics"
          disabled={loading}
          aria-label="Niche"
          className={`${inputClass} w-[11ch] sm:w-[14ch]`}
        />
        <span className="font-serif">in</span>
        <input
          value={city}
          onChange={(e) => setCity(e.target.value)}
          list="scan-cities"
          placeholder={DEFAULT_CITY}
          disabled={loading}
          aria-label="City"
          className={`${inputClass} w-[9ch] sm:w-[11ch]`}
        />
        <span className="flex items-center gap-2 text-base">
          <button
            type="submit"
            disabled={loading || !query.trim() || isExhausted}
            className="inline-flex items-center gap-1.5 rounded-full bg-signal px-4 py-2 text-sm font-semibold text-signal-ink transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
            {loading ? "Queueing" : "Scan"}
          </button>
          <button
            type="button"
            onClick={surprise}
            disabled={loading || !targets.cities.length}
            title="Pick a random niche and city"
            className="grid h-9 w-9 place-items-center rounded-full border border-line text-muted transition hover:border-ink hover:text-ink disabled:opacity-40"
          >
            <Dices className="h-4 w-4" />
          </button>
        </span>
      </div>
      <datalist id="scan-niches">
        {targets.niches.map((n) => (
          <option key={n} value={n} />
        ))}
      </datalist>
      <datalist id="scan-cities">
        {targets.cities.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>
      <p className={`mt-3 text-xs ${isExhausted ? "text-bad" : "text-faint"}`}>
        {isExhausted
          ? "Every area of this city has been scanned for this niche. Try another pair."
          : "Covers the next 6 unscanned map cells, centre outwards. Each pair rests 24 h after a scan."}
      </p>
    </form>
  );
}
