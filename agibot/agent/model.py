from typing import NamedTuple


class MessageDetail(NamedTuple):
    conversation_id: str
    user_id: str
    nickname: str | None
    message: str
    timestamp: float
