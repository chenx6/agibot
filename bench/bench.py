from pathlib import Path

from pytest import mark

from agibot.agent.agent import chat, ctx_mgr


@mark.asyncio
async def test_benchmark_hange():
    ctx_mgr._context_folder = Path("bench/input")
    agent_input = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "conversation_id=20260916_1.txt 推测一下群聊记录里说的韩哥是谁",
                }
            ],
        }
    ]
    res = await chat(agent_input)
    assert "user_d" in str(res)
