export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (Number.isNaN(diff)) return "—";
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function untilLabel(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return "now";
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export function everyLabel(seconds: number): string {
  if (seconds < 3600) return `every ${Math.round(seconds / 60)} min`;
  const h = seconds / 3600;
  return `every ${Number.isInteger(h) ? h : h.toFixed(1)} h`;
}

const CURRENCY_SIGN: Record<string, string> = { USD: "$", INR: "₹", EUR: "€", GBP: "£", AUD: "A$", CAD: "C$" };

/** "₹12,500–37,500" from the post's own currency, else "~$230" from the USD estimate. */
export function budgetLabel(p: {
  budget_min: number | null;
  budget_max: number | null;
  currency: string | null;
  budget_usd: number | null;
}): string | null {
  const sign = p.currency ? CURRENCY_SIGN[p.currency] ?? `${p.currency} ` : null;
  const fmt = (n: number) => Math.round(n).toLocaleString("en-IN");
  if (sign && (p.budget_min || p.budget_max)) {
    if (p.budget_min && p.budget_max && p.budget_min !== p.budget_max) {
      return `${sign}${fmt(p.budget_min)}–${fmt(p.budget_max)}`;
    }
    return `${sign}${fmt((p.budget_max || p.budget_min) as number)}`;
  }
  if (p.budget_usd) return `~$${fmt(p.budget_usd)}`;
  return null;
}

/** "bengaluru_central" -> "Bengaluru Central" */
export function displayCity(city: string): string {
  return city
    .replace(/[_-]+/g, " ")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
