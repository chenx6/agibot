from datetime import datetime
from zoneinfo import ZoneInfo

from nonebot.adapters import Event

tz = ZoneInfo("Asia/Shanghai")


def conversation_id(event: Event):
    group_id = getattr(event, "group_id", None)
    if group_id:
        return f"group:{group_id}"
    return f"private:{event.get_session_id()}"


def readable_time(timestamp: float):
    return datetime.fromtimestamp(timestamp, tz=tz).strftime("%Y-%m-%d %H:%M:%S")
