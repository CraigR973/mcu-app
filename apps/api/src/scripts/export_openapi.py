"""Write the API's OpenAPI description to `packages/shared/openapi.json` — Batch X8 (CR43-04).

The web's contract test (`apps/web/src/contract.test.ts`) reads that file and holds every
zod schema the web parses an answer with to the response model the API declares: enums,
nullability, minimums. The API's own test (`tests/test_openapi_snapshot.py`) fails when the
file no longer matches the app, so neither side can drift without CI saying so.

    PROCESS_ROLE=web PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.export_openapi
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SNAPSHOT = Path(__file__).resolve().parents[4] / "packages" / "shared" / "openapi.json"


def current() -> dict[str, Any]:
    from src.main import app

    spec: dict[str, Any] = app.openapi()
    return spec


def render(spec: dict[str, Any]) -> str:
    return json.dumps(spec, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    SNAPSHOT.write_text(render(current()), encoding="utf-8")
    print(f"wrote {SNAPSHOT}")


if __name__ == "__main__":
    main()
