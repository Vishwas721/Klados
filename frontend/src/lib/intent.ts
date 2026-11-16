import { IntentFit, IntentPost, IntentSourceKey, IntentStatus } from "./types";

export const FIT_META: Record<IntentFit, { label: string; short: string; tone: string }> = {
  WEBSITE_BUILD: { label: "New website", short: "Build", tone: "var(--c-build)" },
  WEBSITE_FIX: { label: "Fix / redesign", short: "Fix", tone: "var(--c-fix)" },
  AUTOMATION: { label: "Automation", short: "Automate", tone: "var(--c-auto)" },
  OTHER: { label: "Other", short: "Other", tone: "var(--muted)" },
};

export const SOURCE_META: Record<IntentSourceKey, { label: string; mark: string }> = {
  freelancer: { label: "Freelancer.com", mark: "FL" },
  reddit: { label: "Reddit", mark: "RD" },
  hackernews: { label: "Hacker News", mark: "HN" },
  rss: { label: "RSS feeds", mark: "RS" },
  web: { label: "Open web", mark: "WB" },
};

export const STATUS_META: Record<IntentStatus, { label: string; verb: string; key: string }> = {
  NEW: { label: "Inbox", verb: "Back to inbox", key: "U" },
  SAVED: { label: "Shortlist", verb: "Shortlist", key: "S" },
  REPLIED: { label: "Replied", verb: "Mark replied", key: "R" },
  WON: { label: "Won", verb: "Mark won", key: "W" },
  DISMISSED: { label: "Binned", verb: "Bin it", key: "X" },
};

export const STATUS_ORDER: IntentStatus[] = ["NEW", "SAVED", "REPLIED", "WON", "DISMISSED"];
export const FIT_ORDER: IntentFit[] = ["WEBSITE_BUILD", "WEBSITE_FIX", "AUTOMATION", "OTHER"];
export const SOURCE_ORDER: IntentSourceKey[] = ["freelancer", "reddit", "hackernews", "rss", "web"];

export const HOT_SCORE = 70;

export type Heat = "hot" | "warm" | "cool";

export function heat(score: number): Heat {
  if (score >= HOT_SCORE) return "hot";
  if (score >= 45) return "warm";
  return "cool";
}

/** When the person asked: the post's own time, else when we found it. */
export function askedAt(p: IntentPost): string {
  return p.posted_at ?? p.created_at;
}

export type Band = "Last hour" | "Today" | "This week" | "Earlier";

export function band(p: IntentPost): Band {
  const hours = (Date.now() - new Date(askedAt(p)).getTime()) / 3_600_000;
  if (hours < 1) return "Last hour";
  if (hours < 24) return "Today";
  if (hours < 24 * 7) return "This week";
  return "Earlier";
}
