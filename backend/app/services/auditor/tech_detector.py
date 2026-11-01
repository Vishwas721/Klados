"""Fingerprint a website's stack and engagement widgets from its HTML.

Signature matching on the raw markup is cheap and deterministic, and it sees
script tags an LLM reading body text never would - which is exactly where
chat widgets and booking embeds live.
"""

import re

# (label, pattern) - patterns are matched case-insensitively against the HTML
TECH_SIGNATURES: list[tuple[str, str]] = [
    ("WordPress", r"wp-content/|wp-includes/"),
    ("WooCommerce", r"woocommerce"),
    ("Elementor", r"elementor"),
    ("Wix", r"static\.wixstatic\.com|wix\.com/"),
    ("Shopify", r"cdn\.shopify\.com|myshopify\.com"),
    ("Squarespace", r"squarespace\.com|static1\.squarespace"),
    ("GoDaddy Builder", r"img1\.wsimg\.com|godaddy"),
    ("Webflow", r"webflow\.(com|io)|data-wf-page"),
    ("Joomla", r"/media/jui/|joomla"),
    ("Drupal", r"drupal-settings-json|/sites/default/files/"),
    ("Google Sites", r"sites\.google\.com"),
    ("Blogger", r"blogger\.com|blogspot\.com"),
    ("Zoho Sites", r"zohositescontent|zoho\.com/sites"),
    ("Next.js", r"__NEXT_DATA__|/_next/static/"),
    ("React", r"data-reactroot|react-dom"),
    ("Angular", r"ng-version="),
    ("Vue", r"data-v-[0-9a-f]{8}|vue(\.min)?\.js"),
    ("jQuery", r"jquery(\.min)?\.js|jquery-\d"),
    ("Bootstrap", r"bootstrap(\.min)?\.(css|js)"),
    ("Google Analytics", r"googletagmanager\.com/gtag/js|google-analytics\.com"),
    ("Google Tag Manager", r"googletagmanager\.com/gtm\.js"),
    ("Meta Pixel", r"connect\.facebook\.net/[^\"']*/fbevents\.js"),
    ("Hotjar", r"static\.hotjar\.com"),
]

CHAT_SIGNATURES: list[tuple[str, str]] = [
    ("Tawk.to", r"embed\.tawk\.to"),
    ("Intercom", r"widget\.intercom\.io|intercomcdn"),
    ("Crisp", r"client\.crisp\.chat"),
    ("Tidio", r"code\.tidio\.co"),
    ("Zendesk Chat", r"zopim|static\.zdassets\.com"),
    ("Freshchat", r"wchat\.freshchat\.com|freshchat"),
    ("LiveChat", r"cdn\.livechatinc\.com"),
    ("Drift", r"js\.driftt\.com"),
    ("HubSpot Chat", r"js\.hs-scripts\.com|js\.usemessages\.com"),
    ("Interakt", r"interakt"),
    ("WATI", r"wati\.io"),
    ("Gallabox", r"gallabox"),
    ("WhatsApp", r"wa\.me/|api\.whatsapp\.com/send|web\.whatsapp\.com/send"),
]

BOOKING_SIGNATURES: list[tuple[str, str]] = [
    ("Calendly", r"calendly\.com"),
    ("Practo", r"practo\.com"),
    ("Zoho Bookings", r"zohobookings|bookings\.zoho"),
    ("SimplyBook", r"simplybook\.(me|it)"),
    ("Setmore", r"setmore\.com"),
    ("Acuity", r"acuityscheduling\.com"),
    ("Fresha", r"fresha\.com"),
    ("Booksy", r"booksy\.com"),
    ("Square Appointments", r"squareup\.com/appointments"),
    ("Google Booking", r"calendar\.app\.google|calendar\.google\.com/calendar/appointments"),
    ("Cal.com", r"cal\.com/"),
]

_COMPILED = {
    name: [(label, re.compile(pattern, re.IGNORECASE)) for label, pattern in sigs]
    for name, sigs in (
        ("tech", TECH_SIGNATURES),
        ("chat", CHAT_SIGNATURES),
        ("booking", BOOKING_SIGNATURES),
    )
}


def _matches(kind: str, html: str) -> list[str]:
    return [label for label, rx in _COMPILED[kind] if rx.search(html)]


def detect_stack(html: str | None) -> dict:
    """Return detected tech plus whether a chat widget / booking flow is embedded.

    `detected_tech` lists the site's platform/libraries followed by any chat
    or booking providers found, so the dashboard shows them together.
    """
    if not html:
        return {"detected_tech": [], "has_chat_widget": False, "has_online_booking": False}

    tech = _matches("tech", html)
    chat = _matches("chat", html)
    booking = _matches("booking", html)
    return {
        "detected_tech": tech + chat + booking,
        "has_chat_widget": bool(chat),
        "has_online_booking": bool(booking),
    }
