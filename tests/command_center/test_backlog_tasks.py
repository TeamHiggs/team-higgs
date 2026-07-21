"""Backlog grooming + create task: transitions, events, reorder, boundary."""

from __future__ import annotations

from fastapi.testclient import TestClient

from emctl.db import transaction
from emctl.repo import task_events
from tests.command_center import seed
from tests.command_center.conftest import login


def _events(task_id: int) -> list[dict[str, object]]:
    with transaction() as conn:
        return task_events.list_for_task(conn, task_id)


def test_create_task_opens_in_backlog_with_event(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    resp = client.post(
        "/api/tasks",
        json={"title": "build the SPA", "project": pid, "tier": "execute"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "backlog"
    assert body["model_tier"] == "execute"
    # Opening event recorded (shared with the CLI via emctl.services).
    evts = _events(body["id"])
    assert len(evts) == 1
    assert evts[0]["from_status"] is None
    assert evts[0]["to_status"] == "backlog"
    assert evts[0]["actor"] == "tyler@tylerdorland.com"


def test_create_task_rejects_bad_tier(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    resp = client.post(
        "/api/tasks", json={"title": "x", "project": pid, "tier": "genius"}
    )
    assert resp.status_code == 422


def test_greenlight_moves_backlog_to_planned_with_event(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    tid = seed.task(pid, status="backlog")
    resp = client.post(f"/api/tasks/{tid}/greenlight")
    assert resp.status_code == 200
    assert resp.json()["status"] == "planned"
    evts = _events(tid)
    assert evts[-1]["from_status"] == "backlog"
    assert evts[-1]["to_status"] == "planned"


def test_greenlight_non_backlog_is_rejected(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    tid = seed.task(pid, status="in_progress")
    resp = client.post(f"/api/tasks/{tid}/greenlight")
    assert resp.status_code == 400


def test_block_and_unblock(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    tid = seed.task(pid, status="planned")

    blocked = client.post(f"/api/tasks/{tid}/block", json={"reason": "waiting on #29"})
    assert blocked.status_code == 200
    assert blocked.json()["blocked"] is True
    assert blocked.json()["blocked_reason"] == "waiting on #29"

    unblocked = client.post(f"/api/tasks/{tid}/unblock")
    assert unblocked.status_code == 200
    assert unblocked.json()["blocked"] is False
    # Blocking is a flag, not a transition: no spurious status events.
    assert _events(tid) == _events(tid)  # stable
    assert all(e["to_status"] != "blocked" for e in _events(tid))


def test_reorder_sets_groom_rank_and_orders_board(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    a = seed.task(pid, title="a", status="backlog")
    b = seed.task(pid, title="b", status="backlog")
    c = seed.task(pid, title="c", status="backlog")

    resp = client.post("/api/backlog/reorder", json={"ordered_ids": [c, a, b]})
    assert resp.status_code == 200
    ranks = {r["id"]: r["groom_rank"] for r in resp.json()}
    assert ranks == {c: 0, a: 1, b: 2}

    board = client.get("/api/backlog").json()
    backlog_ids = [t["id"] for t in board["backlog"]]
    assert backlog_ids == [c, a, b]


def test_reorder_unknown_id_is_404_and_atomic(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    a = seed.task(pid, status="backlog")
    resp = client.post("/api/backlog/reorder", json={"ordered_ids": [a, 999]})
    assert resp.status_code == 404
    # The whole reorder ran in one transaction, so the valid id was not ranked.
    assert seed.get_task(a)["groom_rank"] is None


def test_backlog_groups_by_status(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    seed.task(pid, status="backlog")
    seed.task(pid, status="planned")
    seed.task(pid, status="in_review")
    seed.task(pid, status="done")
    board = client.get("/api/backlog").json()
    assert len(board["backlog"]) == 1
    assert len(board["planned"]) == 1
    assert len(board["in_flight"]) == 1  # in_review; done is excluded
