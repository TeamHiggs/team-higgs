"""Publish the OpenAPI contract for the SPA (task #28) to build against.

The live ``/openapi.json`` route is fenced behind ``DEV_AUTH`` (info disclosure
in prod), so the contract is generated offline here instead:

    python -m command_center.openapi > command_center/openapi.json

Runs ``app.openapi()`` in-process against a minimal settings object -- no
database, network, or secret is touched.
"""

from __future__ import annotations

import json
import sys

from command_center.config import Settings
from command_center.main import create_app


def generate() -> dict[str, object]:
    # A throwaway settings object: only fields needed to build the app. No real
    # secret -- this never serves traffic.
    settings = Settings(SESSION_SECRET="openapi-dump", ALLOWED_EMAILS="")
    app = create_app(settings=settings)
    return app.openapi()


def main() -> None:
    json.dump(generate(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
