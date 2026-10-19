"use client";

import { useMemo } from "react";
import { Lock, Unlock, Compass, Clock, CheckCircle2, ArrowUpRight } from "lucide-react";
import { SearchHistoryItem } from "@/lib/types";

interface CoverageHistoryProps {
  items: SearchHistoryItem[];
  loading?: boolean;
  onSelectNicheCity?: (niche: string, city: string) => void;
}

function formatTimeAgo(isoString: string): string {
  try {
    const diff = (Date.now() - new Date(isoString).getTime()) / 1000;
    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  } catch {
    return isoString;
  }
}

function formatLockRemaining(lockedUntilIso: string): string {
  try {
    const diffMs = new Date(lockedUntilIso).getTime() - Date.now();
    if (diffMs <= 0) return "unlocking soon";
    const hours = Math.floor(diffMs / (1000 * 60 * 60));
    const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
    if (hours > 0) return `${hours}h ${mins}m left`;
    return `${mins}m left`;
  } catch {
    return "locked";
  }
}

export function CoverageHistory({
  items,
  loading = false,
  onSelectNicheCity,
}: CoverageHistoryProps) {
  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      // Prioritize locked ones or most recent
      return new Date(b.last_run_at).getTime() - new Date(a.last_run_at).getTime();
    });
  }, [items]);

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <span className="rounded-lg bg-indigo-50 p-1.5 text-indigo-600">
            <Compass className="h-4 w-4" />
          </span>
          <h2 className="text-base font-semibold text-gray-900">Coverage &amp; Daily Locks</h2>
          <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
            {items.length} Tracked
          </span>
        </div>
        <p className="text-xs text-gray-500">
          Combos enter a 24-hour safe lock after scanning to protect IP reputation
        </p>
      </div>

      {loading && items.length === 0 ? (
        <div className="mt-4 flex items-center justify-center py-8 text-sm text-gray-400">
          Loading coverage history...
        </div>
      ) : sortedItems.length === 0 ? (
        <div className="mt-4 rounded-xl border border-dashed border-gray-200 p-6 text-center text-sm text-gray-500">
          No region scans recorded yet. Run a radar scan to track daily coverage!
        </div>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {sortedItems.map((item) => {
            const isLocked = item.is_locked;
            return (
              <div
                key={item.id}
                className={`relative flex flex-col justify-between rounded-xl border p-3.5 transition-all ${
                  isLocked
                    ? "border-amber-200 bg-gradient-to-br from-amber-50/60 to-white"
                    : "border-gray-200 bg-gradient-to-br from-gray-50/50 to-white hover:border-gray-300"
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="text-sm font-semibold capitalize text-gray-900">
                        {item.niche}
                      </h3>
                      <p className="text-xs font-medium text-gray-500">{item.city}</p>
                    </div>

                    {isLocked ? (
                      <span className="inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
                        <Lock className="h-3 w-3" />
                        {formatLockRemaining(item.locked_until)}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                        <Unlock className="h-3 w-3" />
                        Ready
                      </span>
                    )}
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between border-t border-gray-100 pt-2.5 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="h-3.5 w-3.5 text-indigo-500" />
                    <strong>{item.leads_count}</strong> leads saved
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="flex items-center gap-1 text-gray-400">
                      <Clock className="h-3 w-3" />
                      {formatTimeAgo(item.last_run_at)}
                    </span>

                    {onSelectNicheCity && (
                      <button
                        type="button"
                        onClick={() => onSelectNicheCity(item.niche, item.city)}
                        title="Use this niche and city in search"
                        className="inline-flex items-center gap-0.5 font-medium text-indigo-600 hover:text-indigo-800"
                      >
                        Pick
                        <ArrowUpRight className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
