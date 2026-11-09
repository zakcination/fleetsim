"""Print the CHANGELOG.md section for one version: ``python scripts/release_notes.py 0.2.0``."""

import re
import sys
from pathlib import Path

version = sys.argv[1]
text = Path(__file__).resolve().parents[1].joinpath("CHANGELOG.md").read_text()
m = re.search(rf"^## \[?{re.escape(version)}\]?[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
if not m:
    sys.exit(f"no CHANGELOG section for {version}")
print(m.group(1).strip())
