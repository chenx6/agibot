from json import dumps, load
from pathlib import Path

from anyio import open_file

from ..logger import get_logger

logger = get_logger()


class MemoryManager:
    def __init__(self, filename: str) -> None:
        self.mem_file = Path(filename)
        if not self.mem_file.exists():
            self.mem_file.write_text("{}")
        with open(self.mem_file) as f:
            self.memory: dict[str, str] = load(f)

    def get_memory(self, user_id: str):
        """
        获取记忆
        """
        logger.debug("Get memory: %s", user_id)
        return self.memory.get(user_id)

    async def store_memory(self, user_id: str, memory: str):
        """
        存储记忆
        """
        logger.debug("Store memory: %s %s", user_id, memory)
        self.memory[user_id] = memory
        async with await open_file(self.mem_file, "w", encoding="utf-8") as f:
            await f.write(dumps(self.memory, ensure_ascii=False))
