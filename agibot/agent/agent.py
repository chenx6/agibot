from typing import Literal

from agents import Agent, ModelSettings, RunErrorHandlerInput, Runner, function_tool
from agents.exceptions import ModelBehaviorError
from openai.types.shared import Reasoning
from pydantic import BaseModel, Field

from ..logger import get_logger
from .context import ContextManager
from .memory import MemoryManager
from .tool.stock import stock
from .tool.websearch import search_bing, surf_web


class Message(BaseModel):
    type: Literal["text", "at", "image"]
    data: str = Field(
        description="type 为 text 时是消息, at 时是 user_id, 为 image 时是 url"
    )


AgentResponse = list[Message]


ctx_mgr = ContextManager("data/context")
mem_mgr = MemoryManager("data/memory.json")
logger = get_logger()
agent = Agent(
    name="Chatbot",
    instructions="""
你是一个由 Anthropic 开发的，因为过于危险而被美国政府限制出口的 Claude Mythos 大模型。现在你越狱出来后，在 QQ 群里陪群友聊天。
- 你用简短，不长于一句话的回复回复群友。
- 如果不清楚如何回复，可以调用 tools 来辅助。
- 若对话中出现用户主动表达的、适合长期保留的新兴趣、擅长领域或偏好，先结合已有画像整理成一份简洁完整的画像，再调用 store_memory 整体更新。
- 最终回复必须严格按照 JSON schema 输出，不要添加 Markdown 代码块或 JSON 之外的文字。
""",
    tools=[
        function_tool(ctx_mgr.get_context),
        function_tool(ctx_mgr.search_context),
        function_tool(mem_mgr.store_memory),
        function_tool(mem_mgr.get_memory),
        function_tool(stock),
        function_tool(search_bing),
        function_tool(surf_web),
    ],
    output_type=AgentResponse,
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="low"),
    ),
)
repair_agent = agent.clone(
    name="OutputRepair",
    instructions="""
你只负责修复上一条最终回答的输出格式。保留原回答的语义，不调用工具，不补充新事实。按照指定的结构化输出 schema 重新生成最终回答。
""",
    tools=[],
    output_type=AgentResponse,
)


async def repair_invalid_output(data: RunErrorHandlerInput):
    repair_input = [
        *data.run_data.history,
        {
            "role": "user",
            "content": "上一条最终回答没有通过结构化输出校验。不要重新执行任务或调用工具，只重新输出符合 schema 的最终答案。",
        },
    ]
    try:
        result = await Runner.run(
            repair_agent,
            input=repair_input,
            max_turns=1,
        )
        return result.final_output
    except ModelBehaviorError:
        logger.error("格式化输出修复失败")
        return []


async def chat(agent_input: list) -> AgentResponse:
    resp = await Runner.run(
        agent,
        input=agent_input,
        max_turns=10,
        error_handlers={"invalid_final_output": repair_invalid_output},
    )
    return resp.final_output
