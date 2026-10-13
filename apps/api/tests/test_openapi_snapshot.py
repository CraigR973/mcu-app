"""The committed OpenAPI description matches the app — Batch X8 (CR43-04).

`packages/shared/openapi.json` is what the web's contract test holds the zod schemas to. A
response model that changes without the file being written again would leave the contract
test checking yesterday's API, so this fails instead.
"""

from __future__ import annotations

from src.scripts.export_openapi import SNAPSHOT, current, render

REGENERATE = (
    "PROCESS_ROLE=web PYTHONPATH=apps/api "
    "apps/api/.venv/bin/python3.12 -m src.scripts.export_openapi"
)


def test_the_committed_openapi_matches_the_app() -> None:
    assert SNAPSHOT.exists(), f"No {SNAPSHOT}; write it with: {REGENERATE}"
    assert SNAPSHOT.read_text(encoding="utf-8") == render(current()), (
        f"The API's response models changed; write the snapshot again with: {REGENERATE}"
    )


def test_the_audit_action_vocabulary_matches_the_table() -> None:
    """The response's Literal and the table's CHECK are one list, written twice."""
    from typing import get_args

    from src.models.admin_action import ACTION_TYPES
    from src.schemas.collection import AuditEntryResponse

    declared = get_args(AuditEntryResponse.model_fields["actionType"].annotation)
    assert set(declared) == set(ACTION_TYPES)
