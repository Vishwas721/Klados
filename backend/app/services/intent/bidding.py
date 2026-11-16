"""Suggested bids and proposal drafts for marketplace projects (Freelancer.com).

A new profile without reviews wins on a fair, slightly-low price and a
concrete plan, so the suggestion sits about a third of the way into the
client's range: never under their minimum, never near their maximum.
"""

from dataclasses import asdict, dataclass
import math

from app.core.config import settings

# How far into the client's range to bid (0 = their minimum, 1 = their maximum)
FIXED_POSITION = 0.35
HOURLY_POSITION = 0.30

CURRENCY_SIGN = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£", "AUD": "A$", "CAD": "C$", "SGD": "S$"}


@dataclass
class Bid:
    amount: float
    currency: str
    hourly: bool
    days: int | None
    label: str
    rationale: str

    def as_dict(self) -> dict:
        return asdict(self)


def _nice(amount: float, currency: str) -> float:
    """Round to a number a person would quote: ₹14,000 not ₹13,862."""
    if currency == "INR":
        step = 500 if amount >= 5000 else 100
    elif amount < 100:
        step = 5
    elif amount < 1000:
        step = 10
    else:
        step = 50
    return max(step, math.floor(amount / step + 0.5) * step)  # halves round up


def money(amount: float, currency: str) -> str:
    return f"{CURRENCY_SIGN.get(currency, f'{currency} ')}{amount:,.0f}"


def delivery_days(fit: str, budget_usd: float | None) -> int:
    usd = budget_usd or 0
    if fit == "WEBSITE_FIX":
        return 3 if usd <= 150 else 5
    if fit == "AUTOMATION":
        return 5 if usd <= 300 else 10 if usd <= 1000 else 14
    return 5 if usd <= 150 else 7 if usd <= 500 else 14 if usd <= 1500 else 21


def suggest_bid(
    *,
    budget_min: float | None,
    budget_max: float | None,
    currency: str | None,
    hourly: bool,
    fit: str,
    budget_usd: float | None,
) -> Bid | None:
    low = budget_min or budget_max
    high = budget_max or budget_min
    if not low or not currency:
        return None
    position = HOURLY_POSITION if hourly else FIXED_POSITION
    amount = _nice(low + (high - low) * position, currency)
    amount = max(amount, low)  # bids under the client's minimum look careless

    if hourly:
        return Bid(
            amount=amount,
            currency=currency,
            hourly=True,
            days=None,
            label=f"{money(amount, currency)}/hour",
            rationale="A third into their hourly range: competitive for a new profile, not a race to the bottom.",
        )
    days = delivery_days(fit, budget_usd)
    return Bid(
        amount=amount,
        currency=currency,
        hourly=False,
        days=days,
        label=f"{money(amount, currency)} · {days} days",
        rationale=(
            f"A third into their {money(low, currency)}–{money(high, currency)} range: new profiles win on a fair "
            "price plus a clear plan. Raise it once you have reviews."
        ),
    )


def bid_for_post(post) -> Bid | None:
    """suggest_bid for an IntentPost row (or anything with the same fields)."""
    if post.source != "freelancer":
        return None
    hourly = "hourly" in (post.signals or [])
    return suggest_bid(
        budget_min=post.budget_min,
        budget_max=post.budget_max,
        currency=post.currency,
        hourly=hourly,
        fit=post.fit,
        budget_usd=post.budget_usd,
    )


_OPENING = {
    "WEBSITE_BUILD": "This is exactly the kind of site I build: fast, mobile-first, and easy for you to update yourself.",
    "WEBSITE_FIX": "I'd start by finding the real cause rather than patching symptoms, and I'll tell you up front if anything needs more than the budget.",
    "AUTOMATION": "I build these automations so enquiries and bookings get handled even when you're busy.",
    "OTHER": "This is right in my area: I build websites and automations for small businesses.",
}
_STEPS = {
    "WEBSITE_BUILD": [
        "Agree the pages, content and look in a short chat",
        "Design the homepage first for your approval, then build the rest",
        "Launch with speed, mobile and basic SEO checked, and show you how to edit it",
    ],
    "WEBSITE_FIX": [
        "Review the site and send you a list of what's wrong and why",
        "Fix it on a backup first so your live site stays safe",
        "Test on mobile and desktop, then put the fixes live",
    ],
    "AUTOMATION": [
        "Map the exact flow with you: what triggers what",
        "Build and test it with sample data",
        "Hand it over with a short video on how it works",
    ],
}
_STEPS["OTHER"] = _STEPS["WEBSITE_BUILD"]
_QUESTION = {
    "WEBSITE_BUILD": "do you already have a domain, hosting and your logo/photos?",
    "WEBSITE_FIX": "can you share the site URL and a screenshot of the problem?",
    "AUTOMATION": "which tools do you use today (WhatsApp Business, Google Sheets, a CRM)?",
    "OTHER": "is there a site you like the look of that I can use as a reference?",
}


def price_line(bid: Bid | None) -> str:
    if bid is None:
        return "Price: I'll give you a fixed quote after one quick question below."
    if bid.hourly:
        return f"Rate: {bid.label}. I'll send a fixed estimate of the hours after a quick look."
    return (
        f"Price: {money(bid.amount, bid.currency)} fixed, ready in {bid.days} days. Happy to split it into two "
        "milestones: half when you approve the design, half at launch."
    )


def proposal_text(fit: str, topic: str, bid: Bid | None) -> str:
    fit = fit if fit in _OPENING else "OTHER"
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(_STEPS[fit], 1))
    portfolio = settings.PORTFOLIO_URL or "[add your portfolio link]"
    return (
        f"Hi there,\n\n"
        f'I read your brief for "{topic}". {_OPENING[fit]}\n\n'
        f"How I'd approach it:\n{steps}\n\n"
        f"{price_line(bid)}\n\n"
        f"Recent work: {portfolio}\n\n"
        f"One question so I can be precise: {_QUESTION[fit]}"
    )
