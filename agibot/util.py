from nonebot.adapters import Event


def conversation_id(event: Event):
    group_id = getattr(event, "group_id", None)
    if group_id:
        return f"group:{group_id}"
    return f"private:{event.get_session_id()}"
