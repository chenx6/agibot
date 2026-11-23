from json import loads
from pathlib import Path

import pytest

from agibot.agent.memory import MemoryManager


@pytest.mark.asyncio
async def test_memory_manager_async_store(tmp_path: Path):
    mem_file = tmp_path / "memory.json"
    mgr = MemoryManager(str(mem_file))

    assert mgr.get_memory("1001") is None
    await mgr.store_memory("1001", "喜欢写 Python")

    assert mgr.get_memory("1001") == "喜欢写 Python"
    assert loads(mem_file.read_text(encoding="utf-8")) == {"1001": "喜欢写 Python"}
