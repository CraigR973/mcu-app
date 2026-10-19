"""The fake outside world — Batch 38.

Every call this app makes to another service (TMDB, eBay, Brave, Blu-ray.com, the shops, the
model, web push, Letterboxd) goes through ``httpx``. :func:`install` puts a
``httpx.MockTransport`` under every client the process builds and answers by host, so one fake
serves the API under the browser suite *and* the cron jobs run as real subprocesses, including
the call sites that have no dependency-injection seam.

It is armed only by ``MCU_OUTSIDE_WORLD=1`` (see ``apps/e2e/fakes/sitecustomize.py``) and only
against a local throwaway database. **A host not in the table is not let through**: the call
fails, and is written to the log as ``unfaked`` for the run to fail on.
"""

from __future__ import annotations

from .core import install, read_log, set_scenario  # noqa: F401
