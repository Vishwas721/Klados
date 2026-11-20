"""Call desk endpoints against the real Postgres, inside a rolled-back transaction.

Skipped when the database isn't reachable (e.g. Docker is down).
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app import main
from app.db.models import Lead
from app.db.session import engine, get_db


@pytest.fixture
def db_client(monkeypatch):
    try:
        conn = engine.connect()
    except Exception:
        pytest.skip("Postgres not reachable")
    outer = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    # Only the test's own leads should be visible to the queue
    session.query(Lead).update({Lead.opted_out: True}, synchronize_session=False)

    def override():
        yield session

    monkeypatch.setattr(main.settings, "API_KEY", None)
    main.app.dependency_overrides[get_db] = override
    try:
        yield TestClient(main.app), session
    finally:
        main.app.dependency_overrides.pop(get_db, None)
        session.close()
        outer.rollback()
        conn.close()


def make_lead(session, name, category, **kw):
    lead = Lead(
        business_name=name,
        phone_number=kw.pop("phone", f"9{abs(hash(name)) % 10**9:09d}"),
        category=category,
        city="Bengaluru",
        origin_source_url="test",
        status="AUDITED",
        **kw,
    )
    session.add(lead)
    session.flush()
    return lead


def queue_names(client):
    return [l["business_name"] for l in client.get("/api/calls/queue").json()]


def test_queue_order_and_outcomes(db_client):
    client, s = db_client
    make_lead(s, "healthy", "AUTOMATION_CANDIDATE")
    ghost = make_lead(s, "no site", "DIGITAL_GHOST")
    make_lead(s, "slow", "LAGGY_UX")
    later = make_lead(s, "call me later", "DIGITAL_GHOST", call_outcome="CALL_BACK", call_attempts=1,
                      next_call_at=datetime.now(timezone.utc) + timedelta(days=1))

    # Never-called leads by need; a callback that isn't due yet is hidden
    assert queue_names(client) == ["no site", "slow", "healthy"]

    # Interested: leaves the queue, shows in the yes list, marked responded
    res = client.post(f"/api/leads/{ghost.id}/call", json={"outcome": "INTERESTED", "notes": "wants 5 pages"})
    assert res.status_code == 200
    body = res.json()
    assert body["call_attempts"] == 1 and body["status"] == "RESPONDED" and body["call_notes"] == "wants 5 pages"
    assert "no site" not in queue_names(client)
    assert [l["business_name"] for l in client.get("/api/calls/interested").json()] == ["no site"]

    # A due callback jumps to the front
    later.next_call_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    s.flush()
    assert queue_names(client)[0] == "call me later"

    stats = client.get("/api/calls/stats").json()
    assert stats["called_today"] == 1 and stats["today_by_outcome"] == {"INTERESTED": 1}
    assert stats["interested_total"] == 1 and stats["queue"] == 3


def test_no_answer_retries_then_gives_up(db_client):
    client, s = db_client
    lead = make_lead(s, "never picks up", "DIGITAL_GHOST")
    for attempt in range(1, 4):
        body = client.post(f"/api/leads/{lead.id}/call", json={"outcome": "NO_ANSWER"}).json()
        assert body["call_attempts"] == attempt and body["next_call_at"] is not None
        lead.next_call_at = datetime.now(timezone.utc) - timedelta(minutes=1)  # pretend a day passed
        s.flush()
        assert ("never picks up" in queue_names(client)) == (attempt < 3)


def test_call_back_time_and_final_outcomes(db_client):
    client, s = db_client
    a = make_lead(s, "busy now", "DIGITAL_GHOST")
    b = make_lead(s, "no thanks", "DIGITAL_GHOST")
    when = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    body = client.post(f"/api/leads/{a.id}/call", json={"outcome": "CALL_BACK", "callback_at": when}).json()
    assert body["next_call_at"].startswith(when[:16])
    client.post(f"/api/leads/{b.id}/call", json={"outcome": "NOT_INTERESTED"})
    assert queue_names(client) == []
    assert client.post(f"/api/leads/{b.id}/call", json={"outcome": "MAYBE"}).status_code == 422
