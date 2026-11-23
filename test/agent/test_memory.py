from asyncio import gather
from json import loads
from pathlib import Path

import pytest

import agibot.agent.memory as memory_mod
from agibot.agent.memory import MemoryManager


@pytest.mark.asyncio
async def test_memory_manager_user_and_group(tmp_path: Path):
    mem_file = tmp_path / "memory.json"
    mgr = MemoryManager(str(mem_file))

    assert mgr.get_memory("user", "1001") is None
    assert mgr.get_memory("group", "533961263") is None

    await mgr.store_memory("user", "1001", "喜欢写 Python")
    await mgr.store_memory("group", "group:533961263", "偏技术与二次元调侃")
    assert mgr.get_memory("user", "1001") == "喜欢写 Python"
    assert mgr.get_memory("group", "533961263") == "偏技术与二次元调侃"
    assert mgr.get_memory("group", "group:533961263") == "偏技术与二次元调侃"
    assert loads(mem_file.read_text(encoding="utf-8")) == {
        "user:1001": "喜欢写 Python",
        "group:533961263": "偏技术与二次元调侃",
    }

    with pytest.raises(ValueError):
        mgr.get_memory("user", "")
    with pytest.raises(ValueError):
        mgr.get_memory("group", "group:")


@pytest.mark.asyncio
async def test_memory_manager_concurrent_store(tmp_path: Path):
    mem_file = tmp_path / "memory.json"
    mgr = MemoryManager(str(mem_file))

    items = [
        (("user" if i % 2 == 0 else "group"), f"10{i:02d}", f"记忆-{i}")
        for i in range(20)
    ]
    await gather(*(mgr.store_memory(t, tid, mem) for t, tid, mem in items))  # pyright: ignore[reportArgumentType]

    expected = {f"{t}:{tid}": mem for t, tid, mem in items}
    assert loads(mem_file.read_text(encoding="utf-8")) == expected
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.asyncio
async def test_memory_manager_atomic_write_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    mem_file = tmp_path / "memory.json"
    mgr = MemoryManager(str(mem_file))
    await mgr.store_memory("user", "1001", "旧记忆")

    def boom(*_args, **_kwargs):
        raise OSError("disk error")

    monkeypatch.setattr(memory_mod, "replace", boom)
    with pytest.raises(OSError):
        await mgr.store_memory("user", "1001", "新记忆")

    assert mgr.get_memory("user", "1001") == "旧记忆"
    assert loads(mem_file.read_text(encoding="utf-8")) == {"user:1001": "旧记忆"}
    assert list(tmp_path.glob("*.tmp")) == []
