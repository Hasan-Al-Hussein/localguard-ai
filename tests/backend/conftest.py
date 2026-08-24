"""Backend test path and explicit deterministic runtime configuration."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for package_root in (
    ROOT / "apps" / "api",
    ROOT / "services" / "mcp",
    ROOT / "services" / "worker",
):
    value = str(package_root)
    if value not in sys.path:
        sys.path.insert(0, value)
