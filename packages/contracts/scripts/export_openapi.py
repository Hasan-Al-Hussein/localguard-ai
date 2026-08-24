"""Write or verify the checked FastAPI OpenAPI snapshot."""

from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path

from localguard_api.main import app


def serialized_schema() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", type=Path)
    mode.add_argument("--check", type=Path)
    arguments = parser.parse_args()
    expected = serialized_schema()

    if arguments.write is not None:
        arguments.write.write_text(expected, encoding="utf-8")
        return 0

    assert arguments.check is not None
    actual = arguments.check.read_text(encoding="utf-8") if arguments.check.exists() else ""
    if actual == expected:
        return 0

    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile=str(arguments.check),
        tofile="FastAPI app.openapi()",
        n=3,
    )
    print("OpenAPI snapshot drift detected. Regenerate it from the frozen FastAPI app.")
    print("\n".join(list(diff)[:200]))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
