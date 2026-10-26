from pathlib import Path

import pytest

from bilkatogo import FileTokenStorage


@pytest.mark.asyncio
async def test_missing_file_loads_as_no_session(tmp_path: Path) -> None:
    assert await FileTokenStorage(tmp_path / "session.json").load() is None


@pytest.mark.asyncio
async def test_saved_session_loads_back_and_parent_dirs_are_created(tmp_path: Path) -> None:
    storage = FileTokenStorage(tmp_path / "nested" / "session.json")

    await storage.save({"jwt": "eyFake.jwt.token", "cookies": {"PHPSESSID": "abc"}})

    assert await storage.load() == {"jwt": "eyFake.jwt.token", "cookies": {"PHPSESSID": "abc"}}


@pytest.mark.asyncio
async def test_corrupt_file_loads_as_no_session(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text("{not json", encoding="utf-8")

    assert await FileTokenStorage(path).load() is None
