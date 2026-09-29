from asyncio.locks import Lock
from pathlib import Path
from subprocess import run

from ..logger import get_logger
from .jsonl import append_jsonl, read_jsonl, read_jsonl_rev
from .model import MessageDetail

logger = get_logger()


def sanitize_path(folder: Path, conv_id: str):
    res = folder / conv_id
    if res.absolute().is_relative_to(folder.absolute()):
        return res
    raise ValueError("conversation id is wrong")


class ContextManager:
    def __init__(self, context_folder: str) -> None:
        self._context_folder = Path(context_folder)
        self.lock = Lock()
        if not self._context_folder.exists():
            self._context_folder.mkdir()

    def get_context(self, conversation_id: str, offset: int, length: int = 10):
        """
        获取当前聊天记录的上下文

        Args:
            conversation_id: 会话的 id
            offset: 文件行数偏移
            length: 文件行数，默认为 10 行
        """
        logger.debug("Get context: %s %s", conversation_id, length)
        return read_jsonl(
            sanitize_path(self._context_folder, conversation_id), offset, length
        )

    def get_nearest_context(self, conversation_id: str, length: int):
        logger.debug("Get nearest context: %s %s", conversation_id, length)
        return read_jsonl_rev(
            sanitize_path(self._context_folder, conversation_id), length
        )

    def search_context(self, conversation_id: str, pattern: str):
        """
        在聊天记录中搜索关键字

        Args:
            conversation_id: 会话的 id
            pattern: 搜索 pattern, 格式为 ripgrep 支持的正则
        """
        logger.debug("Search context: %s %s", conversation_id, pattern)
        p = run(
            ["rg", pattern, sanitize_path(self._context_folder, conversation_id)],
            capture_output=True,
            check=False,
        )
        return p.stdout.decode()

    async def add_context(self, conversation_id: str, message: MessageDetail):
        """
        加入当前的聊天记录
        """
        logger.debug("Add context: %s %s", conversation_id, message)
        async with self.lock:
            append_jsonl(
                sanitize_path(self._context_folder, conversation_id), message._asdict()
            )
