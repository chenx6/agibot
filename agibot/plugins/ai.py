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

context_matcher = on_message(priority=10)
tome_matcher = on_message(rule=to_me(), priority=1, block=True)


def _conversation_id(event: Event):
    group_id = getattr(event, "group_id", None)
    if group_id:
        return f"group:{group_id}"
    return f"private:{event.get_session_id()}"


def _nickname(event: Event):
    if isinstance(event, MessageEvent):
        return event.sender.nickname


def msg_detail(event: Event, msg: Message):
    text = msg.extract_plain_text().strip()
    user_id = event.get_user_id()
    conversation_id = _conversation_id(event)
    nickname = _nickname(event)
    timestamp = time()
    return MessageDetail(conversation_id, user_id, nickname, text, timestamp)


def assemble_context(detail: MessageDetail):
    last_ctx = ctx_mgr.get_context(detail.conversation_id, 20)
    return "这是前面的消息记录：" + "\n".join(last_ctx) + f"这是当前的消息：{detail}"


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


def msg_request(msg: Message, text_msg: str):
    content: list[dict] = [{"type": "input_text", "text": text_msg}]
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
    return [{"role": "user", "content": content}]


@context_matcher.handle()
async def record_reply_message(event: Event, msg: Annotated[Message, EventMessage()]):
    detail = msg_detail(event, msg)
    await ctx_mgr.add_context(
        detail.conversation_id,
        detail,
    )
    if randint(1, 1000) == 1:
        context = assemble_context(detail)
        req = msg_request(msg, context)
        if not req:
            return
        resp = await chat(req)
        resp_msg = response_msg(resp)
        await ctx_mgr.add_context(
            detail.conversation_id,
            MessageDetail(detail.conversation_id, "[bot]", "[bot]", str(resp), time()),
        )
        if not resp:
            return
        await context_matcher.send(resp_msg)
        await context_matcher.finish()


@tome_matcher.handle()
async def reply(event: Event, msg: Annotated[Message, EventMessage()]):
    detail = msg_detail(event, msg)
    await ctx_mgr.add_context(
        detail.conversation_id,
        detail,
    )
    context = assemble_context(detail)
    req = msg_request(msg, context)
    if isinstance(event, MessageEvent) and event.reply:
        req += msg_request(event.reply.message, "下面是引用的回复")
    if not req:
        return
    resp = await chat(req)
    resp_msg = response_msg(resp)
    if not resp_msg:
        return
    await ctx_mgr.add_context(
        detail.conversation_id,
        MessageDetail(detail.conversation_id, "[bot]", "[bot]", str(resp), time()),
    )
    await tome_matcher.send(resp_msg)
    await tome_matcher.finish()
