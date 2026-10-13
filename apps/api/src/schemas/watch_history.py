"""Wire models for the Letterboxd sync — Batch S5, snag 10a."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.schemas.wire import UtcDatetime


class SyncRunResponse(BaseModel):
    """One sync, in the shape the panel reads.

    **`startedAt` is the field the UI actually needs.** The 50-entry feed cap makes the
    *interval* a correctness property (`DECISIONS.md` #159), so "when did this last run"
    is the question, and a sync that failed still answers it — `error` says why.
    """

    id: str
    startedAt: UtcDatetime
    finishedAt: UtcDatetime | None
    trigger: str
    entries: int = Field(ge=0)
    written: int = Field(ge=0)
    alreadyImported: int = Field(ge=0)
    ambiguous: int = Field(ge=0)
    notInCollection: int = Field(ge=0)
    error: str | None


class WatchHistoryStatusResponse(BaseModel):
    """Everything the panel shows before anybody presses anything."""

    #: NULL until this person supplies one. The panel says so rather than offering a
    #: button that cannot work.
    letterboxdUsername: str | None
    lastSync: SyncRunResponse | None
    #: Live watch rows for this person. 0 for both until the S8 import is run.
    watchCount: int = Field(ge=0)


class SyncRequest(BaseModel):
    """Empty on purpose. A sync takes no options — the feed is the feed."""


class SyncResponse(BaseModel):
    run: SyncRunResponse
    #: Offered, never guessed. Described so a person can settle each one.
    ambiguities: list[str] = Field(default_factory=list)
    #: The feed came back at its 50-entry cap, so entries may have fallen off the end
    #: since the last sync. A cadence warning, not a failure.
    feedWasFull: bool


class UsernameRequest(BaseModel):
    """Letterboxd's own username alphabet, mirrored from the CHECK on the column.

    **A public username, never a credential** (`DECISIONS.md` #161).
    """

    letterboxdUsername: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_]{1,64}$")
