"""process_h3_cell control flow, with scraping, auditing and the DB stubbed out."""

import pytest

from app import worker
from app.services.discovery.coverage import mark_seen, unseen_cells
from app.services.discovery.geo_grid import generate_city_cells


class FakeQueue:
    jobs: list = []

    def __init__(self, *args, **kwargs):
        pass

    def enqueue(self, func, args, job_timeout):
        FakeQueue.jobs.append(args)


class FakeAuditor:
    closed = 0

    def audit(self, url):
        return {"category": "DIGITAL_GHOST"}

    def close(self):
        FakeAuditor.closed += 1


class FakeSession:
    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


@pytest.fixture
def stubbed(monkeypatch, fake_redis):
    FakeQueue.jobs = []
    counter = {"today": 0}
    calls = {"exhausted": 0, "history": []}

    monkeypatch.setattr(worker, "redis_conn", fake_redis)
    monkeypatch.setattr(worker, "Queue", FakeQueue)
    monkeypatch.setattr(worker, "SessionLocal", FakeSession)
    monkeypatch.setattr(worker, "get_leads_collected_today", lambda r=None: counter["today"])
    monkeypatch.setattr(worker, "is_duplicate_lead", lambda *a, **k: False)
    monkeypatch.setattr(worker, "SiteAuditor", FakeAuditor)
    monkeypatch.setattr(worker.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        worker, "_update_search_history", lambda db, q, c, n: calls["history"].append(n)
    )
    monkeypatch.setattr(worker, "_handle_exhaustion", lambda q, c: calls.__setitem__("exhausted", calls["exhausted"] + 1))

    def insert(db, place, hex_id, audit, city):
        counter["today"] += 1
        return place["business_name"]

    monkeypatch.setattr(worker, "_insert_lead_on_conflict_do_nothing", insert)
    monkeypatch.setattr(worker, "increment_leads_collected_today", lambda r=None: counter["today"])
    return fake_redis, counter, calls


def _places(n):
    return [
        {"business_name": f"Biz {i}", "phone_number": f"98450{i:05d}", "website_url": None}
        for i in range(n)
    ]


def test_thin_cell_expands_into_unseen_neighbours(monkeypatch, stubbed):
    fake_redis, _, calls = stubbed
    monkeypatch.setattr(worker, "extract_places", lambda *a, **k: _places(3))
    cell = generate_city_cells("Mysuru")[0]
    mark_seen(fake_redis, "Mysuru", "Gyms", [cell])

    result = worker.process_h3_cell(cell, "Gyms", "Mysuru")

    assert result["leads_processed"] == 3
    assert len(result["expanded_cells"]) == 2
    assert all(c not in unseen_cells(fake_redis, "Mysuru", "Gyms") for c in result["expanded_cells"])
    assert calls["exhausted"] == 0
    assert calls["history"] == [3]


def test_daily_limit_mid_batch_stops_expansion_and_releases_cell(monkeypatch, stubbed):
    fake_redis, counter, calls = stubbed
    counter["today"] = worker.DAILY_LIMIT - 2
    monkeypatch.setattr(worker, "extract_places", lambda *a, **k: _places(5))
    cell = generate_city_cells("Mysuru")[0]
    mark_seen(fake_redis, "Mysuru", "Gyms", [cell])

    result = worker.process_h3_cell(cell, "Gyms", "Mysuru")

    assert result["status"] == "daily_limit_reached"
    assert result["leads_processed"] == 2
    assert result["expanded_cells"] == []
    assert FakeQueue.jobs == []
    assert cell in unseen_cells(fake_redis, "Mysuru", "Gyms")
    assert calls["exhausted"] == 0


def test_zero_lead_cell_still_resolves_search_history(monkeypatch, stubbed):
    _, _, calls = stubbed
    monkeypatch.setattr(worker, "extract_places", lambda *a, **k: [])

    worker.process_h3_cell(generate_city_cells("Mysuru")[0], "Gyms", "Mysuru")

    assert calls["history"] == [0]


def test_scrape_error_does_not_crash_job(monkeypatch, stubbed):
    def boom(*a, **k):
        raise RuntimeError("camoufox died")

    monkeypatch.setattr(worker, "extract_places", boom)
    result = worker.process_h3_cell(generate_city_cells("Mysuru")[0], "Gyms", "Mysuru")
    assert result["leads_processed"] == 0


def test_exhaustion_only_when_city_fully_covered(monkeypatch, stubbed):
    fake_redis, _, calls = stubbed
    monkeypatch.setattr(worker, "extract_places", lambda *a, **k: [])
    cells = generate_city_cells("Udupi Manipal")
    mark_seen(fake_redis, "Udupi Manipal", "Gyms", cells)

    # Max depth, nothing left unscanned: genuinely exhausted
    worker.process_h3_cell(cells[0], "Gyms", "Udupi Manipal", worker.MAX_EXPANSION_DEPTH)
    assert calls["exhausted"] == 1

    # Max depth with plenty of the city left: not exhausted
    worker.process_h3_cell(generate_city_cells("Mysuru")[0], "Gyms", "Mysuru", worker.MAX_EXPANSION_DEPTH)
    assert calls["exhausted"] == 1


def test_fallback_audit_trims_call_log():
    audit = worker._fallback_audit("https://x.in", RuntimeError("Page.goto: boom\nCall log:\n - navigating"))
    assert audit["operational_bottleneck"] == "Audit failed: Page.goto: boom"
    assert audit["category"] == "LAGGY_UX"


def test_auditor_closed_even_when_cell_errors(monkeypatch, stubbed):
    FakeAuditor.closed = 0
    monkeypatch.setattr(worker, "extract_places", lambda *a, **k: _places(1))

    def explode(db, q, c, n):
        raise RuntimeError("db down")

    monkeypatch.setattr(worker, "_update_search_history", explode)
    with pytest.raises(RuntimeError):
        worker.process_h3_cell(generate_city_cells("Mysuru")[0], "Gyms", "Mysuru")
    assert FakeAuditor.closed == 1
