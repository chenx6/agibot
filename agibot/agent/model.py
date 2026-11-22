from typing import NamedTuple


class MessageDetail(NamedTuple):
    conversation_id: str
    user_id: str
    nickname: str | None
    message: str
    timestamp: float
    raw: str
    reply_to: str | None = None
