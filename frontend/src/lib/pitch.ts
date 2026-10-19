import { Lead } from "./types";

const DPDP_FOOTER = "\n\nSource: Public Google Maps listing. Reply STOP to opt out.";

function buildPitchBody(lead: Lead): string {
  switch (lead.category) {
    case "DIGITAL_GHOST":
      return `Hi ${lead.business_name}, noticed you're listed on Google Maps in Bengaluru without a dedicated website. We build modern sites for clinics in 48 hours - want a quick preview?`;
    case "DIGITAL_DINOSAUR":
      return `Hi ${lead.business_name}, your Google Maps listing looks great, but your site is missing basics visitors expect (HTTPS/mobile support). We can modernize it fast - interested?`;
    case "LAGGY_UX":
      return `Hi ${lead.business_name}, ran a speed audit on your site - it's taking ${Math.round(
        lead.dom_load_time_ms
      )}ms to load on mobile. You're losing visitors to that delay. We can fix it fast.`;
    case "AUTOMATION_CANDIDATE":
      return `Hi ${lead.business_name}, loved your site design, but noticed you don't have an automated AI booking/chat workflow. We can add one so you stop losing leads after hours.`;
    default:
      return `Hi ${lead.business_name}, we help local businesses like yours modernize their online presence. Got a minute to chat?`;
  }
}

export function buildWhatsAppMessage(lead: Lead): string {
  return `${buildPitchBody(lead)}${DPDP_FOOTER}`;
}

/** Returns a wa.me deep link for the lead, or null if it has no usable phone number. */
export function buildWhatsAppLink(lead: Lead): string | null {
  const cleanPhone = lead.phone_number?.replace(/\D/g, "");
  if (!cleanPhone) return null;

  const message = buildWhatsAppMessage(lead);
  return `https://wa.me/91${cleanPhone}?text=${encodeURIComponent(message)}`;
}
