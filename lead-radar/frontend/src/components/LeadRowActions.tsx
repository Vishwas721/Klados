"use client";

import { useState } from "react";
import { MessageCircle, UserX } from "lucide-react";
import { Lead } from "@/lib/types";
import { buildWhatsAppLink } from "@/lib/pitch";

interface LeadRowActionsProps {
  lead: Lead;
  onWhatsAppSent: (id: string) => Promise<void>;
  onOptOut: (id: string) => Promise<void>;
}

export function LeadRowActions({ lead, onWhatsAppSent, onOptOut }: LeadRowActionsProps) {
  const [pending, setPending] = useState<"whatsapp" | "optout" | null>(null);
  const whatsappLink = buildWhatsAppLink(lead);

  if (lead.opted_out) {
    return <span className="text-xs font-medium text-gray-400">Opted out</span>;
  }

  async function handleWhatsApp() {
    if (!whatsappLink) return;
    window.open(whatsappLink, "_blank", "noopener,noreferrer");
    setPending("whatsapp");
    try {
      await onWhatsAppSent(lead.id);
    } finally {
      setPending(null);
    }
  }

  async function handleOptOut() {
    setPending("optout");
    try {
      await onOptOut(lead.id);
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        suppressHydrationWarning
        onClick={handleWhatsApp}
        disabled={!whatsappLink || pending !== null}
        title={whatsappLink ? undefined : "No phone number on file"}
        className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <MessageCircle className="h-3.5 w-3.5" />
        WhatsApp Pitch
      </button>
      <button
        type="button"
        suppressHydrationWarning
        onClick={handleOptOut}
        disabled={pending !== null}
        className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <UserX className="h-3.5 w-3.5" />
        Opt Out
      </button>
    </div>
  );
}
