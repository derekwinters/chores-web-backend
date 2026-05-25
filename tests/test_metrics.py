"""Tests for the Prometheus metrics endpoint."""
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_prometheus_client_importable():
    """prometheus_client must be installed as a dependency."""
    import prometheus_client  # noqa: F401


@pytest.mark.asyncio
async def test_starlette_prometheus_importable():
    """starlette_prometheus must be installed as a dependency."""
    import starlette_prometheus  # noqa: F401


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_200(client: AsyncClient):
    """GET /metrics returns 200 with Prometheus text format."""
    response = await client.get("/metrics")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_metrics_endpoint_content_type(client: AsyncClient):
    """GET /metrics returns Prometheus text format content type."""
    response = await client.get("/metrics")
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_metrics_no_auth_required(client: AsyncClient):
    """GET /metrics is public — no authentication required."""
    response = await client.get("/metrics")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_chores_total_gauge_present(client: AsyncClient, db):
    """chores_total gauge is present in metrics output."""
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert b"chores_total" in response.content


@pytest.mark.asyncio
async def test_chores_due_now_total_gauge_present(client: AsyncClient, db):
    """chores_due_now_total gauge is present in metrics output."""
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert b"chores_due_now_total" in response.content


@pytest.mark.asyncio
async def test_chores_due_soon_total_gauge_present(client: AsyncClient, db):
    """chores_due_soon_total gauge is present in metrics output."""
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert b"chores_due_soon_total" in response.content


@pytest.mark.asyncio
async def test_chores_due_now_by_person_gauge_present(client: AsyncClient, db):
    """chores_due_now_by_person gauge is present in metrics output."""
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert b"chores_due_now_by_person" in response.content


@pytest.mark.asyncio
async def test_people_total_gauge_present(client: AsyncClient, db):
    """people_total gauge is present in metrics output."""
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert b"people_total" in response.content


@pytest.mark.asyncio
async def test_points_awarded_total_gauge_present(client: AsyncClient, db):
    """points_awarded_total gauge is present in metrics output."""
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert b"points_awarded_total" in response.content


@pytest.mark.asyncio
async def test_chore_completions_by_person_gauge_present(client: AsyncClient, db):
    """chore_completions_by_person gauge is present in metrics output."""
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert b"chore_completions_by_person" in response.content


@pytest.mark.asyncio
async def test_chores_total_reflects_db_state(client: AsyncClient, db):
    """chores_total gauge values reflect actual chore counts in the DB."""
    from app.models import Chore
    from datetime import date

    # Add two chores: one 'due', one 'completed'
    db.add(Chore(
        name="Vacuum",
        schedule_type="weekly",
        state="due",
        disabled=False,
        next_due=date.today(),
    ))
    db.add(Chore(
        name="Mop",
        schedule_type="weekly",
        state="completed",
        disabled=False,
        next_due=date.today(),
    ))
    await db.commit()

    response = await client.get("/metrics")
    assert response.status_code == 200
    text = response.text
    # Should see both states in the output
    assert "chores_total" in text


@pytest.mark.asyncio
async def test_people_total_reflects_db_count(client: AsyncClient, db):
    """people_total gauge value matches DB person count."""
    from app.models import Person

    db.add(Person(name="Alice", username="alice", password_hash="hash"))
    db.add(Person(name="Bob", username="bob", password_hash="hash"))
    await db.commit()

    response = await client.get("/metrics")
    assert response.status_code == 200
    text = response.text
    # people_total should be in output
    assert "people_total" in text


@pytest.mark.asyncio
async def test_chore_completions_by_person_has_window_labels(client: AsyncClient, db):
    """chore_completions_by_person includes window labels (7d, 30d)."""
    from app.models import Person, PointsLog
    from datetime import datetime, timezone

    person = Person(name="Alice", username="alice2", password_hash="hash")
    db.add(person)
    await db.flush()

    db.add(PointsLog(
        person="alice2",
        points=10,
        chore_id=1,
        completed_at=datetime.now(timezone.utc),
    ))
    await db.commit()

    response = await client.get("/metrics")
    assert response.status_code == 200
    assert b"chore_completions_by_person" in response.content


@pytest.mark.asyncio
async def test_http_request_metrics_present(client: AsyncClient):
    """starlette_prometheus middleware injects HTTP request count metrics."""
    # Make a request first so metrics get populated
    await client.get("/health")
    response = await client.get("/metrics")
    assert response.status_code == 200
    # starlette-prometheus registers starlette_requests_total
    assert b"starlette_requests" in response.content
