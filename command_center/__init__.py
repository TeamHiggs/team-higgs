"""command-center: emctl-over-HTTP.

A FastAPI service that exposes the platform state ``emctl`` manages over an
authenticated JSON API, so the command-center SPA (task #28) can read and write
it. It reuses emctl's data layer (``emctl.db``, ``emctl.repo.*``,
``emctl.services``) rather than duplicating queries (PRD command-center §3,
decision #18). No endpoint spawns compute, invokes the model API, or launches an
agent (decisions #15/#16); the only outward call is a GitHub PR merge, which is
external state, not compute (decision #21).
"""
