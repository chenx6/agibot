from base64 import b64encode

import pytest
from agents import ToolOutputImage
from httpx import AsyncClient, MockTransport, Request, Response
from nonebot.adapters.onebot.v11 import Message, MessageSegment

import agibot.agent.image_cache as image_cache_mod
import agibot.plugins.ai as ai_mod
from agibot.agent.image_cache import ImageCacheManager

SAMPLE_BYTES = b"\xff\xd8\xff\xe0img"
EXPECTED_URL = f"data:image/jpeg;base64,{b64encode(SAMPLE_BYTES).decode()}"


def _mock_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    real_client, transport = AsyncClient, MockTransport(handler)
    monkeypatch.setattr(
        image_cache_mod,
        "AsyncClient",
        lambda **kw: real_client(transport=transport, **kw),
    )


@pytest.mark.asyncio
async def test_image_cache_manager(monkeypatch: pytest.MonkeyPatch):
    calls = 0

    def handler(req: Request) -> Response:
        nonlocal calls
        calls += 1
        return (
            Response(404)
            if req.url.path == "/fail"
            else Response(200, content=SAMPLE_BYTES)
        )

    _mock_client(monkeypatch, handler)
    mgr = ImageCacheManager(max_per_conversation=2, max_image_bytes=1024)

    assert mgr.register("group:1", "https://ex/big.jpg", declared_size=2048) is None
    id1 = mgr.register("group:1", "https://ex/1.jpg")
    id2 = mgr.register("group:1", "https://ex/2.jpg")
    id3 = mgr.register("group:1", "https://ex/fail")
    assert id1 and id2 and id3 and calls == 0

    # 窗口为 2，加入 id3 后淘汰最早的 id1
    assert isinstance(await mgr.read_image("group:1", id1), str)
    assert isinstance(await mgr.read_image("group:2", id2), str)

    res = await mgr.read_image("group:1", f"id={id2}")
    assert isinstance(res, ToolOutputImage) and res.image_url == EXPECTED_URL
    assert await mgr.read_image("group:1", id2) == res and calls == 1
    assert isinstance(await mgr.read_image("group:1", id3), str)


def test_message_to_text_image_id(monkeypatch: pytest.MonkeyPatch):
    mgr = ImageCacheManager(max_image_bytes=1024)
    monkeypatch.setattr(ai_mod, "img_cache", mgr)

    ok = MessageSegment("image", {"url": "https://ex/a.jpg", "file_size": "256"})
    big = MessageSegment("image", {"url": "https://ex/b.jpg", "file_size": "4096"})
    msg = Message([MessageSegment.text("看"), ok, big])
    image_ids = ai_mod._cache_images(msg, "g:1")

    text = ai_mod.message_to_text(msg, image_ids)
    assert text.startswith("看[图片:id=") and text.endswith("][图片]")
    assert ai_mod.message_to_text(Message([ok])) == "[图片]"
