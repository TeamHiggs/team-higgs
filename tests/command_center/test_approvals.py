"""Approval queue: composition, decisions, artifact preview, PR merge."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.command_center import seed
from tests.command_center.conftest import FakeMerger, login


def test_queue_composes_all_kinds(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    seed.pr(pid, github_pr=7)
    seed.artifact(pid, type_="mockup", path="docs/design/command-center-v1.html")
    seed.decision(title="use OIDC")
    seed.question(pid, body="which host?")

    items = client.get("/api/approvals").json()["items"]
    kinds = sorted(i["kind"] for i in items)
    assert kinds == ["artifact", "decision", "pr", "question"]


def test_queue_excludes_already_decided_pr(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    seed.pr(pid, github_pr=8, tyler_decision="approve")
    items = client.get("/api/approvals").json()["items"]
    assert [i for i in items if i["kind"] == "pr"] == []


def test_approve_artifact_writes_status(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    aid = seed.artifact(pid, path="README.md")
    resp = client.post(
        "/api/approvals/decision",
        json={"kind": "artifact", "id": aid, "verdict": "approve", "note": "ship"},
    )
    assert resp.status_code == 200
    # No longer proposed, so it drops out of the queue.
    items = client.get("/api/approvals").json()["items"]
    assert [i for i in items if i["kind"] == "artifact"] == []


def test_reject_pr_sets_decision_and_status(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    pr_id = seed.pr(pid, github_pr=9)
    resp = client.post(
        "/api/approvals/decision",
        json={"kind": "pr", "id": pr_id, "verdict": "reject"},
    )
    assert resp.status_code == 200
    row = seed.get_pr(pr_id)
    assert row["tyler_decision"] == "reject"
    assert row["status"] == "rejected"


def test_decision_on_missing_pr_is_404(client: TestClient) -> None:
    login(client)
    resp = client.post(
        "/api/approvals/decision",
        json={"kind": "pr", "id": 999, "verdict": "approve"},
    )
    assert resp.status_code == 404


def test_bad_verdict_is_422(client: TestClient) -> None:
    login(client)
    resp = client.post(
        "/api/approvals/decision",
        json={"kind": "pr", "id": 1, "verdict": "maybe"},
    )
    assert resp.status_code == 422


def test_pr_detail_returns_reviews(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    pr_id = seed.pr(pid, github_pr=10)
    seed.review(pr_id)
    body = client.get(f"/api/approvals/pr/{pr_id}").json()
    assert body["pr"]["github_pr"] == 10
    assert len(body["reviews"]) == 1
    assert body["reviews"][0]["verdict"] == "approve"


def test_artifact_preview_reads_repo_file(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    aid = seed.artifact(pid, path="BOOTSTRAP.md")
    body = client.get(f"/api/approvals/artifact/{aid}/content").json()
    assert body["path"] == "BOOTSTRAP.md"
    assert len(body["content"]) > 0


def test_artifact_preview_rejects_path_traversal(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    aid = seed.artifact(pid, path="../../etc/passwd")
    resp = client.get(f"/api/approvals/artifact/{aid}/content")
    assert resp.status_code == 403


def test_artifact_preview_rejects_gcs_ref(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    aid = seed.artifact(pid, path="gs://bucket/thing.png")
    resp = client.get(f"/api/approvals/artifact/{aid}/content")
    assert resp.status_code == 400


def test_merge_succeeds_with_fake_and_flips_status(
    client: TestClient, fake_merger: FakeMerger
) -> None:
    login(client)
    pid = seed.project(repo="TeamHiggs/team-higgs")
    pr_id = seed.pr(pid, github_pr=11, tyler_decision="approve")
    resp = client.post(f"/api/approvals/pr/{pr_id}/merge")
    assert resp.status_code == 200, resp.text
    assert resp.json()["merged"] is True
    assert fake_merger.calls == [("TeamHiggs", "team-higgs", 11)]
    assert seed.get_pr(pr_id)["status"] == "merged"


def test_merge_requires_prior_approval(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    pr_id = seed.pr(pid, github_pr=12)  # undecided
    resp = client.post(f"/api/approvals/pr/{pr_id}/merge")
    assert resp.status_code == 400


def test_merge_degrades_without_token(no_token_client: TestClient) -> None:
    login(no_token_client)
    pid = seed.project()
    pr_id = seed.pr(pid, github_pr=13, tyler_decision="approve")
    resp = no_token_client.post(f"/api/approvals/pr/{pr_id}/merge")
    assert resp.status_code == 503
    # Clean degradation: still not merged, no crash.
    assert seed.get_pr(pr_id)["status"] == "open"


def test_answer_blocking_question(client: TestClient) -> None:
    login(client)
    pid = seed.project()
    qid = seed.question(pid, body="which host?")
    resp = client.post(
        f"/api/approvals/question/{qid}/answer", json={"answer": "higgs subdomain"}
    )
    assert resp.status_code == 200
    # Answered questions leave the blocking queue.
    items = client.get("/api/approvals").json()["items"]
    assert [i for i in items if i["kind"] == "question"] == []
