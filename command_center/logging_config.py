"""Structured logging setup for the command-center service.

A single JSON-ish line per record via the stdlib logger. Handlers never log
tokens, credentials, or request bodies; call sites pass only safe fields
(ids, types) in ``extra``.
"""

from __future__ import annotations

import logging

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger("command_center")
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True
