"""Arms the fake outside world in any Python process started with this directory on its path.

Only when ``MCU_OUTSIDE_WORLD=1``. The API, and every cron job the suite runs as a
subprocess, start with it, so no process can reach a real service.

**It fails closed.** Python carries on after a ``sitecustomize`` that raised, printing the
error and starting the program anyway, which here would mean a process with no fake in it and
a real network. So any failure to arm ends the process on the spot.
"""

import os
import sys
from pathlib import Path

if os.environ.get("MCU_OUTSIDE_WORLD") == "1":
    try:
        tests_dir = Path(__file__).resolve().parents[2] / "api" / "tests"
        sys.path.insert(0, str(tests_dir))
        from outside_world import install

        install()
    except BaseException as exc:  # noqa: BLE001 - nothing may be allowed through
        sys.stderr.write(f"the fake outside world could not be armed: {exc}\n")
        sys.stderr.flush()
        os._exit(2)
