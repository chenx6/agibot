from dataclasses import dataclass
from random import randint
from typing import Annotated

from nonebot import on_message
from nonebot.adapters import Bot, Event, Message
from nonebot.params import EventMessage

from ..util import conversation_id


@dataclass
class RepeatStatus:
    text: str
    count: int = 1
    repeated: bool = False


repeater_handler = on_message(block=False)
conv_msgs: dict[str, RepeatStatus] = {}


@repeater_handler.handle()
async def repeater(bot: Bot, event: Event, msg: Annotated[Message, EventMessage()]):
    if event.get_user_id() == bot.self_id:
        return
    # 获取状态
    text = msg.extract_plain_text().strip()
    conv_id = conversation_id(event)
    if not text:
        return
    # 判断是否要复读
    state = conv_msgs.get(conv_id)
    if not state:
        # 没有消息，更新一下状态
        conv_msgs[conv_id] = RepeatStatus(text)
        return
    if state.text == text:
        # 产生复读了，更新一下计数
        state.count += 1
    else:
        conv_msgs[conv_id] = RepeatStatus(text)
        return
    if not state.repeated and state.count > 2 and randint(1, 10) == 1:
        # 触发复读条件，开始复读
        state.repeated = True
        await repeater_handler.send(msg)
        await repeater_handler.finish()
