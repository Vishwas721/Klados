import { Lead, OutreachStatus, ScanTriggerResponse, SearchHistoryItem } from "./types";

export const API_BASE_URL = "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function fetchLeads(
  params: { category?: string; status?: string; limit?: number; offset?: number } = {}
): Promise<Lead[]> {
  const search = new URLSearchParams();
  if (params.category) search.set("category", params.category);
  if (params.status) search.set("status", params.status);
  search.set("limit", String(params.limit ?? 200));
  search.set("offset", String(params.offset ?? 0));

  const res = await fetch(`${API_BASE_URL}/api/leads?${search.toString()}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new ApiError(`Failed to fetch leads (${res.status})`, res.status);
  return res.json();
}

export async function updateLeadStatus(id: string, status: OutreachStatus): Promise<Lead> {
  const res = await fetch(`${API_BASE_URL}/api/leads/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new ApiError(`Failed to update lead status (${res.status})`, res.status);
  return res.json();
}

export async function optOutLead(id: string): Promise<Lead> {
  const res = await fetch(`${API_BASE_URL}/api/leads/${id}/opt-out`, {
    method: "POST",
  });
  if (!res.ok) throw new ApiError(`Failed to opt out lead (${res.status})`, res.status);
  return res.json();
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
  if (!res.ok) {
    let detail = `Scan trigger failed (${res.status})`;
    try {
      const data = await res.json();
      if (data?.detail) {
        detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      const text = await res.text().catch(() => "");
      if (text) detail = text;
    }
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

export async function fetchSearchHistory(limit = 20): Promise<SearchHistoryItem[]> {
  const res = await fetch(`${API_BASE_URL}/api/search-history?limit=${limit}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new ApiError(`Failed to fetch search history (${res.status})`, res.status);
  return res.json();
}
