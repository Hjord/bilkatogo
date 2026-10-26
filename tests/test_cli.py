import asyncio
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bilkatogo import FileTokenStorage
from bilkatogo.cli import app
from tests.fake_bilka import EMAIL, PASSWORD, FakeBilka, form


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    return tmp_path / "config"


@pytest.fixture
def invoke(bilka: FakeBilka, config_dir: Path):
    runner = CliRunner()

    def run(*args: str, env: dict[str, str] | None = None, input: str | None = None):
        full_env: dict[str, str | None] = {
            "BILKATOGO_CONFIG_DIR": str(config_dir),
            "BILKATOGO_EMAIL": None,
            "BILKATOGO_PASSWORD": None,
            **(env or {}),
        }
        return runner.invoke(app, list(args), env=full_env, input=input, obj=bilka.client)

    return run


def logged_in_as(bilka: FakeBilka) -> str:
    [login] = bilka.calls("gigya_login")
    return form(login)["loginID"]


def test_help_lists_the_login_command(invoke) -> None:
    result = invoke("--help")

    assert result.exit_code == 0
    assert "login" in result.output


def test_login_with_flags_stores_the_session(invoke, config_dir: Path) -> None:
    result = invoke("login", "--email", EMAIL, "--password", PASSWORD)

    assert result.exit_code == 0, result.output
    assert EMAIL in result.output
    session = asyncio.run(FileTokenStorage(config_dir / "session.json").load())
    assert session is not None
    assert session["jwt"] == "eyFake.jwt.token"


def test_login_reads_credentials_from_environment(invoke, bilka: FakeBilka) -> None:
    result = invoke("login", env={"BILKATOGO_EMAIL": EMAIL, "BILKATOGO_PASSWORD": PASSWORD})

    assert result.exit_code == 0, result.output
    assert logged_in_as(bilka) == EMAIL


def test_flags_win_over_environment(invoke, bilka: FakeBilka) -> None:
    result = invoke(
        "login",
        "--email",
        EMAIL,
        "--password",
        PASSWORD,
        env={"BILKATOGO_EMAIL": "other@example.com", "BILKATOGO_PASSWORD": "other"},
    )

    assert result.exit_code == 0, result.output
    assert logged_in_as(bilka) == EMAIL


def test_environment_wins_over_config_file(invoke, bilka: FakeBilka, config_dir: Path) -> None:
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(
        json.dumps({"email": "other@example.com", "password": "other"}), encoding="utf-8"
    )

    result = invoke("login", env={"BILKATOGO_EMAIL": EMAIL, "BILKATOGO_PASSWORD": PASSWORD})

    assert result.exit_code == 0, result.output
    assert logged_in_as(bilka) == EMAIL


def test_login_reads_credentials_from_config_file(
    invoke, bilka: FakeBilka, config_dir: Path
) -> None:
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(
        json.dumps({"email": EMAIL, "password": PASSWORD}), encoding="utf-8"
    )

    result = invoke("login")

    assert result.exit_code == 0, result.output
    assert logged_in_as(bilka) == EMAIL


def test_login_prompts_for_missing_credentials(invoke, bilka: FakeBilka) -> None:
    result = invoke("login", input=f"{EMAIL}\n{PASSWORD}\n")

    assert result.exit_code == 0, result.output
    assert logged_in_as(bilka) == EMAIL
    assert PASSWORD not in result.output


def test_wrong_password_prints_a_clear_message_and_exits_non_zero(invoke, config_dir: Path) -> None:
    result = invoke("login", "--email", EMAIL, "--password", "forkert")

    assert result.exit_code == 1
    assert "Wrong email or password" in result.output
    assert not (config_dir / "session.json").exists()


def test_login_json_output(invoke) -> None:
    result = invoke("login", "--email", EMAIL, "--password", PASSWORD, "--json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"email": EMAIL, "logged_in": True}
