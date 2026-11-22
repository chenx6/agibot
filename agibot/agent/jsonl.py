from collections import deque
from json import dumps
from pathlib import Path

from anyio import Path as AsyncPath


async def read_jsonl(filename: str | Path, offset: int, length: int) -> list[str]:
    if length <= 0:
        return []
    path = AsyncPath(filename)
    if not await path.exists():
        return []
    start = max(offset, 1)
    end = start + length
    contents: list[str] = []
    async with await path.open(encoding="utf-8") as f:
        linenum = 1
        async for line in f:
            if linenum >= end:
                break
            if linenum >= start:
                contents.append(line)
            linenum += 1
    return contents


async def read_jsonl_rev(filename: str | Path, length: int) -> list[str]:
    if length <= 0:
        return []
    path = AsyncPath(filename)
    if not await path.exists():
        return []
    lines: deque[str] = deque(maxlen=length)
    async with await path.open(encoding="utf-8") as f:
        async for line in f:
            lines.append(line)
    return list(lines)


async def append_jsonl(filename: str | Path, content: object) -> None:
    async with await AsyncPath(filename).open("a+", encoding="utf-8") as fw:
        await fw.write(dumps(content, ensure_ascii=False) + "\n")
