from json import dumps
from os import SEEK_END
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


async def read_jsonl_rev(
    filename: str | Path, length: int, chunk_size: int = 8192
) -> list[str]:
    if length <= 0:
        return []
    path = AsyncPath(filename)
    if not await path.exists():
        return []

    async with await path.open("rb") as f:
        await f.seek(0, SEEK_END)
        pos = await f.tell()
        chunks: list[bytes] = []
        newlines = 0
        while pos > 0 and newlines <= length:
            # 倒序读取 chunk 并计算 chunk 里的行数
            read_size = min(chunk_size, pos)
            pos -= read_size
            await f.seek(pos)
            chunk = await f.read(read_size)
            chunks.append(chunk)
            newlines += chunk.count(b"\n")
    # 拼接 chunk 并只保留所需行数
    data = b"".join(reversed(chunks))
    return [line.decode("utf-8") for line in data.splitlines(keepends=True)[-length:]]


async def append_jsonl(filename: str | Path, content: object) -> None:
    async with await AsyncPath(filename).open("a+", encoding="utf-8") as fw:
        await fw.write(dumps(content, ensure_ascii=False) + "\n")
