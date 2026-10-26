import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bilkatogo.cli import app
from tests.fake_bilka import EMAIL, PASSWORD, FakeBilka, load_fixture


@pytest.fixture
def invoke(bilka: FakeBilka, tmp_path: Path):
    runner = CliRunner()

    def run(*args: str):
        env: dict[str, str | None] = {
            "BILKATOGO_CONFIG_DIR": str(tmp_path / "config"),
            "BILKATOGO_EMAIL": None,
            "BILKATOGO_PASSWORD": None,
        }
        return runner.invoke(
            app, [*args, "--email", EMAIL, "--password", PASSWORD], env=env, obj=bilka.client
        )

    return run


def test_cart_raw_prints_bilkas_json_as_received(invoke, logged_in_cart: FakeBilka) -> None:
    result = invoke("cart", "--raw")

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == load_fixture("cart_logged_in.json")


def test_order_raw_prints_bilkas_json_as_received(invoke) -> None:
    result = invoke("order", "900000000004", "--raw")

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == load_fixture("order_details_captured.json")


def test_order_raw_without_a_number_prints_the_current_order(invoke) -> None:
    result = invoke("order", "--raw")

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == load_fixture("order_details_plain.json")


def test_order_raw_without_a_number_and_no_orders(invoke, bilka: FakeBilka) -> None:
    bilka.orders = []

    result = invoke("order", "--raw")

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "null"
