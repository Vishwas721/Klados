"use client";

import { useState } from "react";
import { MessageCircle, Phone, UserX } from "lucide-react";
import { Lead } from "@/lib/types";
import { buildWhatsAppLink, isLandline } from "@/lib/pitch";

const TTFB_LIMIT = 1800;
const LOAD_LIMIT = 4500;

function speedTone(ms: number, limit: number): string {
  if (!ms) return "text-faint";
  if (ms <= limit * 0.6) return "text-ok";
  if (ms <= limit) return "text-warn";
  return "text-bad";
}

const CONTACTED = new Set(["CONTACTED_WHATSAPP", "CONTACTED_EMAIL", "RESPONDED", "CONVERTED"]);

interface BusinessCardProps {
  lead: Lead;
  onWhatsAppSent: (id: string) => Promise<void>;
  onOptOut: (id: string) => Promise<void>;
}

export function BusinessCard({ lead, onWhatsAppSent, onOptOut }: BusinessCardProps) {
  const [pending, setPending] = useState(false);
  const link = buildWhatsAppLink(lead);
  const landline = isLandline(lead.phone_number);
  const host = lead.website_url?.replace(/^https?:\/\//, "").replace(/\/$/, "");

  const run = async (fn: () => Promise<void>) => {
    setPending(true);
    try {
      await fn();
    } finally {
      setPending(false);
    }
  };

  return (
    <article className={`rounded-xl border border-line bg-card p-3.5 ${lead.opted_out ? "opacity-50" : ""}`}>
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-[15px] font-medium leading-snug text-ink">{lead.business_name}</h4>
        {CONTACTED.has(lead.status) && (
          <span className="shrink-0 rounded-full bg-ok/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ok">
            pitched
          </span>
        )}
      </div>

      <div className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-muted">
        <a href={`tel:+91${lead.phone_number.replace(/^0/, "")}`} className="inline-flex items-center gap-1 hover:text-ink">
          <Phone className="h-3 w-3" />
          {lead.phone_number}
        </a>
        {landline && <span className="text-faint">landline</span>}
        {host && (
          <a
            href={lead.website_url!}
            target="_blank"
            rel="noreferrer"
            title={lead.website_url!}
            className="max-w-[12rem] truncate underline decoration-line underline-offset-2 hover:text-ink"
          >
            {host}
          </a>
        )}
      </div>

      {lead.website_url && (lead.ttfb_ms > 0 || lead.dom_load_time_ms > 0) && (
        <div className="mt-2 flex gap-3 font-mono text-[11px]">
          <span className={speedTone(lead.ttfb_ms, TTFB_LIMIT)}>TTFB {lead.ttfb_ms ? `${lead.ttfb_ms}ms` : "—"}</span>
          <span className={speedTone(lead.dom_load_time_ms, LOAD_LIMIT)}>
            load {lead.dom_load_time_ms ? `${(lead.dom_load_time_ms / 1000).toFixed(1)}s` : "—"}
          </span>
          {!lead.has_ssl && <span className="text-bad">no https</span>}
          {lead.has_ssl && !lead.is_mobile_responsive && <span className="text-warn">not mobile</span>}
        </div>
      )}

      {(lead.detected_tech.length > 0 || lead.lacks_booking_flow || lead.lacks_chat_widget) && (
        <div className="mt-2 flex flex-wrap gap-1">
          {lead.detected_tech.slice(0, 3).map((t) => (
            <span key={t} className="rounded bg-sunk px-1.5 py-0.5 text-[10px] text-muted">
              {t}
            </span>
          ))}
          {lead.lacks_booking_flow && (
            <span className="rounded border border-dashed border-line px-1.5 py-0.5 text-[10px] text-muted">no booking</span>
          )}
          {lead.lacks_chat_widget && (
            <span className="rounded border border-dashed border-line px-1.5 py-0.5 text-[10px] text-muted">no chat</span>
          )}
        </div>
      )}

      {lead.llm_audit_summary && lead.llm_audit_summary !== "unknown" && (
        <p className="mt-2 font-serif text-[15px] italic leading-snug text-muted">{lead.llm_audit_summary}</p>
      )}

      {!lead.opted_out && (
        <div className="mt-3 flex items-center gap-1.5">
          <button
            type="button"
            disabled={!link || pending}
            title={link ? "Open WhatsApp with a tailored pitch" : landline ? "Landline: call instead" : "No usable mobile"}
            onClick={() =>
              run(async () => {
                if (!link) return;
                window.open(link, "_blank", "noopener,noreferrer");
                await onWhatsAppSent(lead.id);
              })
            }
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-full bg-ok px-3 py-1.5 text-xs font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-35"
          >
            <MessageCircle className="h-3.5 w-3.5" />
            WhatsApp pitch
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={() => run(() => onOptOut(lead.id))}
            title="Opted out: never contact again"
            aria-label="Opt out"
            className="grid h-7 w-7 place-items-center rounded-full border border-line text-faint transition hover:border-bad hover:text-bad disabled:opacity-40"
          >
            <UserX className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </article>
  );
}
