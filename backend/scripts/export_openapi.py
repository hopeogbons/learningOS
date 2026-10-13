"""Export actual API DTO schemas; --check is a deterministic drift gate."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.main import app

parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
path = ROOT / "contracts/openapi.json"
content = json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
if args.check:
    if not path.exists() or path.read_text() != content:
        raise SystemExit("OpenAPI drift: run uv run python scripts/export_openapi.py from backend")
else:
    path.write_text(content)
print("OpenAPI " + ("matches" if args.check else "exported"))
