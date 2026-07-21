"""Notes (append-only) and read-only state surfaces."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.command_center import seed
from tests.command_center.conftest import ALLOWED_EMAIL, login


def test_note_append_and_list_newest_first(client: TestClient) -> None:
    login(client)
    assert client.post("/api/notes", json={"body": "first"}).status_code == 201
    assert client.post("/api/notes", json={"body": "second"}).status_code == 201
    notes = client.get("/api/notes").json()
    assert [n["body"] for n in notes] == ["second", "first"]
    # Author is recorded server-side from the session, not the client.
    assert all(n["author"] == ALLOWED_EMAIL for n in notes)


def test_note_rejects_empty_body(client: TestClient) -> None:
    login(client)
    assert client.post("/api/notes", json={"body": ""}).status_code == 422


def test_read_only_prs_and_runs(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    seed.pr(pid, github_pr=21)
    prs = client.get("/api/prs").json()
    assert len(prs) == 1
    assert prs[0]["github_pr"] == 21
    # Runs surface returns a list (possibly empty) without error.
    assert client.get("/api/runs").status_code == 200


def test_improvement_reads_ledgers(client: TestClient) -> None:
    login(client)
    body = client.get("/api/improvement").json()
    assert set(body) == {"retros", "learnings", "debt"}
