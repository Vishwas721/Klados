import {
  ExhaustedCampaign,
  Lead,
  LeadStats,
  OutreachStatus,
  ScanTargets,
  ScanTriggerResponse,
  SearchHistoryItem,
} from "./types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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
  const res = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
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
  const res = await fetch(`${API_BASE_URL}/api/leads/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  return (await ensureOk(res, "Failed to update lead status")).json();
}

export async function optOutLead(id: string): Promise<Lead> {
  const res = await fetch(`${API_BASE_URL}/api/leads/${id}/opt-out`, {
    method: "POST",
  });
  return (await ensureOk(res, "Failed to opt out lead")).json();
}

export async function triggerScan(
  query: string,
  city: string,
  maxCells = 6
): Promise<ScanTriggerResponse> {
  const res = await fetch(`${API_BASE_URL}/api/scrape/trigger`, {
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
