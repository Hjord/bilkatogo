import asyncio
import json
import sys
from importlib.metadata import entry_points
from pathlib import Path

import httpx
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
            "store_id": None,
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


@pytest.mark.parametrize("command", ["login", "orders"])
@pytest.mark.parametrize(
    ("route", "failure", "message"),
    [
        ("gigya_login", httpx.ConnectError("fake: refused"), "Could not reach Bilka"),
        ("login_jwt", httpx.ReadTimeout("fake: timed out"), "Could not reach Bilka"),
        ("login_jwt", httpx.Response(503, text="<html>Down</html>"), "Bilka answered unexpectedly"),
    ],
)
def test_failures_print_a_clear_message_and_exit_non_zero(
    invoke, bilka: FakeBilka, command: str, route: str, failure, message: str
) -> None:
    bilka.script(route, failure)

    result = invoke(command, "--email", EMAIL, "--password", PASSWORD)

    assert result.exit_code == 1
    assert message in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (httpx.ConnectError("fake: refused"), "Could not reach Bilka"),
        (httpx.Response(200, text="<html>Vedligehold</html>"), "Bilka answered unexpectedly"),
    ],
)
def test_orders_failures_on_the_order_history_call(
    invoke, bilka: FakeBilka, failure, message: str
) -> None:
    bilka.script("order_history", failure)

    result = invoke("orders", "--email", EMAIL, "--password", PASSWORD)

    assert result.exit_code == 1
    assert message in result.output


def test_order_prints_details_and_substitutions(invoke, bilka: FakeBilka) -> None:
    invoke("login", "--email", EMAIL, "--password", PASSWORD)

    result = invoke("order", "900000000001")

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        "Order         900000000001",
        "Status        Picked Up",
        "Pickup Slot   Tue 27/10 12:00-14:00",
        "Pickup Point  Bilka Eksempelby",
        "Pickup Code   12345678",
        "Substitutions",
        "  Æbler -> 4 x Pærer",
        "  Letmælk -> 3 x Minimælk",
    ]
    assert len(bilka.calls("gigya_login")) == 1


def test_order_without_substitutions_says_so(invoke) -> None:
    result = invoke("order", "900000000002", "--email", EMAIL, "--password", PASSWORD)

    assert result.exit_code == 0, result.output
    assert "Pickup Code   87654321" in result.output
    assert result.output.splitlines()[-1] == "Substitutions none"


def test_order_json_output(invoke) -> None:
    result = invoke("order", "900000000001", "--email", EMAIL, "--password", PASSWORD, "--json")

    assert result.exit_code == 0, result.output
    details = json.loads(result.output)
    assert details["order_number"] == "900000000001"
    assert details["status"] == "picked_up"
    assert details["pickup_slot"] == {"date": "2026-10-27", "start": "12:00:00", "end": "14:00:00"}
    assert details["pickup_point"]["name"] == "Bilka Eksempelby"
    assert details["pickup_code"] == {"code": "12345678"}
    assert details["substitutions"][0] == {
        "original_product": "Æbler",
        "replacement_product": "Pærer",
        "quantity": 4,
    }
    assert details["lines"][1] == {
        "category": "Frugt & grønt",
        "product_id": 1003,
        "name": "Rugbrød",
        "quantity": 1,
        "amount": 2500,
        "substituted": False,
        "unavailable_reason": "",
    }


def test_order_that_does_not_exist_fails_clearly(invoke) -> None:
    result = invoke("order", "900000000099", "--email", EMAIL, "--password", PASSWORD)

    assert result.exit_code == 1
    assert "Could not fetch order 900000000099" in result.output


def test_order_without_a_number_prints_the_current_order(invoke, bilka: FakeBilka) -> None:
    result = invoke("order", "--email", EMAIL, "--password", PASSWORD)

    assert result.exit_code == 0, result.output
    assert result.output.splitlines()[:3] == [
        "Order         900000000002",
        "Status        Received",
        "Pickup Slot   Tue 03/11 16:00-18:00",
    ]


def test_order_without_a_number_and_no_orders(invoke, bilka: FakeBilka) -> None:
    bilka.orders = []

    result = invoke("order", "--email", EMAIL, "--password", PASSWORD)

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "No orders."


def test_order_without_a_number_and_no_orders_json(invoke, bilka: FakeBilka) -> None:
    bilka.orders = []

    result = invoke("order", "--email", EMAIL, "--password", PASSWORD, "--json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) is None


def test_entry_point_without_the_cli_extra_explains_how_to_install_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    [script] = entry_points(group="console_scripts", name="bilkatogo")
    main = script.load()
    monkeypatch.setitem(sys.modules, "typer", None)
    monkeypatch.delitem(sys.modules, "bilkatogo.cli")

    with pytest.raises(SystemExit) as exit_info:
        main()

    assert exit_info.value.code == 1
    message = capsys.readouterr().err.strip()
    assert "bilkatogo[cli]" in message
    assert "\n" not in message
