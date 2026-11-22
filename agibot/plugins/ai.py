from random import randint
from time import time
from typing import Annotated

from nonebot import on_message
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment
from nonebot.params import EventMessage
from nonebot.rule import to_me

from ..agent.agent import AgentResponse, chat, ctx_mgr
from ..agent.model import MessageDetail
from ..util import conversation_id, readable_time

context_matcher = on_message(priority=10)
tome_matcher = on_message(rule=to_me(), priority=1, block=True)


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


def message_to_text(msg: Message) -> str:
    """
    将 OneBot Message 转换为可读文本
    """
    parts: list[str] = []
    for seg in msg:
        match seg.type:
            case "text":
                parts.append(str(seg.data.get("text", "")))
            case "at":
                qq = seg.data.get("qq") or seg.data.get("user_id") or ""
                parts.append(f"[@{qq}]" if qq else "[@]")
            case "image":
                parts.append("[图片]")
            case "video":
                parts.append("[视频]")
            case "record":
                parts.append("[语音]")
            case "forward":
                parts.append("[合并转发]")
            case "face":
                parts.append("[表情]")
            case "json":
                parts.append("[卡片消息]")
            case "reply":
                continue
            case _:
                parts.append(f"[{seg.type}]")
    return "".join(parts).strip()


def msg_detail(msg: Message, event: Event):
    text = message_to_text(msg)
    user_id = event.get_user_id()
    conv_id = conversation_id(event)
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


def assemble_context(detail: MessageDetail):
    last_ctx = ctx_mgr.get_nearest_context(detail.conversation_id, 20)
    return (
        f"当前会话：{detail.conversation_id}\n"
        f"这是前面的消息记录：\n" + "\n".join(last_ctx) + "\n"
        f"这是当前的消息：[{readable_time(detail.timestamp)}] "
        f"{detail.nickname or detail.user_id}({detail.user_id}): "
    )


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


def msg_request(msg: Message, context: str):
    content: list[dict] = [{"type": "input_text", "text": context}]
    for seg in msg:
        match seg.type:
            case "image":
                url = None
                if url := seg.data.get("url"):
                    pass
                elif file := seg.data.get("file"):
                    if file.startswith(("http://", "https://")):
                        url = file
                    elif file.startswith("file://"):
                        # TODO
                        pass
                if url:
                    content.append(
                        {
                            "type": "input_image",
                            "image_url": url,
                            "detail": "auto",
                        }
                    )
            case "text":
                content.append({"type": "input_text", "text": str(seg)})
            case _:
                content.append(
                    {
                        "type": "input_text",
                        "text": seg.to_rich_text(0),
                    }
                )
    return [{"role": "user", "content": content}]


@context_matcher.handle()
async def record_reply_message(event: Event, msg: Annotated[Message, EventMessage()]):
    detail = msg_detail(msg, event)
    if randint(1, 1000) == 1:
        context = assemble_context(detail)  # 延迟组装 context, 降低组装消耗
        await ctx_mgr.add_context(
            detail.conversation_id,
            detail,
        )
        req = msg_request(msg, context)
        if isinstance(event, MessageEvent) and event.reply:
            if reply_sender := _reply_sender(event):
                reply_prefix = f"下面是引用的回复（{reply_sender}）："
            else:
                reply_prefix = "下面是引用的回复："
            req += msg_request(event.reply.message, reply_prefix)
        if not req:
            return
        resp = await chat(req)
        resp_msg = response_msg(resp)
        if not resp_msg:
            return
        await ctx_mgr.add_context(
            detail.conversation_id,
            MessageDetail(
                detail.conversation_id,
                "0",
                "[bot]",
                message_to_text(resp_msg),
                time(),
                resp_msg.to_rich_text(0),
            ),
        )
        await context_matcher.send(resp_msg)
        await context_matcher.finish()
    else:
        await ctx_mgr.add_context(
            detail.conversation_id,
            detail,
        )


@tome_matcher.handle()
async def reply(event: Event, msg: Annotated[Message, EventMessage()]):
    detail = msg_detail(msg, event)
    context = assemble_context(detail)
    await ctx_mgr.add_context(
        detail.conversation_id,
        detail,
    )
    req = msg_request(msg, context)
    if isinstance(event, MessageEvent) and event.reply:
        reply_sender = _reply_sender(event)
        if reply_sender := _reply_sender(event):
            reply_prefix = f"下面是引用的回复（{reply_sender}）："
        else:
            reply_prefix = "下面是引用的回复："
        req += msg_request(event.reply.message, reply_prefix)
    if not req:
        return
    resp = await chat(req)
    resp_msg = response_msg(resp)
    if not resp_msg:
        return
    await ctx_mgr.add_context(
        detail.conversation_id,
        MessageDetail(
            detail.conversation_id,
            "0",
            "[bot]",
            message_to_text(resp_msg),
            time(),
            resp_msg.to_rich_text(0),
        ),
    )
    await tome_matcher.send(resp_msg)
    await tome_matcher.finish()
