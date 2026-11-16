"""Request radar: parsers, scoring and the poll loop, with the network stubbed."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app import intent_poller
from app.services.intent import freelancer, hackernews, poller, reddit, rss, websearch
from app.services.intent.base import RawPost, SourceRateLimited, html_to_text
from app.services.intent.scoring import assess, budget_from_text
from app.services.intent.writer import template_reply

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def post(title, body="", source="reddit", **kw) -> RawPost:
    return RawPost(source=source, external_id="x", url="https://example.com", title=title, body=body,
                   posted_at=kw.pop("posted_at", NOW - timedelta(hours=1)), **kw)


# ── scoring ──────────────────────────────────────────────────────────────────

def test_hiring_post_for_a_small_business_site_scores_high():
    a = assess(post("[Hiring] Website for my bakery in Bengaluru",
                    "Need a simple website with online ordering. Budget ₹25,000."), now=NOW)
    assert a is not None
    assert a.fit == "WEBSITE_BUILD"
    assert a.is_local
    assert a.score >= 70
    assert "small business" in a.signals


def test_freelancers_advertising_themselves_are_skipped():
    assert assess(post("[For Hire] Full-stack web developer, 5 years"), now=NOW) is None
    hn = post("SEEKING WORK | Remote", "SEEKING WORK | Remote\nI build websites", source="hackernews")
    assert assess(hn, now=NOW) is None


def test_hn_seeking_freelancer_is_a_request():
    hn = post("SEEKING FREELANCER | Remote", "SEEKING FREELANCER | Remote\nNeed a Shopify store redesign",
              source="hackernews")
    a = assess(hn, now=NOW)
    assert a is not None and a.fit == "WEBSITE_FIX"


def test_general_subreddit_post_needs_hiring_intent():
    assert assess(post("What CRM do you all use?", "Curious about tools."), now=NOW) is None
    a = assess(post("Can anyone recommend a web designer?", "Our clinic's site is ancient."), now=NOW)
    assert a is not None


def test_off_target_work_is_pushed_down():
    a = assess(post("[Hiring] Flutter mobile app for crypto trading", "Need android app + website"), now=NOW)
    assert a is not None
    assert any(s.startswith("off-target") for s in a.signals)
    assert a.score < 30


def test_agencies_hiring_sales_help_are_pushed_down():
    a = assess(post("International Website Sales Closer Needed", "Commission on every new website we sell",
                    source="freelancer"), now=NOW)
    assert a.score < 20


def test_untagged_posts_need_a_first_person_ask():
    assert assess(post("How I'd build a $1M website business from scratch",
                       "Most people want a website but never ship one."), now=NOW) is None
    assert assess(post("Looking for a web developer in Pune", ""), now=NOW) is not None
    assert assess(post("Advice?", "We are looking for an agency to redo our store site"), now=NOW) is not None


def test_revenue_talk_is_not_a_budget():
    assert budget_from_text("grew it to $1M ARR") is None


def test_automation_and_fix_fits():
    auto = assess(post("[Task] WhatsApp booking system for salon", "Want appointment automation"), now=NOW)
    assert auto.fit == "AUTOMATION"
    fix = assess(post("[Hiring] Fix my WordPress site, it's broken and slow", ""), now=NOW)
    assert fix.fit == "WEBSITE_FIX"


def test_freelancer_budget_uses_exchange_rate_and_bids():
    p = post("Need a landing page", "Simple landing page for product", source="freelancer",
             budget_min=10000, budget_max=20000, currency="INR", usd_rate=0.0114, bid_count=3)
    a = assess(p, now=NOW)
    assert a.budget_usd == pytest.approx(228, abs=1)
    assert "few bids" in a.signals and a.is_local


def test_old_posts_get_no_freshness_bonus():
    fresh = assess(post("[Hiring] Website for my gym"), now=NOW)
    stale = assess(post("[Hiring] Website for my gym", posted_at=NOW - timedelta(days=5)), now=NOW)
    assert fresh.score > stale.score


def test_budget_from_text_handles_inr_usd_and_suffixes():
    assert budget_from_text("budget $1.5k") == 1500
    assert budget_from_text("around 2 lakh INR") == pytest.approx(200000 / 88)
    assert budget_from_text("Rs 15,000 max") == pytest.approx(15000 / 88)
    assert budget_from_text("no budget given") is None


def test_template_reply_mentions_topic():
    reply = template_reply("WEBSITE_BUILD", "[Hiring] Website for my bakery", "sam")
    assert reply.startswith("Hi sam,") and "website for my bakery" in reply


# ── parsers ──────────────────────────────────────────────────────────────────

FREELANCER_PAYLOAD = {
    "status": "success",
    "result": {"projects": [{
        "id": 40820279, "title": "Website for dental clinic", "seo_url": "website-design/dental-40820279",
        "description": "Need a 5 page website", "time_submitted": 1794810000, "type": "fixed",
        "currency": {"code": "INR", "exchange_rate": 0.0114, "country": "IN"},
        "budget": {"minimum": 12500, "maximum": 37500}, "bid_stats": {"bid_count": 7},
        "jobs": [{"name": "Website Design"}, {"name": "PHP"}],
    }]},
}


def test_parse_freelancer_projects():
    [p] = freelancer.parse_projects(FREELANCER_PAYLOAD)
    assert p.url == "https://www.freelancer.com/projects/website-design/dental-40820279"
    assert p.currency == "INR" and p.bid_count == 7 and p.channel == "Website Design, PHP"
    assert p.posted_at.year == 2026


REDDIT_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
 <entry>
  <author><name>/u/bakerbee</name></author>
  <category term="forhire" label="r/forhire"/>
  <content type="html">&lt;div&gt;&lt;p&gt;Need a site for my bakery&lt;/p&gt;&lt;/div&gt; submitted by /u/bakerbee [link] [comments]</content>
  <id>t3_1abcde</id>
  <link href="https://www.reddit.com/r/forhire/comments/1abcde/hiring_site/"/>
  <published>2026-11-16T10:00:00+00:00</published>
  <title>[Hiring] Website for my bakery</title>
 </entry>
</feed>"""


