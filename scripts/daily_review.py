#!/usr/bin/env python3
"""Run the durable review scheduler once; no independent/duplicated schedule state."""
from pathlib import Path
import os
import subprocess
import sys

repo = Path(__file__).resolve().parents[1]
result = subprocess.run(["uv", "run", "--frozen", "python", "-m", "app.worker", "--once"], cwd=repo / "backend", env=os.environ.copy())
sys.exit(result.returncode)
