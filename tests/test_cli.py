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


def test_orders_uses_the_stored_session_and_prints_a_table(invoke, bilka: FakeBilka) -> None:
    invoke("login", "--email", EMAIL, "--password", PASSWORD)

    result = invoke("orders")

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0].split() == ["Order", "Ordered", "Pickup", "Slot", "Pickup", "Point", "Status"]
    assert lines[1].split() == [
        "900000000002",
        "2026-11-01",
        "20:15",
        "Tue",
        "03/11",
        "16:00-18:00",
        "Bilka",
        "Eksempelby",
        "Received",
    ]
    assert lines[2].split()[0] == "900000000001"
    assert lines[2].split()[-2:] == ["Picked", "Up"]
    assert len(bilka.calls("gigya_login")) == 1


def test_orders_limit(invoke, bilka: FakeBilka) -> None:
    invoke("login", "--email", EMAIL, "--password", PASSWORD)

    result = invoke("orders", "--limit", "1")

    assert result.exit_code == 0, result.output
    assert "900000000002" in result.output
    assert "900000000001" not in result.output
    [request] = bilka.calls("order_history")
    assert request.url.params["limit"] == "1"


def test_orders_json_output(invoke) -> None:
    invoke("login", "--email", EMAIL, "--password", PASSWORD)

    result = invoke("orders", "--json")

    assert result.exit_code == 0, result.output
    upcoming, collected = json.loads(result.output)
    assert upcoming == {
        "order_number": "900000000002",
        "status": "received",
        "status_code": "Bestilt",
        "ordered_at": "2026-11-01T20:15:00",
        "pickup_slot": {"date": "2026-11-03", "start": "16:00:00", "end": "18:00:00"},
        "pickup_point": {
            "name": "Bilka Eksempelby",
            "address": "Testvej 1",
            "zip_code": "9999",
            "city": "Eksempelby",
        },
        "home_delivery": False,
        "delivered": False,
        "ordered_price": 45600,
        "packed_price": 0,
        "content": "Æbler, Havregryn, Letmælk",
    }
    assert collected["status"] == "picked_up"


def test_orders_without_a_session_prompts_for_the_password(
    invoke, bilka: FakeBilka, config_dir: Path
) -> None:
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(json.dumps({"email": EMAIL}), encoding="utf-8")

    result = invoke("orders", input=f"{PASSWORD}\n")

    assert result.exit_code == 0, result.output
    assert logged_in_as(bilka) == EMAIL
    assert "900000000002" in result.output
    assert (config_dir / "session.json").exists()


def test_orders_with_a_wrong_password_fails_clearly(invoke) -> None:
    result = invoke("orders", "--email", EMAIL, "--password", "forkert")

    assert result.exit_code == 1
    assert "Wrong email or password" in result.output


def test_orders_when_there_are_none(invoke, bilka: FakeBilka) -> None:
    bilka.orders = []

    result = invoke("orders", "--email", EMAIL, "--password", PASSWORD)

    assert result.exit_code == 0, result.output
    assert "No orders" in result.output
