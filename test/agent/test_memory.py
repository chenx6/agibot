from asyncio import gather
from json import loads
from pathlib import Path

import pytest

import agibot.agent.memory as memory_mod
from agibot.agent.memory import MemoryManager


@pytest.mark.asyncio
async def test_memory_manager_concurrent_store(tmp_path: Path):
    mem_file = tmp_path / "memory.json"
    mgr = MemoryManager(str(mem_file))
    assert mgr.get_memory("1001") is None

    expected = {f"10{i:02d}": f"喜欢写 Python {i}" for i in range(20)}
    await gather(*(mgr.store_memory(uid, mem) for uid, mem in expected.items()))

    assert loads(mem_file.read_text(encoding="utf-8")) == expected
    assert mgr.get_memory("1001") == "喜欢写 Python 1"
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.asyncio
async def test_memory_manager_atomic_write_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    mem_file = tmp_path / "memory.json"
    mgr = MemoryManager(str(mem_file))
    await mgr.store_memory("1001", "旧记忆")

    def boom(*_args, **_kwargs):
        raise OSError("disk error")

    monkeypatch.setattr(memory_mod, "replace", boom)
    with pytest.raises(OSError):
        await mgr.store_memory("1001", "新记忆")

    assert mgr.get_memory("1001") == "旧记忆"
    assert loads(mem_file.read_text(encoding="utf-8")) == {"1001": "旧记忆"}
    assert list(tmp_path.glob("*.tmp")) == []
