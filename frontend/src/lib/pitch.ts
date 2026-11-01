import type { Lead } from "./types";

const DPDP_FOOTER = "\n\nSource: Public Google Maps listing. Reply STOP to opt out.";

/** "bengaluru_central" -> "Bengaluru Central" */
function displayCity(city: string): string {
  return city
    .replace(/[_-]+/g, " ")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function buildPitchBody(lead: Lead): string {
  const name = lead.business_name;
  const city = displayCity(lead.city || "your area");

  switch (lead.category) {
    case "DIGITAL_GHOST":
      if (lead.website_url) {
        // Listed a website on Maps, but the audit couldn't reach it
        return `Hi ${name}, the website on your Google Maps listing (${lead.website_url}) isn't loading for customers right now. We can get you a fast, modern site back up within 48 hours - want a quick preview?`;
      }
      return `Hi ${name}, noticed you're listed on Google Maps in ${city} without a website. We build modern sites for local businesses like yours in 48 hours - want a quick preview?`;
    case "DIGITAL_DINOSAUR":
      return `Hi ${name}, your Google Maps listing looks great, but your site is missing basics visitors expect (${
        lead.has_ssl ? "mobile support" : "a secure HTTPS connection"
      }). We can modernize it fast - interested?`;
    case "LAGGY_UX":
      return `Hi ${name}, ran a speed audit on your site - it took ${(lead.dom_load_time_ms / 1000).toFixed(
        1
      )}s to load. You're losing visitors to that delay. We can fix it fast.`;
    case "AUTOMATION_CANDIDATE": {
      const gaps = [
        lead.lacks_booking_flow ? "online booking" : null,
        lead.lacks_chat_widget ? "an instant chat/WhatsApp assistant" : null,
      ].filter(Boolean);
      const gapText = gaps.length ? gaps.join(" or ") : "an automated booking/chat workflow";
      return `Hi ${name}, loved your site, but noticed you don't have ${gapText}. We can add it so you stop losing leads after hours.`;
    }
    default:
      return `Hi ${name}, we help local businesses like yours modernize their online presence. Got a minute to chat?`;
  }
}

export function buildWhatsAppMessage(lead: Lead): string {
  return `${buildPitchBody(lead)}${DPDP_FOOTER}`;
}

/**
 * Convert a stored Indian number into wa.me's international format (91XXXXXXXXXX).
 * Landlines keep their STD code but drop the trunk 0. Returns null for anything
 * that can't be a valid Indian number.
 */
export function toWhatsAppNumber(phone: string | null | undefined): string | null {
  let digits = phone?.replace(/\D/g, "") ?? "";
  if (digits.length === 12 && digits.startsWith("91")) digits = digits.slice(2);
  if (digits.length === 11 && digits.startsWith("0")) digits = digits.slice(1);
  return digits.length === 10 ? `91${digits}` : null;
}

/** Returns a wa.me deep link for the lead, or null if it has no usable phone number. */
export function buildWhatsAppLink(lead: Lead): string | null {
  const number = toWhatsAppNumber(lead.phone_number);
  if (!number) return null;

  const message = buildWhatsAppMessage(lead);
  return `https://wa.me/${number}?text=${encodeURIComponent(message)}`;
}
