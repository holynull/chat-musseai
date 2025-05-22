from typing import Annotated, cast, Optional
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from langchain_core.prompts import SystemMessagePromptTemplate
from langchain_core.messages import AIMessage, BaseMessage
from langgraph.utils.runnable import RunnableCallable

# 导入自定义工具和提示
from tools.tools_solana_meme import tools
from prompts.prompt_solana_meme import SYSTEM_PROMPT

# 初始化LLM
_llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    max_tokens=4096,
    temperature=0.9,
    streaming=True,
    stream_usage=True,
    verbose=True,
)


# 定义状态类型
class State(TypedDict):
    messages: Annotated[list, add_messages]
    wallet_connected: bool
    wallet_address: str
    current_token: Optional[dict]
    transaction_history: list


# 初始化图构建器
graph_builder = StateGraph(State)


# 格式化消息
def format_messages(state: State) -> list[BaseMessage]:
    system_template = SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT)
    system_message = system_template.format_messages(
        wallet_connected=state["wallet_connected"],
        wallet_address=state["wallet_address"],
    )
    return system_message + state["messages"]


# 调用模型
def call_model_solana_meme(state: State, config: RunnableConfig) -> State:
    llm_with_tools = _llm.bind_tools(tools)
    response = cast(
        AIMessage, llm_with_tools.invoke(format_messages(state=state), config)
    )
    return {"messages": [response]}


# 异步调用模型
async def acall_model_solana_meme(state: State, config: RunnableConfig) -> State:
    llm_with_tools = _llm.bind_tools(tools)
    response = cast(
        AIMessage, await llm_with_tools.ainvoke(format_messages(state), config)
    )
    return {"messages": [response]}


# 创建工具节点
from langgraph.prebuilt import ToolNode, tools_condition

tool_node = ToolNode(tools=tools, name="node_tools_solana_meme")

# 创建LLM节点
node_llm = RunnableCallable(
    call_model_solana_meme, acall_model_solana_meme, name="node_llm_solana_meme"
)

# 构建图
graph_builder.add_node(node_llm.get_name(), node_llm)
graph_builder.add_node(tool_node.get_name(), tool_node)
graph_builder.add_conditional_edges(
    node_llm.get_name(),
    tools_condition,
    {"tools": tool_node.get_name(), END: END},
)
graph_builder.add_edge(tool_node.get_name(), node_llm.get_name())
graph_builder.add_edge(START, node_llm.get_name())

# 编译图
graph = graph_builder.compile()
graph.name = "graph_solana_meme"
