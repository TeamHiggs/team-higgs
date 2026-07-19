# ML stack

Authoritative for **product** ML work (decided 2026-07-19). No current product
needs ML; recorded so the choice is settled when the first ML task arrives.

## Decisions

- **PyTorch** for deep-learning / neural models.
- **scikit-learn** for classical ML (regression, trees, clustering, pipelines).
- Standard Python discipline applies (uv, ruff, mypy, pytest, Docker per
  `docs/stack-backend.md`). Models, eval-sets, and prompts are **artifacts**
  (large binaries in GCS with references in `docs/design/`), tracked with the
  same approval-gate lifecycle as any artifact (EM charter, *Artifacts and
  approval gates*).

Serving/routing infrastructure (local model serving, model routing) is
deliberately deferred — decided alongside that work, not before
(`docs/stack-devops.md`).
