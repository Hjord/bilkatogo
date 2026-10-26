"""Lockstep release of the bilkatogo package and its Home Assistant integration."""

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

PYPROJECT = Path("pyproject.toml")
MANIFEST = Path("custom_components/bilkatogo/manifest.json")
PIN_PREFIX = "bilkatogo=="
VERSION = re.compile(r"\d+\.\d+\.\d+")


class ReleaseError(Exception):
    pass


def package_version(root: Path) -> str:
    return tomllib.loads((root / PYPROJECT).read_text(encoding="utf-8"))["project"]["version"]


def bump(root: Path, version: str) -> None:
    current = package_version(root)
    if not VERSION.fullmatch(version):
        raise ReleaseError(f"{version} is not an X.Y.Z version")
    if parse(version) <= parse(current):
        raise ReleaseError(f"{version} is not newer than {current}")

    replace(root / PYPROJECT, r'(?m)^version = "[^"]*"', f'version = "{version}"')
    replace(root / MANIFEST, r'"version": "[^"]*"', f'"version": "{version}"')
    replace(root / MANIFEST, rf'"{re.escape(PIN_PREFIX)}[^"]*"', f'"{PIN_PREFIX}{version}"')


def parse(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def replace(path: Path, pattern: str, replacement: str) -> None:
    text, count = re.subn(pattern, replacement, path.read_text(encoding="utf-8"), count=1)
    if count != 1:
        raise ReleaseError(f"{path} has no match for {pattern}")
    path.write_text(text, encoding="utf-8", newline="")


def check(root: Path) -> list[str]:
    package = package_version(root)
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


def publish(root: Path, version: str) -> None:
    def run(*cmd: str) -> str:
        result = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        if result.returncode != 0:
            raise ReleaseError(f"{' '.join(cmd)} failed:\n{result.stderr}")
        return result.stdout

    if run("git", "branch", "--show-current").strip() != "main":
        raise ReleaseError("Release from the main branch")
    if run("git", "status", "--porcelain").strip():
        raise ReleaseError("Commit or stash your changes first")
    run("git", "pull", "--ff-only")

    bump(root, version)
    run("uv", "lock")
    run("git", "add", str(PYPROJECT), str(MANIFEST), "uv.lock")
    run("git", "commit", "-m", f"Release v{version}")
    run("git", "push", "origin", "main")
    run("gh", "release", "create", f"v{version}", "--title", f"v{version}", "--generate-notes")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("check", "Fail when the package and integration versions differ."),
        ("bump", "Set the package, manifest and library pin to VERSION."),
        ("publish", "Bump, commit, push and create the GitHub release vVERSION."),
    ]:
        command = commands.add_parser(name, help=help_text)
        if name != "check":
            command.add_argument("version", metavar="VERSION")
        command.add_argument("--root", type=Path, default=Path(__file__).parent)
    args = parser.parse_args(argv)

    try:
        if args.command == "bump":
            bump(args.root, args.version)
        elif args.command == "publish":
            publish(args.root, args.version)
    except ReleaseError as error:
        print(error, file=sys.stderr)
        return 1

    problems = check(args.root)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
