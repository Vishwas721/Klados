import {
  CallOutcome,
  CallStats,
  ExhaustedCampaign,
  IntentFit,
  IntentPost,
  IntentSource,
  IntentSourceKey,
  IntentStats,
  IntentStatus,
  Lead,
  LeadStats,
  OutreachStatus,
  ScanTargets,
  ScanTriggerResponse,
  SearchHistoryItem,
} from "./types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY;

/** fetch against the API, adding the X-API-Key header when one is configured. */
function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (API_KEY) headers.set("X-API-Key", API_KEY);
  return fetch(`${API_BASE_URL}${path}`, { cache: "no-store", ...init, headers });
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Throw an ApiError carrying the backend's `detail` message when there is one. */
async function ensureOk(res: Response, fallback: string): Promise<Response> {
  if (res.ok) return res;
  let detail = `${fallback} (${res.status})`;
  try {
    const data = await res.json();
    if (data?.detail) {
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    }
  } catch {
    // Non-JSON error body: keep the generic message
  }
  throw new ApiError(detail, res.status);
}

async function getJson<T>(path: string, fallback: string): Promise<T> {
  const res = await apiFetch(path);
  return (await ensureOk(res, fallback)).json();
}

export async function fetchLeads(
  params: { category?: string; status?: string; limit?: number; offset?: number } = {}
): Promise<Lead[]> {
  const search = new URLSearchParams();
  if (params.category) search.set("category", params.category);
  if (params.status) search.set("status", params.status);
  search.set("limit", String(params.limit ?? 500));
  search.set("offset", String(params.offset ?? 0));

  return getJson(`/api/leads?${search.toString()}`, "Failed to fetch leads");
}

export async function fetchLeadStats(): Promise<LeadStats> {
  return getJson("/api/leads/stats", "Failed to fetch lead stats");
}

export async function updateLeadStatus(id: string, status: OutreachStatus): Promise<Lead> {
  const res = await apiFetch(`/api/leads/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  return (await ensureOk(res, "Failed to update lead status")).json();
}

export async function optOutLead(id: string): Promise<Lead> {
  const res = await apiFetch(`/api/leads/${id}/opt-out`, {
    method: "POST",
  });
  return (await ensureOk(res, "Failed to opt out lead")).json();
}

export async function triggerScan(
  query: string,
  city: string,
  maxCells = 6
): Promise<ScanTriggerResponse> {
  const res = await apiFetch("/api/scrape/trigger", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, city, max_cells: maxCells }),
  });
  return (await ensureOk(res, "Scan trigger failed")).json();
}

export async function fetchSearchHistory(limit = 20): Promise<SearchHistoryItem[]> {
  return getJson(`/api/search-history?limit=${limit}`, "Failed to fetch search history");
}

export async function fetchExhaustedCampaigns(): Promise<ExhaustedCampaign[]> {
  return getJson("/api/campaigns/exhausted", "Failed to fetch exhausted campaigns");
}

export async function fetchScanTargets(): Promise<ScanTargets> {
  return getJson("/api/targets", "Failed to fetch scan targets");
}

// ── Request radar ────────────────────────────────────────────────────────────
export async function fetchIntentPosts(
  params: { source?: IntentSourceKey; fit?: IntentFit; status?: IntentStatus; minScore?: number; limit?: number } = {}
): Promise<IntentPost[]> {
  const search = new URLSearchParams();
  if (params.source) search.set("source", params.source);
  if (params.fit) search.set("fit", params.fit);
  if (params.status) search.set("status", params.status);
  if (params.minScore) search.set("min_score", String(params.minScore));
  search.set("limit", String(params.limit ?? 300));
  return getJson(`/api/intent/posts?${search.toString()}`, "Failed to fetch requests");
}

export async function fetchIntentStats(): Promise<IntentStats> {
  return getJson("/api/intent/stats", "Failed to fetch request stats");
}

export async function updateIntentStatus(id: string, status: IntentStatus): Promise<IntentPost> {
  const res = await apiFetch(`/api/intent/posts/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  return (await ensureOk(res, "Failed to update request")).json();
}

export async function fetchIntentSources(): Promise<IntentSource[]> {
  return getJson("/api/intent/sources", "Failed to fetch sources");
}

export async function pollIntentSource(source: IntentSourceKey): Promise<void> {
  const res = await apiFetch(`/api/intent/sources/${source}/poll`, { method: "POST" });
  await ensureOk(res, "Failed to queue poll");
}

// ── Call desk ────────────────────────────────────────────────────────────────
export async function fetchCallQueue(limit = 40): Promise<Lead[]> {
  return getJson(`/api/calls/queue?limit=${limit}`, "Failed to load the call queue");
}

export async function fetchInterested(): Promise<Lead[]> {
  return getJson("/api/calls/interested", "Failed to load interested leads");
}

export async function fetchCallStats(): Promise<CallStats> {
  return getJson("/api/calls/stats", "Failed to load call stats");
}

export async function logCall(
  id: string,
  outcome: CallOutcome,
  opts: { notes?: string; callbackAt?: string } = {}
): Promise<Lead> {
  const res = await apiFetch(`/api/leads/${id}/call`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ outcome, notes: opts.notes, callback_at: opts.callbackAt }),
  });
  return (await ensureOk(res, "Failed to log the call")).json();
}
