"""Decide whether a post is someone asking for work, what kind, and how good.

Pure functions over RawPost so they're easy to test. `assess()` returns None
for posts that aren't requests (freelancers advertising themselves, chatter
without a hiring intent); otherwise a fit, a 0-100 score, and the short
reasons behind it ("signals") the dashboard shows.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re

from app.services.intent.base import RawPost

# Rough INR→USD, only used to compare budgets on one scale
INR_TO_USD = 1 / 88
# A Freelancer.com hourly budget is a rate; assume a small job's hours
HOURLY_JOB_HOURS = 20


def _phrases(*words: str) -> list[tuple[str, re.Pattern]]:
    return [(w, re.compile(r"(?<![\w-])" + re.escape(w).replace(r"\ ", r"[\s-]?") + r"(?![\w-])", re.I)) for w in words]


BUILD_STRONG = _phrases(
    "new website", "build a website", "build my website", "build our website", "create a website",
    "make a website", "website for my", "website for our", "website development", "website design",
    "web design", "landing page", "ecommerce", "e-commerce", "online store", "shopify", "woocommerce",
    "wordpress", "webflow", "wix", "squarespace", "business website", "portfolio website",
    "one page website", "static site",
)
BUILD_WEAK = _phrases("website", "web site", "web app", "webpage", "web developer", "web designer")
FIX_STRONG = _phrases(
    "redesign", "revamp", "fix my website", "fix our website", "website fix", "bug fix", "fix bugs",
    "speed up", "slow website", "site is slow", "page speed", "pagespeed", "core web vitals", "migrate",
    "migration", "update my website", "update our website", "not working", "broken", "mobile responsive",
    "make it responsive", "ssl", "seo audit", "website maintenance", "hacked", "malware",
)
AUTOMATION_STRONG = _phrases(
    "automation", "automate", "chatbot", "whatsapp", "booking system", "online booking",
    "appointment booking", "appointment", "crm", "zapier", "n8n", "make.com", "workflow", "ai agent",
    "lead capture", "payment gateway", "razorpay", "google sheets", "integration",
)
EXCLUDE = _phrases(
    "android app", "ios app", "mobile app", "flutter", "react native", "blockchain", "crypto", "nft",
    "smart contract", "data entry", "essay", "homework", "assignment", "thesis", "dissertation",
    "game development", "game dev", "unreal engine", "video editing", "voice over", "logo design", "translation",
    "transcription", "trading bot", "forex", "casino", "betting", "onlyfans", "ghostwriter", "academic",
    # Agencies hiring sales/marketing help are not clients
    "sales closer", "closer", "lead generation", "commission", "commission based", "cold calling",
    "appointment setter", "telemarketing", "b2b sales", "sales representative", "sales rep",
    "business development", "link building", "backlinks", "guest post",
    # Background-check gigs that mention "website" in passing
    "verification needed", "background check", "pre-employment",
)
LOCAL = _phrases(
    "india", "indian", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "pune", "chennai",
    "kolkata", "ahmedabad", "kochi", "mysore", "mysuru", "karnataka", "inr", "rupees", "lakh",
)
SMALL_BIZ_RE = re.compile(
    r"\b(my|our)\s+(own\s+)?(shop|store|clinic|salon|restaurant|cafe|café|gym|studio|business|startup|"
    r"company|practice|bakery|boutique|hotel|school|academy|agency|brand)\b",
    re.I,
)

OFFERING_RE = re.compile(
    r"\[\s*for\s*hire\s*\]|^\s*seeking work\b|\bhire me\b|\bi(?:'m| am) offering\b|"
    r"\bavailable for (?:freelance|new) (?:work|projects)\b|\bi(?:'m| am) a (?:freelance )?"
    r"(?:web )?(?:developer|designer) (?:with|offering|available)\b",
    re.I | re.M,
)
TAGGED_REQUEST_RE = re.compile(r"\[\s*(hiring|task|paid|request)\s*\]|^\s*seeking freelancer", re.I | re.M)
_WHAT = (
    r"\b(web ?sites?|web ?developer|web ?designer|web ?dev|developer|designer|freelancer|agency|someone|"
    r"landing page|online store|e-?commerce|shopify|wordpress)\b"
)
# Untagged posts count only when someone asks in the first person (or the
# title opens with the ask), so "how I built a website business" doesn't.
TITLE_ASK_RE = re.compile(r"^\s*(looking for|need|needed|seeking|hiring|wanted)\b[^.\n?]{0,60}?" + _WHAT, re.I)
INTENT_RES = [
    re.compile(
        r"\b(i|we)(?:'m|'re|\s+am|\s+are)?\s+(?:currently\s+|really\s+|urgently\s+)?"
        r"(looking for|need|want|seeking|searching for|trying to find|hiring|would like)\b[^.\n?]{0,60}?" + _WHAT,
        re.I,
    ),
    re.compile(r"\b(can|could) (anyone|someone|you) (build|make|create|design|fix|recommend)\b", re.I),
    re.compile(r"\brecommend(ations?)?\b[^.\n?]{0,25}\b(web|website|developer|designer|agency)\b", re.I),
    re.compile(r"\bwho (can|could) (build|make|design|fix)\b", re.I),
]

INR_RE = re.compile(r"(?:₹|\brs\.?|\binr)\s?(\d[\d,]*(?:\.\d+)?)\s?(k|lakhs?|l)?\b", re.I)
INR_SUFFIX_RE = re.compile(r"\b(\d[\d,]*(?:\.\d+)?)\s?(k|lakhs?)?\s?(?:inr|rupees|rs)\b", re.I)
USD_RE = re.compile(r"(?:\$|\busd)\s?(\d[\d,]*(?:\.\d+)?)\s?(k|m)?\b", re.I)
# Larger amounts are revenue talk ("a $1M business"), not a project budget
MAX_PLAUSIBLE_BUDGET_USD = 50_000


@dataclass
class Assessment:
    fit: str
    score: int
    signals: list[str] = field(default_factory=list)
    is_local: bool = False
    budget_usd: float | None = None


def _hits(patterns, text: str) -> list[str]:
    return [label for label, rx in patterns if rx.search(text)]


def _amount(number: str, suffix: str | None) -> float:
    value = float(number.replace(",", ""))
    suffix = (suffix or "").lower()
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    elif suffix.startswith("l"):
        value *= 100_000
    return value


def budget_from_text(text: str) -> float | None:
    """Largest money amount mentioned in the post, in USD."""
    amounts = [_amount(n, s) * INR_TO_USD for n, s in INR_RE.findall(text)]
    amounts += [_amount(n, s) * INR_TO_USD for n, s in INR_SUFFIX_RE.findall(text)]
    amounts += [_amount(n, s) for n, s in USD_RE.findall(text)]
    amounts = [a for a in amounts if 0 < a <= MAX_PLAUSIBLE_BUDGET_USD]
    return max(amounts) if amounts else None


def marketplace_budget_usd(post: RawPost) -> float | None:
    top = post.budget_max or post.budget_min
    if not top:
        return None
    rate = post.usd_rate
    if rate is None:
        rate = INR_TO_USD if (post.currency or "").upper() == "INR" else 1.0
    usd = float(top) * float(rate)
    if post.hints.get("project_type") == "hourly":
        usd *= HOURLY_JOB_HOURS
    return usd


def is_request(post: RawPost) -> bool:
    head = f"{post.title}\n{post.body[:400]}"
    if post.source == "freelancer":
        return True  # every project there is a client asking
    if post.source == "hackernews":
        return bool(re.match(r"\s*seeking freelancer", post.body, re.I))
    if OFFERING_RE.search(head):
        return False
    if TAGGED_REQUEST_RE.search(post.title):
        return True
    flair = (post.hints.get("flair") or "").lower()
    if flair in ("hiring", "task"):
        return True
    if post.source == "rss":
        return True  # feeds are chosen as job boards
    if TITLE_ASK_RE.search(post.title):
        return True
    text = f"{post.title}\n{post.body[:800]}"
    return any(rx.search(text) for rx in INTENT_RES)


def assess(post: RawPost, now: datetime | None = None) -> Assessment | None:
    if not is_request(post):
        return None

    now = now or datetime.now(timezone.utc)
    text = f"{post.title}\n{post.body}"
    signals: list[str] = []

    build = _hits(BUILD_STRONG, text)
    fix = _hits(FIX_STRONG, text)
    automation = _hits(AUTOMATION_STRONG, text)
    weak = _hits(BUILD_WEAK, text)

    weights = {
        "WEBSITE_FIX": 15 * len(fix),
        "AUTOMATION": 15 * len(automation),
        "WEBSITE_BUILD": 15 * len(build) + (6 if weak else 0),
    }
    # Ties go to the more specific ask: fixing beats automating beats building
    fit = max(weights, key=lambda k: (weights[k], ["WEBSITE_BUILD", "AUTOMATION", "WEBSITE_FIX"].index(k)))
    relevance = weights[fit]
    if relevance == 0:
        fit = "OTHER"
    matched = {"WEBSITE_FIX": fix, "AUTOMATION": automation, "WEBSITE_BUILD": build or weak[:1]}.get(fit, [])
    signals += matched[:3]
    score = min(45, relevance)

    tagged = post.source == "freelancer" or bool(TAGGED_REQUEST_RE.search(post.title))
    if tagged:
        score += 10

    budget_usd = marketplace_budget_usd(post) if post.budget_max or post.budget_min else budget_from_text(text)
    if budget_usd is None:
        score += 5
    elif budget_usd < 30:
        score -= 10
        signals.append("tiny budget")
    elif budget_usd < 100:
        score += 3
    elif budget_usd < 300:
        score += 8
    elif budget_usd < 1000:
        score += 14
        signals.append("good budget")
    else:
        score += 20
        signals.append("big budget")
    if post.hints.get("project_type") == "hourly":
        signals.append("hourly")

    if post.posted_at:
        age_h = (now - post.posted_at).total_seconds() / 3600
        if age_h < 2:
            score += 15
            signals.append("just posted")
        elif age_h < 12:
            score += 10
        elif age_h < 48:
            score += 5
    else:
        score += 3

    is_local = bool(_hits(LOCAL, text)) or (post.currency or "").upper() == "INR"
    if is_local:
        score += 10
        signals.append("India")

    if SMALL_BIZ_RE.search(text):
        score += 8
        signals.append("small business")

    if post.bid_count is not None:
        if post.bid_count > 50:
            score -= 10
            signals.append(f"{post.bid_count} bids")
        elif post.bid_count > 20:
            score -= 5
            signals.append(f"{post.bid_count} bids")
        elif post.bid_count < 5:
            score += 5
            signals.append("few bids")

    excluded = _hits(EXCLUDE, text)
    if excluded:
        score -= min(60, 30 * len(excluded))
        signals.append(f"off-target: {excluded[0]}")

    return Assessment(
        fit=fit,
        score=max(0, min(100, score)),
        signals=signals,
        is_local=is_local,
        budget_usd=round(budget_usd, 2) if budget_usd is not None else None,
    )
