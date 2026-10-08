from asyncio import CancelledError, create_task, sleep
from json import JSONDecodeError, loads
from os import environ
from typing import TYPE_CHECKING, NotRequired, TypedDict

from anyio import open_file
from nonebot import get_bots, get_driver
from nonebot.adapters.onebot.v11 import MessageSegment
from redis.asyncio import Redis
from redis.exceptions import TimeoutError

from ..logger import get_logger

if TYPE_CHECKING:
    from asyncio import Task

logger = get_logger()
LOADED = False
MQ_KEY = "message"
_background_task = None
if environ.get("REDIS_HOST"):
    _client = Redis(
        host=environ["REDIS_HOST"],
        port=int(environ["REDIS_PORT"]),
        password=environ.get("REDIS_PASSWORD"),
        socket_timeout=30,
        health_check_interval=30,
        socket_keepalive=True,
    )
    logger.info("Redis init done")
    LOADED = True


class QueueMessage(TypedDict):
    type: str
    text: NotRequired[str]
    image: NotRequired[str]
    video: NotRequired[str]


async def get_type_dispatch() -> dict[str, list[int]]:
    async with await open_file("data/dispatch.json") as f:
        return loads(await f.read())


async def get_message() -> QueueMessage | None:
    try:
        result = await _client.brpop(MQ_KEY, 5)
    except TimeoutError:
        return
    if not result:
        return
    _, data = result
    try:
        return loads(data)
    except (JSONDecodeError, TypeError):
        return


def to_msgseg(msg: QueueMessage):
    if txt := msg.get("text"):
        return MessageSegment.text(txt)
    elif img := msg.get("image"):
        return MessageSegment.image(img)
    elif vid := msg.get("video"):
        return MessageSegment.video(vid)


async def loop():
    while LOADED:
        bots = list(get_bots().values())
        if not bots:
            # No bot connected yet; wait instead of consuming messages.
            await sleep(3)
            continue
        msg = await get_message()
        if not msg:
            continue
        dsp = await get_type_dispatch()
        msgseg = to_msgseg(msg)
        if not msgseg:
            continue
        logger.info("Get message from redis %s", msgseg)
        groups = dsp.get(msg["type"], [])
        for bot in bots:
            try:
                for group in groups:
                    await bot.call_api("send_group_msg", group_id=group, message=msgseg)
                logger.info("Send message to %s done", groups)
            except Exception:
                logger.exception("Send message to %s failed", groups)


def handle_task_result(task: "Task"):
    try:
        task.result()
    except CancelledError:
        pass
    except Exception:
        logger.exception("Task failed:")


@get_driver().on_startup
async def start():
    global _background_task
    _background_task = create_task(loop())
    _background_task.add_done_callback(handle_task_result)


@get_driver().on_shutdown
async def stop():
    global _background_task
    if _background_task:
        _background_task.cancel()
        try:
            await _background_task
        except CancelledError:
            pass
        _background_task = None
