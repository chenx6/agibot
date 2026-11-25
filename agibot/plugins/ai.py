from random import randint
from time import time
from typing import Annotated

from nonebot import on_message
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment
from nonebot.params import EventMessage
from nonebot.rule import to_me

from ..agent.agent import AgentResponse, chat, ctx_mgr, img_cache, mem_mgr
from ..agent.model import MessageDetail
from ..util import conversation_id, readable_time

context_matcher = on_message(priority=10)
tome_matcher = on_message(rule=to_me(), priority=1, block=True)
_SEG_PLACEHOLDERS = {
    "image": "[图片]",
    "video": "[视频]",
    "record": "[语音]",
    "forward": "[合并转发]",
    "face": "[表情]",
    "json": "[卡片消息]",
}


def _nickname(event: Event):
    if isinstance(event, MessageEvent):
        return event.sender.nickname


def _reply_sender(event: Event) -> str | None:
    if not isinstance(event, MessageEvent) or not event.reply:
        return
    sender = event.reply.sender
    user_id = str(sender.user_id or "")
    nickname = (sender.nickname or "").strip()
    if nickname and user_id and nickname != user_id:
        return f"{nickname}({user_id})"
    return nickname or user_id or None


def _reply_to(event: Event) -> str | None:
    if not isinstance(event, MessageEvent) or not event.reply:
        return
    who = _reply_sender(event)
    text = " ".join(message_to_text(event.reply.message).split())
    if who and text:
        return f"{who}: {text}"
    return text or who or None


def _image_url(seg: MessageSegment) -> str | None:
    if url := seg.data.get("url"):
        return url
    if (file := seg.data.get("file")) and file.startswith(("http://", "https://")):
        return file
    return None


def _image_size(seg: MessageSegment) -> int | None:
    val = seg.data.get("file_size")
    if not val:
        return
    try:
        val = int(val)
        return val if val > 0 else None
    except (TypeError, ValueError):
        return


def _cache_images(msg: Message, conv_id: str) -> dict[str, str]:
    image_ids: dict[str, str] = {}
    for seg in msg:
        if (
            seg.type == "image"
            and (url := _image_url(seg))
            and (
                img_id := img_cache.register(
                    conv_id, url, declared_size=_image_size(seg)
                )
            )
        ):
            image_ids[url] = img_id
    return image_ids


def _segment_to_text(
    seg: MessageSegment, image_ids: dict[str, str] | None = None
) -> str:
    if seg.type == "text":
        return str(seg.data.get("text", ""))
    if seg.type == "at":
        qq = seg.data.get("qq") or seg.data.get("user_id") or ""
        return f"[@{qq}]" if qq else "[@]"
    if seg.type == "reply":
        return ""
    if (
        seg.type == "image"
        and image_ids
        and (url := _image_url(seg))
        and (img_id := image_ids.get(url))
    ):
        return f"[图片:id={img_id}]"
    return _SEG_PLACEHOLDERS.get(seg.type, f"[{seg.type}]")


def message_to_text(msg: Message, image_ids: dict[str, str] | None = None) -> str:
    """
    将 OneBot Message 转换为可读文本
    """
    return "".join(_segment_to_text(seg, image_ids) for seg in msg).strip()


def msg_detail(msg: Message, event: Event):
    conv_id = conversation_id(event)
    image_ids = _cache_images(msg, conv_id)
    text = message_to_text(msg, image_ids)
    user_id = event.get_user_id()
    nickname = _nickname(event)
    timestamp = time()
    return MessageDetail(
        conv_id,
        user_id,
        nickname,
        text,
        timestamp,
        msg.to_rich_text(0),
        _reply_to(event),
    )


async def assemble_context(detail: MessageDetail):
    parts = [f"当前会话：{detail.conversation_id}"]

    if detail.conversation_id.startswith("group:") and (
        group_mem := mem_mgr.get_memory("group", detail.conversation_id)
    ):
        parts.append(f"本群长期记忆：\n{group_mem}")

    last_ctx = await ctx_mgr.get_nearest_context(detail.conversation_id, 20)
    parts.append("这是前面的消息记录：\n" + "\n".join(last_ctx))
    parts.append(
        f"这是当前的消息：[{readable_time(detail.timestamp)}] "
        f"{detail.nickname or detail.user_id}({detail.user_id}): "
    )
    return "\n".join(parts)


def response_msg(resp: AgentResponse):
    msg_list = []
    for msg in resp:
        match msg.type:
            case "text":
                msg_list.append(MessageSegment.text(msg.data))
            case "at":
                msg_list.append(MessageSegment.at(msg.data))
            case "image":
                msg_list.append(MessageSegment.image(msg.data))
    return Message(msg_list)


def _append_text(content: list[dict], text: str) -> None:
    """
    组装并合并 text 消息
    """
    if not text:
        return
    if content and content[-1]["type"] == "input_text":
        content[-1]["text"] += text
    else:
        content.append({"type": "input_text", "text": text})


def msg_request(msg: Message, context: str):
    content: list[dict] = []
    _append_text(content, context)
    for seg in msg:
        if seg.type == "image" and (url := _image_url(seg)):
            content.append(
                {
                    "type": "input_image",
                    "image_url": url,
                    "detail": "auto",
                }
            )
        else:
            _append_text(content, _segment_to_text(seg))
    return [{"role": "user", "content": content}]


async def handle_message(
    event: Event,
    msg: Message,
    *,
    should_reply: bool,
) -> Message | None:
    detail = msg_detail(msg, event)
    # 延迟组装 context，且需在写入当前消息前拉取历史
    if should_reply:
        context = await assemble_context(detail)
    else:
        context = ""
    await ctx_mgr.add_context(
        detail.conversation_id,
        detail,
    )
    if not should_reply:
        return
    # 和 Agent 交互
    req = msg_request(msg, context)
    if isinstance(event, MessageEvent) and event.reply:
        if reply_sender := _reply_sender(event):
            reply_prefix = f"下面是引用的回复（{reply_sender}）："
        else:
            reply_prefix = "下面是引用的回复："
        req += msg_request(event.reply.message, reply_prefix)
    resp = await chat(req)
    resp_msg = response_msg(resp)
    if not resp_msg:
        return
    # 记录并返回 bot 发言
    resp_image_ids = _cache_images(resp_msg, detail.conversation_id)
    await ctx_mgr.add_context(
        detail.conversation_id,
        MessageDetail(
            detail.conversation_id,
            "0",
            "[bot]",
            message_to_text(resp_msg, resp_image_ids),
            time(),
            resp_msg.to_rich_text(0),
        ),
    )
    return resp_msg


@context_matcher.handle()
async def record_reply_message(event: Event, msg: Annotated[Message, EventMessage()]):
    should_reply = randint(1, 1000) == 1
    if resp_msg := await handle_message(event, msg, should_reply=should_reply):
        await context_matcher.finish(resp_msg)


@tome_matcher.handle()
async def reply(event: Event, msg: Annotated[Message, EventMessage()]):
    if resp_msg := await handle_message(event, msg, should_reply=True):
        await tome_matcher.finish(resp_msg)
