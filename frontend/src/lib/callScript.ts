import type { Lead } from "./types";
import { isLandline, toWhatsAppNumber } from "./pitch";

/** One line of the call, in Kannada script, romanised Kannada, and English. */
export interface ScriptLine {
  kn: string;
  roman: string;
  en: string;
}

export interface CallScript {
  open: ScriptLine;
  point: ScriptLine;
  ask: ScriptLine;
  ifYes: ScriptLine;
  ifBusy: ScriptLine;
  ifNo: ScriptLine;
}

export type ScriptLang = keyof ScriptLine;

function line(kn: string, roman: string, en: string): ScriptLine {
  return { kn, roman, en };
}

/**
 * The name as you'd say it: Google listings often read like
 * "Furnishka - Kalyan Nagar | Best Furniture Store in Bangalore".
 */
export function spokenName(name: string): string {
  const short = name
    .split(/\s+[|•·–—]\s+/)[0]
    .split(/\s+-\s+/)[0]
    .replace(/\s*\([^)]*\)\s*/g, " ")
    .trim();
  return short || name;
}

/** The observation that earns the call, from what the audit found. */
function pointFor(lead: Lead): ScriptLine {
  const biz = spokenName(lead.business_name);
  switch (lead.category) {
    case "DIGITAL_GHOST":
      if (lead.website_url) {
        return line(
          `ನಿಮ್ಮ Google Maps ನಲ್ಲಿರೋ ವೆಬ್‌ಸೈಟ್ ಓಪನ್ ಆಗ್ತಿಲ್ಲ. ಗ್ರಾಹಕರು ಕ್ಲಿಕ್ ಮಾಡಿದ್ರೆ ಏನೂ ಬರಲ್ಲ.`,
          `Nimma Google Maps-alliro website open aagtilla. Graahakaru click maadidre enu baralla.`,
          `The website on your Google Maps listing isn't opening. Customers who click it get nothing.`
        );
      }
      return line(
        `Google Maps ನಲ್ಲಿ ${biz} ನೋಡಿದೆ, ಆದ್ರೆ ನಿಮಗೆ ವೆಬ್‌ಸೈಟ್ ಇಲ್ಲ ಅನ್ಸುತ್ತೆ. ವೆಬ್‌ಸೈಟ್ ಇದ್ರೆ ಜನ ಆನ್‌ಲೈನ್‌ನಲ್ಲೇ ನಿಮ್ಮನ್ನ ಹುಡುಕಬಹುದು.`,
        `Google Maps-alli ${biz} nodide, aadre nimge website illa ansutte. Website idre jana online-alle nimmanna hudukabahudu.`,
        `I saw ${biz} on Google Maps, but it looks like you don't have a website. With one, people can find you online.`
      );
    case "DIGITAL_DINOSAUR":
      if (!lead.has_ssl) {
        return line(
          `ನಿಮ್ಮ ವೆಬ್‌ಸೈಟ್ ಓಪನ್ ಮಾಡಿದ್ರೆ ಬ್ರೌಸರ್ 'Not secure' ಅಂತ ತೋರಿಸುತ್ತೆ. ಅದನ್ನ ನೋಡಿ ಜನ ವಾಪಸ್ ಹೋಗ್ತಾರೆ.`,
          `Nimma website open maadidre browser 'Not secure' anta torisutte. Adanna nodi jana vaapas hogtaare.`,
          `When your website opens, the browser shows "Not secure", and people leave when they see it.`
        );
      }
      return line(
        `ನಿಮ್ಮ ವೆಬ್‌ಸೈಟ್ ಮೊಬೈಲ್‌ನಲ್ಲಿ ಸರಿಯಾಗಿ ಕಾಣಿಸ್ತಿಲ್ಲ. ಹೆಚ್ಚಿನ ಜನ ಫೋನ್‌ನಲ್ಲೇ ನೋಡ್ತಾರೆ.`,
        `Nimma website mobile-nalli sariyaagi kaanistilla. Hechchina jana phone-nalle nodtaare.`,
        `Your website doesn't display properly on mobile, and most people look on their phone.`
      );
    case "LAGGY_UX": {
      const secs = lead.dom_load_time_ms >= 15000 ? "15ಕ್ಕೂ ಹೆಚ್ಚು" : String(Math.max(1, Math.round(lead.dom_load_time_ms / 1000)));
      const secsRoman = lead.dom_load_time_ms >= 15000 ? "15-kkoo hechchu" : secs;
      const secsEn = lead.dom_load_time_ms >= 15000 ? "more than 15" : secs;
      return line(
        `ನಿಮ್ಮ ವೆಬ್‌ಸೈಟ್ ಓಪನ್ ಆಗೋಕೆ ${secs} ಸೆಕೆಂಡ್ ತಗೊಳ್ತಿದೆ. ಅಷ್ಟು ಹೊತ್ತು ಜನ ಕಾಯಲ್ಲ.`,
        `Nimma website open aagoke ${secsRoman} second tagoltide. Ashtu hottu jana kaayalla.`,
        `Your website takes ${secsEn} seconds to open. People won't wait that long.`
      );
    }
    case "AUTOMATION_CANDIDATE":
    default: {
      const booking = lead.lacks_booking_flow !== false;
      const chat = !!lead.lacks_chat_widget;
      const gapKn = booking && chat ? "ಆನ್‌ಲೈನ್ ಬುಕಿಂಗ್ ಅಥವಾ WhatsApp ಚಾಟ್" : chat ? "WhatsApp ಚಾಟ್" : "ಆನ್‌ಲೈನ್ ಬುಕಿಂಗ್";
      const gapRoman = booking && chat ? "online booking athava WhatsApp chat" : chat ? "WhatsApp chat" : "online booking";
      const gapEn = booking && chat ? "online booking or WhatsApp chat" : chat ? "WhatsApp chat" : "online booking";
      return line(
        `ನಿಮ್ಮ ವೆಬ್‌ಸೈಟ್ ಚೆನ್ನಾಗಿದೆ, ಆದ್ರೆ ಅದರಲ್ಲಿ ${gapKn} ಇಲ್ಲ. ಅದು ಇದ್ರೆ ರಾತ್ರಿ ಹೊತ್ತೂ ಬುಕಿಂಗ್ ಬರುತ್ತೆ.`,
        `Nimma website chennaagide, aadre adaralli ${gapRoman} illa. Adu idre raatri hottu booking barutte.`,
        `Your website is nice, but it has no ${gapEn}. With it, bookings come in even at night.`
      );
    }
  }
}

