"""Seed helpers: write fixture rows through the shared emctl repos.

Using the same repos the API uses keeps the tests honest about the schema and
avoids a second, drifting insert path.
"""

from __future__ import annotations

from typing import Any

from emctl.db import transaction
from emctl.repo import artifacts, decisions, projects, prs, questions, reviews, tasks


def project(*, name: str = "command-center", repo: str = "TeamHiggs/team-higgs") -> int:
    with transaction() as conn:
        row = projects.create(conn, name=name, repo=repo, brief=None, status=None)
    return int(row["id"])


def task(
    project_id: int, *, title: str = "a task", status: str | None = None
) -> int:
    with transaction() as conn:
        row = tasks.create(
            conn,
            project_id=project_id,
            title=title,
            spec=None,
            role=None,
            model_tier=None,
            prd_ref=None,
            status=status,
            branch=None,
            depends_on=None,
        )
    return int(row["id"])


def pr(
    project_id: int,
    *,
    github_pr: int = 42,
    status: str | None = None,
    tyler_decision: str | None = None,
    em_summary: str | None = "a summary",
) -> int:
    with transaction() as conn:
        row = prs.open_(
            conn,
            project_id=project_id,
            github_pr=github_pr,
            risk_level="low",
            em_summary=em_summary,
            status=status,
            task_id=None,
        )
        pr_id = int(row["id"])
        if tyler_decision is not None:
            prs.update(
                conn,
                pr_id,
                status=None,
                risk_level=None,
                em_summary=None,
                tyler_decision=tyler_decision,
                task_id=None,
            )
    return pr_id


def review(pr_id: int) -> int:
    with transaction() as conn:
        row = reviews.add(
            conn,
            pr_id=pr_id,
            role="reviewer-security",
            model="test",
            verdict="approve",
            findings=[{"severity": "low", "where": "x", "claim": "c"}],
            strongest_objection="none material",
        )
    return int(row["id"])


def artifact(
    project_id: int, *, type_: str = "mockup", path: str = "README.md"
) -> int:
    with transaction() as conn:
        row = artifacts.create(
            conn, project_id=project_id, task_id=None, type_=type_, path=path
        )
    return int(row["id"])


def decision(*, title: str = "a decision", status: str = "proposed") -> int:
    with transaction() as conn:
        row = decisions.add(
            conn,
            project_id=None,
            title=title,
            context=None,
            decision="do the thing",
            significance=None,
            status=status,
        )
    return int(row["id"])


def question(
    project_id: int | None = None, *, body: str = "which way?", blocking: bool = True
) -> int:
    with transaction() as conn:
        row = questions.add(
            conn, project_id=project_id, body=body, blocking=blocking
        )
    return int(row["id"])


def get_task(task_id: int) -> dict[str, Any]:
    with transaction() as conn:
        return tasks.get(conn, task_id)


def get_pr(pr_id: int) -> dict[str, Any]:
    with transaction() as conn:
        return prs.get(conn, pr_id)
