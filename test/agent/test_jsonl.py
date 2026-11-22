from json import loads
from pathlib import Path

import pytest

from agibot.agent.jsonl import append_jsonl, read_jsonl, read_jsonl_rev


@pytest.mark.asyncio
async def test_jsonl_async_read_write(tmp_path: Path):
    path = tmp_path / "chat.jsonl"
    assert await read_jsonl(path, 1, 10) == []
    assert await read_jsonl_rev(path, 10) == []

    for i in range(1, 6):
        await append_jsonl(path, {"n": i, "text": f"中文消息内容-{i}"})

    assert [loads(r)["n"] for r in await read_jsonl(path, 2, 2)] == [2, 3]
    assert [loads(r)["n"] for r in await read_jsonl_rev(path, 2, chunk_size=16)] == [
        4,
        5,
    ]
    assert [loads(r)["n"] for r in await read_jsonl_rev(path, 10, chunk_size=16)] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert await read_jsonl(path, 1, 0) == []
    assert await read_jsonl_rev(path, 0) == []
