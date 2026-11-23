from asyncio import Lock, to_thread
from json import dumps, load
from os import fsync, replace
from pathlib import Path

from ..logger import get_logger

logger = get_logger()


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

    def get_memory(self, user_id: str) -> str | None:
        """
        获取指定用户的长期记忆画像

        Args:
            user_id: 用户的 QQ 号（字符串格式）

        Returns:
            该用户的长期记忆内容；若无记录则返回 None
        """
        logger.debug("Get memory: %s", user_id)
        return self.memory.get(user_id)

    async def store_memory(self, user_id: str, memory: str) -> None:
        """
        存储指定用户的长期记忆画像（全量覆写该用户原有记忆，调用前应先用 get_memory 合并旧记录）

        Args:
            user_id: 用户的 QQ 号（字符串格式）
            memory: 整理后的完整用户长期记忆文本
        """
        logger.debug("Store memory: %s %s", user_id, memory)
        async with self.lock:
            updated = {**self.memory, user_id: memory}
            await to_thread(self._atomic_write, dumps(updated, ensure_ascii=False))
            self.memory[user_id] = memory
