"""Helper script to update the API route contract snapshot."""

from __future__ import annotations

import os
import subprocess
import sys

if __name__ == "__main__":
    env = os.environ.copy()
    env["UPDATE_SNAPSHOT"] = "1"
    cmd = [sys.executable, "-m", "unittest", "tests/test_api_v1_route_map.py"]
    print(f"Running: {' '.join(cmd)} with UPDATE_SNAPSHOT=1...")
    res = subprocess.run(cmd, env=env)
    sys.exit(res.returncode)