export function buildCallScript(lead: Lead, me: string): CallScript {
  const name = me.trim() || "…";
  const landline = isLandline(lead.phone_number);
  return {
    open: line(
      `ನಮಸ್ಕಾರ, ನಾನು ${name}. ನಾನು ಬೆಂಗಳೂರಿನಲ್ಲಿ ಸಣ್ಣ ಬಿಸಿನೆಸ್‌ಗಳಿಗೆ ವೆಬ್‌ಸೈಟ್ ಮಾಡಿಕೊಡ್ತೀನಿ. ಒಂದು ನಿಮಿಷ ಮಾತಾಡಬಹುದಾ?`,
      `Namaskara, naanu ${name}. Naanu Bengaluru-nalli sanna business-galige website maadikodteeni. Ondu nimisha maataadabahudaa?`,
      `Hello, I'm ${name}. I build websites for small businesses in Bengaluru. Can I take one minute?`
    ),
    point: pointFor(lead),
    ask: line(
      `ಇದರ ಬಗ್ಗೆ ನಿಮಗೆ ಆಸಕ್ತಿ ಇದೆಯಾ? ಇಲ್ಲ ಅಂದ್ರೆ ಪರವಾಗಿಲ್ಲ, ಮತ್ತೆ ಕಾಲ್ ಮಾಡಲ್ಲ.`,
      `Idara bagge nimage aasakti ideyaa? Illa andre paravaagilla, matte call maadalla.`,
      `Would you be interested in this? If not, no problem, I won't call again.`
    ),
    ifYes: landline
      ? line(
          `ತುಂಬಾ ಖುಷಿ! ನಿಮ್ಮ WhatsApp ನಂಬರ್ ಕೊಡ್ತೀರಾ? ಕೆಲವು ಸ್ಯಾಂಪಲ್ ಕಳಿಸ್ತೀನಿ.`,
          `Tumba khushi! Nimma WhatsApp number kodteeraa? Kelavu sample kalisteeni.`,
          `Great! Could you give me your WhatsApp number? I'll send some samples.`
        )
      : line(
          `ತುಂಬಾ ಖುಷಿ! ಇದೇ ನಂಬರ್‌ಗೆ WhatsApp ನಲ್ಲಿ ಕೆಲವು ಸ್ಯಾಂಪಲ್ ಕಳಿಸ್ತೀನಿ, ಆಮೇಲೆ ಮಾತಾಡೋಣ.`,
          `Tumba khushi! Ide number-ge WhatsApp-nalli kelavu sample kalisteeni, aamele maataadona.`,
          `Great! I'll send a few samples to this number on WhatsApp, and we'll talk after.`
        ),
    ifBusy: line(`ಸರಿ, ಯಾವಾಗ ಕಾಲ್ ಮಾಡಲಿ?`, `Sari, yaavaaga call maadali?`, `Okay, when should I call you?`),
    ifNo: line(
      `ಪರವಾಗಿಲ್ಲ, ಸಮಯ ಕೊಟ್ಟಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದಗಳು. ಒಳ್ಳೇ ದಿನ!`,
      `Paravaagilla, samaya kottiddakke dhanyavaadagalu. Olle dina!`,
      `No problem, thanks for your time. Have a good day!`
    ),
  };
}

