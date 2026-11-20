export type LeadCategory =
  | "DIGITAL_GHOST"
  | "DIGITAL_DINOSAUR"
  | "LAGGY_UX"
  | "AUTOMATION_CANDIDATE";

export type OutreachStatus =
  | "PENDING"
  | "AUDITED"
  | "CONTACTED_WHATSAPP"
  | "CONTACTED_EMAIL"
  | "RESPONDED"
  | "CONVERTED"
  | "OPTED_OUT";

export interface Lead {
  id: string;
  place_id?: string | null;
  business_name: string;
  phone_number: string;
  email: string | null;
  website_url: string | null;
  city: string;
  h3_hex_id: string | null;
  latitude: number | null;
  longitude: number | null;
  category: LeadCategory;
  has_ssl: boolean;
  is_mobile_responsive: boolean;
  ttfb_ms: number;
  dom_load_time_ms: number;
  detected_tech: string[];
  llm_audit_summary: string | null;
  lacks_chat_widget: boolean | null;
  lacks_booking_flow: boolean | null;
  origin_source_url: string;
  opted_out: boolean;
  status: OutreachStatus;
  call_outcome: CallOutcome | null;
  call_attempts: number;
  last_called_at: string | null;
  next_call_at: string | null;
  call_notes: string | null;
}

export type CallOutcome = "INTERESTED" | "CALL_BACK" | "NOT_INTERESTED" | "WRONG_NUMBER" | "NO_ANSWER";

export interface CallStats {
  queue: number;
  called_today: number;
  today_by_outcome: Partial<Record<CallOutcome, number>>;
  interested_total: number;
}

export interface SearchHistoryItem {
  id: string;
  niche: string;
  city: string;
  last_run_at: string;
  leads_count: number;
  status: string;
  is_locked: boolean;
  locked_until: string;
}

export interface ScanTriggerResponse {
  task_ids: string[];
  cells_queued: number;
  cells_remaining: number;
}

export interface LeadStats {
  total: number;
  by_category: Partial<Record<LeadCategory, number>>;
  opted_out: number;
}

export interface ExhaustedCampaign {
  city: string;
  niche: string;
  last_scraped_at: string;
}

export interface ScanTargets {
  cities: string[];
  niches: string[];
}

// ── Request radar ────────────────────────────────────────────────────────────
export type IntentSourceKey = "freelancer" | "reddit" | "hackernews" | "rss" | "web";
export type IntentFit = "WEBSITE_BUILD" | "WEBSITE_FIX" | "AUTOMATION" | "OTHER";
export type IntentStatus = "NEW" | "SAVED" | "REPLIED" | "WON" | "DISMISSED";

export interface IntentPost {
  id: string;
  source: IntentSourceKey;
  url: string;
  title: string;
  body: string;
  author: string | null;
  channel: string | null;
  posted_at: string | null;
  budget_min: number | null;
  budget_max: number | null;
  currency: string | null;
  budget_usd: number | null;
  bid_count: number | null;
  fit: IntentFit;
  score: number;
  signals: string[];
  is_local: boolean;
  summary: string | null;
  reply_draft: string | null;
  status: IntentStatus;
  created_at: string;
  /** Marketplace projects only: what to bid, from the client's budget */
  bid: SuggestedBid | null;
}

export interface SuggestedBid {
  amount: number;
  currency: string;
  hourly: boolean;
  days: number | null;
  label: string;
  rationale: string;
}

export interface IntentStats {
  total: number;
  by_status: Partial<Record<IntentStatus, number>>;
  by_fit: Partial<Record<IntentFit, number>>;
  by_source: Partial<Record<IntentSourceKey, number>>;
  new_last_24h: number;
  hot: number;
}

export interface IntentSource {
  key: IntentSourceKey;
  label: string;
  configured: boolean;
  setup_hint: string;
  interval_s: number;
  state: "ok" | "error" | "backing_off" | "not_configured" | null;
  last_attempt_at: string | null;
  last_ok_at: string | null;
  last_error: string | null;
  last_fetched: number | null;
  last_new: number | null;
  total_new: number;
  backoff_s: number;
  poll_requested: boolean;
}
