from importlib.util import find_spec
from typing import Any

import pytest

from bilkatogo import TokenStorage
from tests.fake_bilka import FakeBilka

collect_ignore = [] if find_spec("homeassistant") else ["ha"]


class MemoryTokenStorage(TokenStorage):
    def __init__(self) -> None:
        self.data: dict[str, Any] | None = None

    async def load(self) -> dict[str, Any] | None:
        return self.data

    async def save(self, data: dict[str, Any]) -> None:
        self.data = data


@pytest.fixture
def bilka() -> FakeBilka:
    return FakeBilka()


@pytest.fixture
def storage() -> MemoryTokenStorage:
    return MemoryTokenStorage()
