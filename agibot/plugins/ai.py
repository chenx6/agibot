from random import randint
from time import time

from nonebot import on_message
from nonebot.adapters import Event, Message
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import EventMessage
from nonebot.rule import to_me

from ..agent.agent import chat, ctx_mgr
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


@context_matcher.handle()
async def record_reply_message(event: Event, msg: Message = EventMessage()):
    detail = msg_detail(event, msg)
    if not detail.message:
        return
    await ctx_mgr.add_context(
        detail.conversation_id,
        detail,
    )
    context = assemble_context(detail)
    if randint(1, 1000) == 1:
        resp = await chat(context)
        await ctx_mgr.add_context(
            detail.conversation_id,
            MessageDetail(detail.conversation_id, "[bot]", "[bot]", resp, time()),
        )
        await context_matcher.send(resp)
        await context_matcher.finish()


@tome_matcher.handle()
async def reply(event: Event, msg: Message = EventMessage()):
    detail = msg_detail(event, msg)
    if not detail.message:
        return
    await ctx_mgr.add_context(
        detail.conversation_id,
        detail,
    )
    context = assemble_context(detail)
    resp = await chat(context)
    await ctx_mgr.add_context(
        detail.conversation_id,
        MessageDetail(detail.conversation_id, "[bot]", "[bot]", resp, time()),
    )
    await tome_matcher.send(resp)
    await tome_matcher.finish()
