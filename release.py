"""Lockstep release of the bilkatogo package and its Home Assistant integration."""

import argparse
import json
import sys
import tomllib
from pathlib import Path

PYPROJECT = Path("pyproject.toml")
MANIFEST = Path("custom_components/bilkatogo/manifest.json")
PIN_PREFIX = "bilkatogo=="


def check(root: Path) -> list[str]:
    package = tomllib.loads((root / PYPROJECT).read_text(encoding="utf-8"))["project"]["version"]
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    problems = []
    if manifest["version"] != package:
        problems.append(
            f"manifest.json version {manifest['version']} differs from "
            f"pyproject.toml version {package}"
        )
    pins = [
        req.removeprefix(PIN_PREFIX)
        for req in manifest.get("requirements", [])
        if req.startswith(PIN_PREFIX)
    ]
    if not pins:
        problems.append(f"manifest.json does not pin {PIN_PREFIX}{package}")
    for pin in pins:
        if pin != package:
            problems.append(f"manifest.json pins {PIN_PREFIX}{pin}, expected {PIN_PREFIX}{package}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check_parser = commands.add_parser(
        "check", help="Fail when the package and integration versions differ."
    )
    check_parser.add_argument("--root", type=Path, default=Path(__file__).parent)
    args = parser.parse_args(argv)

    problems = check(args.root)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
