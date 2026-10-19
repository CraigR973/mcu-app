"""Arms the fake outside world in any Python process started with this directory on its path.

Only when ``MCU_OUTSIDE_WORLD=1``. The API, and every cron job the suite runs as a
subprocess, start with it, so no process can reach a real service.
"""

import os
import sys
from pathlib import Path

if os.environ.get("MCU_OUTSIDE_WORLD") == "1":
    tests_dir = Path(__file__).resolve().parents[2] / "api" / "tests"
    sys.path.insert(0, str(tests_dir))
    from outside_world import install

    install()
