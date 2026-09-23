import { Lead, OutreachStatus, ScanTriggerResponse } from "./types";

export const API_BASE_URL = "http://localhost:8000";

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
  if (!res.ok) throw new Error(`Failed to fetch leads (${res.status})`);
  return res.json();
}

export async function updateLeadStatus(id: string, status: OutreachStatus): Promise<Lead> {
  const res = await fetch(`${API_BASE_URL}/api/leads/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error(`Failed to update lead status (${res.status})`);
  return res.json();
}

export async function optOutLead(id: string): Promise<Lead> {
  const res = await fetch(`${API_BASE_URL}/api/leads/${id}/opt-out`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to opt out lead (${res.status})`);
  return res.json();
}

export async function triggerScan(
  query: string,
  city: string,
  maxCells = 2
): Promise<ScanTriggerResponse> {
  const res = await fetch(`${API_BASE_URL}/api/scrape/trigger`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, city, max_cells: maxCells }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail || `Scan trigger failed (${res.status})`);
  }
  return res.json();
}
