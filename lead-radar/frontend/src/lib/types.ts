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
}