def test_parse_reddit_atom():
    [p] = reddit.parse_atom(REDDIT_ATOM)
    assert p.external_id == "1abcde" and p.author == "bakerbee" and p.channel == "r/forhire"
    assert p.body == "Need a site for my bakery"


def test_parse_reddit_listing():
    payload = {"data": {"children": [{"data": {
        "id": "zz1", "title": "[Task] Fix WordPress", "selftext": "it's broken", "author": "a",
        "permalink": "/r/slavelabour/comments/zz1/x/", "created_utc": 1794810000, "subreddit": "slavelabour",
        "link_flair_text": "Task"}}]}}
    [p] = reddit.parse_listing(payload)
    assert p.url.startswith("https://www.reddit.com/r/slavelabour") and p.hints["flair"] == "Task"


def test_parse_hn_thread():
    payload = {"title": "Ask HN: Freelancer? Seeking freelancer? (November 2026)", "children": [
        {"id": 1, "author": "acme", "created_at_i": 1794810000,
         "text": "SEEKING FREELANCER | Remote<p>Need a Webflow site &amp; CMS"},
        {"id": 2, "author": "gone", "text": None},
    ]}
    [p] = hackernews.parse_thread(payload)
    assert p.title == "SEEKING FREELANCER | Remote"
    assert "Webflow site & CMS" in p.body
    assert p.channel.startswith("Freelancer? Seeking freelancer?")


