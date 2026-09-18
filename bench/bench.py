from pathlib import Path

from pytest import mark

from agibot.agent.agent import chat, ctx_mgr


@mark.asyncio
async def test_benchmark_hange():
    ctx_mgr._context_folder = Path("bench/input")
    res = await chat("conversation_id=20260916_1.txt 推测一下群聊记录里说的韩哥是谁")
    assert "user_d" in res
