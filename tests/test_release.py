import json
import subprocess
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


def test_bump_moves_package_manifest_and_pin_together(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    release.bump(repo, "1.2.3")

    assert 'version = "1.2.3"' in (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires = ["uv_build>=0.9.26,<0.10.0"]' in (repo / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    manifest = (repo / "custom_components" / "bilkatogo" / "manifest.json").read_text(
        encoding="utf-8"
    )
    assert manifest == (
        "{\n"
        '  "domain": "bilkatogo",\n'
        '  "name": "BilkaToGo",\n'
        '  "requirements": ["bilkatogo==1.2.3"],\n'
        '  "version": "1.2.3"\n'
        "}\n"
    )
    assert release.check(repo) == []


@pytest.mark.parametrize("version", ["1.2", "v1.2.3", "1.2.3.dev1", "0.1.0"])
def test_bump_rejects_versions_that_are_not_a_new_x_y_z(tmp_path: Path, version: str) -> None:
    repo = make_repo(tmp_path)

    with pytest.raises(release.ReleaseError):
        release.bump(repo, version)

    assert release.check(repo) == []
    assert 'version = "0.1.0"' in (repo / "pyproject.toml").read_text(encoding="utf-8")


def test_bump_command_bumps_the_repository(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    assert release.main(["bump", "0.2.0", "--root", str(repo)]) == 0

    assert release.package_version(repo) == "0.2.0"
    assert release.check(repo) == []


def test_bump_command_reports_an_invalid_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = release.main(["bump", "0.0.1", "--root", str(make_repo(tmp_path))])

    assert exit_code == 1
    assert "0.0.1 is not newer than 0.1.0" in capsys.readouterr().err


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.mark.parametrize(
    ("branch", "dirty", "message"),
    [
        ("main", True, "Commit or stash your changes first"),
        ("feature", False, "Release from the main branch"),
    ],
)
def test_publish_refuses_and_changes_nothing_off_a_clean_main(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], branch: str, dirty: bool, message: str
) -> None:
    repo = make_repo(tmp_path)
    git(repo, "init", "-q", "-b", branch)
    git(repo, "add", ".")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "init")
    if dirty:
        (repo / "scratch.txt").write_text("wip", encoding="utf-8")

    assert release.main(["publish", "0.2.0", "--root", str(repo)]) == 1

    assert message in capsys.readouterr().err
    assert release.package_version(repo) == "0.1.0"


def test_check_command_fails_and_reports_mismatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = release.main(["check", "--root", str(make_repo(tmp_path, pin="0.0.9"))])

    assert exit_code == 1
    assert "pins bilkatogo==0.0.9" in capsys.readouterr().err


def test_check_command_passes_on_this_repository() -> None:
    assert release.main(["check", "--root", str(Path(__file__).parents[1])]) == 0
