from base64 import b64encode
from collections import defaultdict, deque
from dataclasses import dataclass
from hashlib import sha256

from agents import ToolOutputImage
from httpx import AsyncClient, HTTPError

from ..logger import get_logger

logger = get_logger()

DEFAULT_MAX_PER_CONVERSATION = 5
DEFAULT_MAX_IMAGE_BYTES = 1 * 1024 * 1024
DEFAULT_DOWNLOAD_TIMEOUT = 10.0


@dataclass
class CachedImage:
    image_id: str
    url: str
    data_url: str | None = None


class ImageCacheManager:
    """
    基于纯内存滚动窗口的会话图片缓存管理器。
    按 conversation_id 保存最近 N 条图片链接，调用 read_image 时按需下载。
    """

    def __init__(
        self,
        *,
        max_per_conversation: int = DEFAULT_MAX_PER_CONVERSATION,
        max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
        download_timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
    ) -> None:
        self.max_per_conversation = max_per_conversation
        self.max_image_bytes = max_image_bytes
        self.download_timeout = download_timeout
        self._cache: defaultdict[str, deque[CachedImage]] = defaultdict(
            lambda: deque(maxlen=self.max_per_conversation)
        )

    def register(
        self,
        conversation_id: str,
        url: str,
        *,
        declared_size: int | None = None,
    ) -> str | None:
        """
        将图片链接登记到对应会话的滚动窗口中，返回短 image_id。
        若 OneBot 上报的文件大小超出上限，直接跳过并返回 None。
        """
        conv_id = conversation_id.strip()
        clean_url = url.strip()
        if not conv_id or not clean_url:
            return None

        if declared_size is not None and declared_size > self.max_image_bytes:
            logger.debug(
                "Skip oversized image: conv=%s size=%s", conv_id, declared_size
            )
            return None

        image_id = sha256(clean_url.encode("utf-8")).hexdigest()[:8]
        self._cache[conv_id].append(CachedImage(image_id=image_id, url=clean_url))
        return image_id

    async def _download_data_url(self, url: str) -> str | None:
        try:
            async with AsyncClient(
                follow_redirects=True, timeout=self.download_timeout
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
        except (HTTPError, TimeoutError, OSError) as e:
            logger.warning("Download image failed (%s): %s", url, e)
            return None

        if not resp.content:
            return None
        content_type = (
            resp.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        )
        mime = content_type if content_type.startswith("image/") else "image/jpeg"
        encoded = b64encode(resp.content).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    async def read_image(
        self, conversation_id: str, image_id: str
    ) -> ToolOutputImage | str:
        """
        查看历史聊天记录中缓存的图片内容

        Args:
            conversation_id: 会话的 id（如 group:123456）
            image_id: 历史消息中 [图片:id=xxx] 对应的图片 id（只需传 xxx）
        """
        conv_id = conversation_id.strip()
        clean_id = image_id.strip().removeprefix("id=")
        logger.debug("Read cached image: %s %s", conv_id, clean_id)

        entry = next(
            (
                item
                for item in self._cache.get(conv_id, ())
                if item.image_id == clean_id
            ),
            None,
        )
        if entry is None:
            return "未找到该图片，可能已超出缓存窗口或不属于当前会话"

        if entry.data_url is None:
            entry.data_url = await self._download_data_url(entry.url)
        if entry.data_url is None:
            return "图片加载失败，无法查看"
        return ToolOutputImage(image_url=entry.data_url, detail="auto")