/** WhatsApp follow-up in Kannada after someone says yes, or null for landlines. */
export function buildFollowUpLink(lead: Lead, me: string, portfolio: string): string | null {
  const number = toWhatsAppNumber(lead.phone_number);
  if (!number) return null;
  const name = me.trim() || "ವೆಬ್‌ಸೈಟ್ ಡೆವಲಪರ್";
  const samples = portfolio.trim()
    ? `\n\n${spokenName(lead.business_name)} ಗೆ ಮಾಡಬಹುದಾದ ವೆಬ್‌ಸೈಟ್‌ನ ಕೆಲವು ಉದಾಹರಣೆಗಳು ಇಲ್ಲಿವೆ: ${portfolio.trim()}`
    : "";
  const text =
    `ನಮಸ್ಕಾರ! ಈಗಷ್ಟೇ ಫೋನ್‌ನಲ್ಲಿ ಮಾತಾಡಿದ್ದು ನಾನೇ, ${name}. ಸಮಯ ಕೊಟ್ಟಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದಗಳು.` +
    samples +
    `\n\nನಿಮಗೆ ಯಾವಾಗ ಮಾತಾಡೋಕೆ ಅನುಕೂಲ?`;
  return `https://wa.me/${number}?text=${encodeURIComponent(text)}`;
}

/** "98450 12345" for mobiles, "080 4123 4567" for Bengaluru-style landlines. */
export function formatPhone(phone: string): string {
  const d = phone.replace(/\D/g, "");
  if (d.length === 10 && !d.startsWith("0")) return `${d.slice(0, 5)} ${d.slice(5)}`;
  if (d.length === 11 && d.startsWith("0")) return `${d.slice(0, 3)} ${d.slice(3, 7)} ${d.slice(7)}`;
  return phone;
}

export function telHref(phone: string): string {
  return `tel:+91${phone.replace(/\D/g, "").replace(/^0/, "")}`;
}
