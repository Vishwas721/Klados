import { SearchHistoryItem } from "@/lib/types";
import { timeAgo, untilLabel } from "@/lib/format";

interface CoverageStripProps {
  items: SearchHistoryItem[];
  onPick: (niche: string, city: string) => void;
}

/** Recent scans as a ledger: what was covered, what it yielded, when it frees up. */
export function CoverageStrip({ items, onPick }: CoverageStripProps) {
  return (
    <div className="flex h-full flex-col rounded-2xl border border-line bg-card p-5 sm:p-6">
      <div className="flex items-baseline justify-between">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">Ledger · recent scans</p>
        <span className="text-[11px] text-faint">tap to rescan</span>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-muted">No scans yet. Your first one will be logged here.</p>
      ) : (
        <ul className="scroll-quiet mt-3 max-h-44 divide-y divide-line overflow-y-auto">
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => onPick(item.niche, item.city)}
                className="flex w-full items-baseline justify-between gap-3 py-2 text-left text-sm hover:text-signal"
              >
                <span className="min-w-0 truncate">
                  <span className="capitalize text-ink">{item.niche}</span>
                  <span className="text-muted"> · {item.city}</span>
                </span>
                <span className="flex shrink-0 items-baseline gap-3 text-xs text-muted">
                  <span className="tabular-nums">
                    <span className="text-ink">{item.leads_count}</span> saved
                  </span>
                  {item.status === "BLOCKED" ? (
                    <span className="text-bad">blocked</span>
                  ) : item.is_locked ? (
                    <span className="text-warn" suppressHydrationWarning>
                      rests {untilLabel(item.locked_until)}
                    </span>
                  ) : (
                    <span suppressHydrationWarning>{timeAgo(item.last_run_at)}</span>
                  )}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
