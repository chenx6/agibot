from asyncio import Lock, to_thread
from json import dumps, load
from os import fsync, replace
from pathlib import Path
from typing import Literal

from ..logger import get_logger

logger = get_logger()
MemoryType = Literal["user", "group"]


def _make_key(memory_type: MemoryType, target_id: str) -> str:
    if memory_type not in ("user", "group"):
        raise ValueError(f"invalid memory_type: {memory_type}")
    clean_id = target_id.strip().removeprefix(f"{memory_type}:")
    if not clean_id:
        raise ValueError("target_id cannot be empty")
    return f"{memory_type}:{clean_id}"


class MemoryManager:
    def __init__(self, filename: str) -> None:
        self.mem_file = Path(filename)
        self.lock = Lock()
        self.mem_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.mem_file.exists():
            self.mem_file.write_text("{}", encoding="utf-8")
        with open(self.mem_file, encoding="utf-8") as f:
            self.memory: dict[str, str] = load(f)

    def _atomic_write(self, content: str) -> None:
        """
        更安全的写入 memory 文件
        """
        tmp_file = self.mem_file.with_name(f"{self.mem_file.name}.tmp")
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                fsync(f.fileno())
            replace(tmp_file, self.mem_file)
        except BaseException:
            tmp_file.unlink(missing_ok=True)
            raise

    def get_memory(self, memory_type: MemoryType, target_id: str) -> str | None:
        """
        获取长期记忆

        Args:
            memory_type: 记忆类型，"user" 表示用户画像，"group" 表示群组记忆
            target_id: 对应 ID；user 为 QQ 号，group 为群号（可带或不带前缀）

        Returns:
            对应的长期记忆内容；若无记录则返回 None
        """
        key = _make_key(memory_type, target_id)
        logger.debug("Get memory: %s", key)
        return self.memory.get(key)

    async def store_memory(
        self, memory_type: MemoryType, target_id: str, memory: str
    ) -> None:
        """
        存储长期记忆（全量覆写该对象原有记忆，调用前应先用 get_memory 合并旧记录）

        Args:
            memory_type: 记忆类型，"user" 表示用户画像，"group" 表示群组记忆
            target_id: 对应 ID；user 为 QQ 号，group 为群号（可带或不带前缀）
            memory: 整理后的完整长期记忆文本（群记忆建议精简控制在 300~500 字内）
        """
        key = _make_key(memory_type, target_id)
        logger.debug("Store memory: %s %s", key, memory)
        async with self.lock:
            updated = {**self.memory, key: memory}
            await to_thread(self._atomic_write, dumps(updated, ensure_ascii=False))
            self.memory[key] = memory
