const TTFB_THRESHOLD_MS = 1800;
const DOM_LOAD_THRESHOLD_MS = 4500;

function speedTone(value: number, threshold: number): string {
  if (!value || value <= 0) return "bg-gray-100 text-gray-400";
  if (value <= threshold * 0.6) return "bg-emerald-100 text-emerald-700";
  if (value <= threshold) return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

interface PerformanceBadgesProps {
  ttfbMs: number;
  domLoadMs: number;
}

export function PerformanceBadges({ ttfbMs, domLoadMs }: PerformanceBadgesProps) {
  return (
    <div className="flex flex-col gap-1">
      <span
        className={`inline-flex w-fit items-center rounded px-1.5 py-0.5 text-xs font-medium ${speedTone(
          ttfbMs,
          TTFB_THRESHOLD_MS
        )}`}
      >
        TTFB {ttfbMs > 0 ? `${Math.round(ttfbMs)}ms` : "—"}
      </span>
      <span
        className={`inline-flex w-fit items-center rounded px-1.5 py-0.5 text-xs font-medium ${speedTone(
          domLoadMs,
          DOM_LOAD_THRESHOLD_MS
        )}`}
      >
        Load {domLoadMs > 0 ? `${Math.round(domLoadMs)}ms` : "—"}
      </span>
    </div>
  );
}
