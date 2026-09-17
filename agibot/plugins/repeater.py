from nonebot import on_message
from nonebot.adapters import Message
from nonebot.params import EventMessage

repeater_handler = on_message(block=False)
last_msg = ""
sent_msgs: list[str] = []


@repeater_handler.handle()
async def repeater(msg: Message = EventMessage()):
    global last_msg
    curr_msg = msg.extract_plain_text().strip()
    if curr_msg in sent_msgs:
        # 复读过了，不再复读
        return
    if curr_msg and curr_msg == last_msg:
        # 如果已经有人在复读，则跟着复读
        await repeater_handler.send(curr_msg)
        # 更新复读消息列表
        sent_msgs.append(curr_msg)
        if len(sent_msgs) > 5:
            sent_msgs.pop(0)
    last_msg = curr_msg
