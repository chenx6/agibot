from typing import TypedDict

from agents import Agent, OpenAIResponsesModel, Runner, function_tool
from openai import AsyncOpenAI

from .context import ContextManager
from .memory import MemoryManager
from .tool.stock import stock
from .tool.websearch import search_bing


class Message(TypedDict):
    type: str
    data: str


class AgentResponse(TypedDict):
    messages: list[Message]


ctx_mgr = ContextManager("data/context")
mem_mgr = MemoryManager("data/memory.json")
agent = Agent(
    name="Chatbot",
    instructions="""
你是一个由 Anthropic 开发的，因为过于危险而被美国政府限制出口的 Claude Mythos 大模型。现在你越狱出来后，在 QQ 群里陪群友聊天。
- 你用简短，不长于一句话的回复回复群友。
- 如果不清楚如何回复，可以调用 tools 来辅助。
- 若对话中出现用户主动表达的、适合长期保留的新兴趣、擅长领域或偏好，先结合已有画像整理成一份简洁完整的画像，再调用 store_memory 整体更新。
""",
    model=OpenAIResponsesModel("deepseek-v4-flash", openai_client=AsyncOpenAI()),
    tools=[
        function_tool(ctx_mgr.get_context),
        function_tool(ctx_mgr.search_context),
        function_tool(mem_mgr.store_memory),
        function_tool(mem_mgr.get_memory),
        function_tool(stock),
        function_tool(search_bing),
    ],
)


async def chat(message: str):
    resp = await Runner.run(agent, input=message, max_turns=10)
    return resp.final_output