def test_parse_rss_and_atom_feeds():
    rss_xml = """<rss><channel><item><title>Need landing page</title><link>https://jobs.example/1</link>
    <description>&lt;b&gt;Budget&lt;/b&gt; $300</description><pubDate>Mon, 16 Nov 2026 09:00:00 +0000</pubDate>
    </item></channel></rss>"""
    [p] = rss.parse_feed(rss_xml, "https://www.jobs.example/feed")
    assert p.channel == "jobs.example" and p.body == "Budget $300" and p.posted_at.day == 16
    [a] = rss.parse_feed(REDDIT_ATOM, "https://reddit.com/x.rss")
    assert a.title == "[Hiring] Website for my bakery"


def test_parse_searxng_skips_covered_domains():
    payload = {"results": [
        {"url": "https://www.reddit.com/r/x", "title": "dup"},
        {"url": "https://forum.example.in/t/need-website", "title": "Need website for shop",
         "content": "looking for a web developer", "publishedDate": "2026-11-15T08:00:00"},
    ]}
    [p] = websearch.parse_results(payload, "q")
    assert p.channel == "forum.example.in" and p.posted_at.tzinfo is not None


def test_html_to_text_keeps_paragraphs():
    assert html_to_text("a<p>b<br>c &amp; d") == "a\nb\nc & d"


def test_freelancer_fetch_dedupes_across_queries(monkeypatch):
    monkeypatch.setattr(freelancer.settings, "FREELANCER_QUERIES", ["website", "wordpress"])
    calls = []

    def handler(request):
        calls.append(request.url.params["query"])
        return httpx.Response(200, json=FREELANCER_PAYLOAD)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        posts = freelancer.fetch(client)
    assert calls == ["website", "wordpress"] and len(posts) == 1


def test_reddit_fetches_hiring_and_community_feeds_separately(monkeypatch):
    monkeypatch.setattr(reddit.settings, "REDDIT_CLIENT_ID", None)
    monkeypatch.setattr(reddit, "ANON_GAP_S", 0)
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, text=REDDIT_ATOM)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        posts = reddit.fetch(client)
    assert paths == ["/r/forhire+slavelabour+freelance_forhire+hiring/new/.rss",
                     "/r/smallbusiness+Entrepreneur+indianstartups+bangalore+india/new/.rss"]
    assert len(posts) == 2


def test_reddit_rate_limit_raises(monkeypatch):
    monkeypatch.setattr(reddit.settings, "REDDIT_CLIENT_ID", None)
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429))) as client:
        with pytest.raises(SourceRateLimited):
            reddit.fetch(client)


# ── poll loop ────────────────────────────────────────────────────────────────

class FakeDb:
    def close(self):
        pass

    def rollback(self):
        pass


def test_poll_source_records_success(fake_redis, monkeypatch):
    spec = poller.SOURCES["hackernews"]
    monkeypatch.setitem(poller.SOURCES, "hackernews", spec.__class__(**{**spec.__dict__, "fetch": lambda c, since: [post("t")]}))
    monkeypatch.setattr(poller, "save_posts", lambda db, posts, now=None: ["row"])
    monkeypatch.setattr(poller, "enrich_and_alert", lambda db, rows: None)

    result = poller.poll_source("hackernews", fake_redis, session_factory=FakeDb)
    assert result == {"source": "hackernews", "status": "ok", "fetched": 1, "new": 1}
    st = poller.source_status(fake_redis, "hackernews")
    assert st["state"] == "ok" and st["last_new"] == "1" and st["total_new"] == "1"


def test_poll_source_backs_off_after_rate_limit(fake_redis, monkeypatch):
    def limited(client, since=None):
        raise SourceRateLimited("reddit", 900)

    spec = poller.SOURCES["reddit"]
    monkeypatch.setitem(poller.SOURCES, "reddit", spec.__class__(**{**spec.__dict__, "fetch": limited}))
    assert poller.poll_source("reddit", fake_redis)["status"] == "rate_limited"
    assert fake_redis.ttls["intent:backoff:reddit"] == 900
    assert poller.poll_source("reddit", fake_redis)["status"] == "backing_off"


