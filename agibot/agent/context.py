from asyncio import Lock, create_subprocess_exec, wait_for
from asyncio.subprocess import PIPE
from json import loads
from pathlib import Path

from anyio import Path as AsyncPath

from ..logger import get_logger
from ..util import readable_time, truncate_text
from .jsonl import append_jsonl, read_jsonl, read_jsonl_rev
from .model import MessageDetail

logger = get_logger()
SEARCH_TIMEOUT = 10.0
SEARCH_MAX_MATCHES = 30
SEARCH_MAX_CHARS = 4000
SEARCH_TRUNCATED_NOTICE = "\n...(结果已截断)"


def sanitize_path(folder: Path, conv_id: str) -> Path:
    if not conv_id.strip() or "/" in conv_id:
        raise ValueError("conversation id is wrong")

    base = folder.resolve()
    res = (base / conv_id).resolve()
    if res != base and res.is_relative_to(base):
        return res
    raise ValueError("conversation id is wrong")


def json_message(js: str) -> str | None:
    """
    将 JSON 变成如下格式：[2026-11-08 01:17:00] 昵称(user_id): 消息正文
    """
    try:
        raw_msg = loads(js)
        time = readable_time(raw_msg["timestamp"])
        speaker = f"{raw_msg.get('nickname') or ''}({raw_msg['user_id']}):"
        message = raw_msg["message"]
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        logger.warning("Format json message failed, %s", e)
        return None
    if reply_to := raw_msg.get("reply_to"):
        message = f"{message}（回复 {reply_to}）"
    return f"[{time}] {speaker} {message}"


def jsonl_list_message(json_strs: list[str]) -> list[str]:
    """
    将 JSON 转换成可读的形式
    """
    return [
        msg
        for js in json_strs
        if js.strip() and (msg := json_message(js)) is not None
    ]


def _format_search_results(raw_output: str, max_chars: int = SEARCH_MAX_CHARS) -> str:
    lines = []
    for line in raw_output.splitlines():
        if not line.strip():
            continue
        lineno, sep, content = line.partition(":")
        if sep and lineno.isdigit():
            lines.append(f"{lineno}: {json_message(content) or content}")
        else:
            lines.append(json_message(line) or line)
    return truncate_text("\n".join(lines), max_chars, suffix=SEARCH_TRUNCATED_NOTICE)


class ContextManager:
    def __init__(self, context_folder: str) -> None:
        self._context_folder = Path(context_folder)
        self.lock = Lock()
        if not self._context_folder.exists():
            self._context_folder.mkdir()

    async def get_context(self, conversation_id: str, offset: int, length: int = 10):
        """
        获取当前聊天记录的上下文

        Args:
            conversation_id: 会话的 id
            offset: 文件行数偏移
            length: 文件行数，默认为 10 行
        """
        logger.debug("Get context: %s %s", conversation_id, length)
        return jsonl_list_message(
            await read_jsonl(
                sanitize_path(self._context_folder, conversation_id), offset, length
            )
        )

    async def get_nearest_context(self, conversation_id: str, length: int):
        logger.debug("Get nearest context: %s %s", conversation_id, length)
        return jsonl_list_message(
            await read_jsonl_rev(
                sanitize_path(self._context_folder, conversation_id), length
            )
        )

    async def search_context(self, conversation_id: str, pattern: str) -> str:
        """
        在聊天记录中搜索关键字，返回带行号的匹配消息（最多 30 条，超长会截断），行号可作为 get_context 的 offset 使用

        Args:
            conversation_id: 会话的 id
            pattern: 搜索 pattern, 格式为 ripgrep 支持的正则（不区分大小写）
        """
        logger.debug("Search context: %s %s", conversation_id, pattern)
        path = sanitize_path(self._context_folder, conversation_id)
        if not pattern or not await AsyncPath(path).is_file():
            return ""
        proc = await create_subprocess_exec(
            "rg",
            "-n",
            "-i",
            "--max-count",
            str(SEARCH_MAX_MATCHES),
            "--",
            pattern,
            str(path),
            stdout=PIPE,
            stderr=PIPE,
        )
        try:
            stdout, stderr = await wait_for(proc.communicate(), timeout=SEARCH_TIMEOUT)
        except TimeoutError:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()
            logger.warning("Search context timeout: %s %s", conversation_id, pattern)
            return ""
        if proc.returncode != 0:
            if proc.returncode != 1:
                logger.warning(
                    "Search context failed (code=%s): %s",
                    proc.returncode,
                    stderr.decode(errors="replace").strip(),
                )
            return ""
        return _format_search_results(stdout.decode(errors="replace"))

    async def add_context(self, conversation_id: str, message: MessageDetail):
        """
        加入当前的聊天记录
        """
        logger.debug("Add context: %s %s", conversation_id, message)
        async with self.lock:
            await append_jsonl(
                sanitize_path(self._context_folder, conversation_id), message._asdict()
            )
