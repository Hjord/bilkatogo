import json
from pathlib import Path

import pytest

import release


def make_repo(
    root: Path, package: str = "0.1.0", manifest: str = "0.1.0", pin: str = "0.1.0"
) -> Path:
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "bilkatogo"\nversion = "{package}"\n\n'
        '[build-system]\nrequires = ["uv_build>=0.9.26,<0.10.0"]\n',
        encoding="utf-8",
    )
    integration = root / "custom_components" / "bilkatogo"
    integration.mkdir(parents=True)
    (integration / "manifest.json").write_text(
        "{\n"
        '  "domain": "bilkatogo",\n'
        '  "name": "BilkaToGo",\n'
        f'  "requirements": ["bilkatogo=={pin}"],\n'
        f'  "version": "{manifest}"\n'
        "}\n",
        encoding="utf-8",
    )
    return root


def test_matching_versions_have_no_problems(tmp_path: Path) -> None:
    assert release.check(make_repo(tmp_path)) == []


def test_manifest_version_differing_from_package_is_a_problem(tmp_path: Path) -> None:
    problems = release.check(make_repo(tmp_path, manifest="0.2.0"))

    assert problems == ["manifest.json version 0.2.0 differs from pyproject.toml version 0.1.0"]


def test_library_pin_differing_from_package_is_a_problem(tmp_path: Path) -> None:
    problems = release.check(make_repo(tmp_path, pin="0.0.9"))

    assert problems == ["manifest.json pins bilkatogo==0.0.9, expected bilkatogo==0.1.0"]


def test_manifest_without_library_pin_is_a_problem(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    manifest = repo / "custom_components" / "bilkatogo" / "manifest.json"
    manifest.write_text(json.dumps({"version": "0.1.0", "requirements": []}), encoding="utf-8")

    assert release.check(repo) == ["manifest.json does not pin bilkatogo==0.1.0"]


def test_check_command_fails_and_reports_mismatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = release.main(["check", "--root", str(make_repo(tmp_path, pin="0.0.9"))])

    assert exit_code == 1
    assert "pins bilkatogo==0.0.9" in capsys.readouterr().err


def test_check_command_passes_on_this_repository() -> None:
    assert release.main(["check", "--root", str(Path(__file__).parents[1])]) == 0