def test_unconfigured_sources_dont_fetch(fake_redis, monkeypatch):
    monkeypatch.setattr(websearch.settings, "SEARXNG_URL", None)
    assert poller.poll_source("web", fake_redis)["status"] == "not_configured"


def test_run_once_polls_due_and_requested_sources(fake_redis, monkeypatch):
    polled = []
    monkeypatch.setattr(intent_poller, "poll_source", lambda name, r: polled.append(name) or {})
    intent_poller.run_once(fake_redis, now=1_000_000_000)
    assert set(polled) == set(poller.SOURCES)  # never polled → all due

    for name in poller.SOURCES:
        fake_redis.hset(f"intent:status:{name}", {"last_attempt_at": datetime.fromtimestamp(1_000_000_000, timezone.utc).isoformat()})
    polled.clear()
    poller.request_poll(fake_redis, "rss")
    intent_poller.run_once(fake_redis, now=1_000_000_005)
    assert polled == ["rss"]


# ── bids ─────────────────────────────────────────────────────────────────────

from app.services.intent.bidding import proposal_text, suggest_bid  # noqa: E402


def test_bid_sits_a_third_into_the_range_and_rounds():
    bid = suggest_bid(budget_min=12500, budget_max=37500, currency="INR", hourly=False,
                      fit="WEBSITE_BUILD", budget_usd=428)
    assert bid.amount == 21500  # 12,500 + 35% of 25,000 = 21,250 → nearest 500
    assert bid.days == 7 and bid.label == "₹21,500 · 7 days"


def test_bid_never_goes_under_the_minimum_and_handles_hourly():
    flat = suggest_bid(budget_min=30, budget_max=30, currency="USD", hourly=False, fit="WEBSITE_FIX", budget_usd=30)
    assert flat.amount == 30 and flat.days == 3
    hourly = suggest_bid(budget_min=15, budget_max=25, currency="USD", hourly=True, fit="AUTOMATION", budget_usd=500)
    assert hourly.hourly and hourly.days is None and hourly.label == "$20/hour"
    assert suggest_bid(budget_min=None, budget_max=None, currency="USD", hourly=False, fit="OTHER", budget_usd=None) is None


def test_proposal_has_plan_price_portfolio_and_question(monkeypatch):
    from app.services.intent import bidding
    monkeypatch.setattr(bidding.settings, "PORTFOLIO_URL", "https://me.example")
    bid = suggest_bid(budget_min=100, budget_max=300, currency="USD", hourly=False, fit="WEBSITE_BUILD", budget_usd=300)
    text = proposal_text("WEBSITE_BUILD", "a site for my bakery", bid)
    assert 'brief for "a site for my bakery".' in text and "1. " in text and "3. " in text
    assert "Price: $170 fixed, ready in 7 days" in text
    assert "Recent work: https://me.example" in text and text.rstrip().endswith("?")


def test_freelancer_fetch_pages_back_to_since(monkeypatch):
    monkeypatch.setattr(freelancer.settings, "FREELANCER_QUERIES", ["website"])
    monkeypatch.setattr(freelancer, "PAGE_GAP_S", 0)
    base = 1794810000

    def page(offset):
        # each page: 50 projects, 10 min apart, getting older with the offset
        return {"result": {"projects": [
            {"id": offset + i + 1, "title": f"p{offset + i}", "time_submitted": base - (offset + i) * 600}
            for i in range(50)
        ]}}

    offsets = []

    def handler(request):
        off = int(request.url.params["offset"])
        offsets.append(off)
        return httpx.Response(200, json=page(off))

    since = datetime.fromtimestamp(base - 70 * 600, timezone.utc)  # ~ project 70
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        posts = freelancer.fetch(client, since)
    assert offsets == [0, 50]  # second page reaches past `since`, so it stops
    assert len(posts) == 100

    offsets.clear()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        freelancer.fetch(client, None)
    assert offsets == [0]  # first run: newest page only
