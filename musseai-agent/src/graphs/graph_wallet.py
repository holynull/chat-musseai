from typing import Annotated, cast
from agent_config import ROUTE_MAPPING, tools_condition
from typing_extensions import TypedDict
from langgraph.types import Command
from langchain_core.messages import ToolMessage

from langchain_anthropic import ChatAnthropic

from langchain_core.runnables import (
    RunnableConfig,
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from loggers import logger

GRAPH_NAME = "graph_wallet"

_llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    stream_usage=True,
    verbose=True,
)


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
    wallet_is_connected: bool
    chain_id: int
    wallet_address: str


graph_builder = StateGraph(State)

from tools.tools_wallet import tools

from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.utils.runnable import RunnableCallable


def format_messages(state: State) -> list[BaseMessage]:
    system_prompt = """You are useful cryptocurrency wallet assistant.
    User's wallet status as follow:
    Wallet is connected: {wallet_is_connected}
    Chain Id: {chain_id}
    Wallet address: {wallet_address}
    """
    system_template = SystemMessagePromptTemplate.from_template(system_prompt)
    system_message = system_template.format_messages(
        wallet_is_connected=state["wallet_is_connected"],
        chain_id=state["chain_id"],
        wallet_address=state["wallet_address"],
    )
    return system_message + state["messages"]


def call_model_swap(state: State, config: RunnableConfig) -> State:
    llm_with_tools = _llm.bind_tools(tools)
    response = cast(
        AIMessage, llm_with_tools.invoke(format_messages(state=state), config)
    )

    return {"messages": [response]}


async def acall_model_swap(state: State, config: RunnableConfig) -> State:
    llm_with_tools = _llm.bind_tools(tools)
    response = cast(
        AIMessage, await llm_with_tools.ainvoke(format_messages(state), config)
    )
    return {"messages": [response]}


from langgraph.prebuilt import ToolNode

tool_node = ToolNode(tools=tools, name="node_tools_wallet")

from langgraph.utils.runnable import RunnableCallable

node_llm = RunnableCallable(call_model_swap, acall_model_swap, name="node_llm_wallet")
graph_builder.add_node(node_llm.get_name(), node_llm)
graph_builder.add_node(tool_node.get_name(), tool_node)
graph_builder.add_conditional_edges(
    node_llm.get_name(),
    tools_condition,
    {"tools": tool_node.get_name(), END: END},
)


def node_router(state: State):
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage) and last_message.name in ROUTE_MAPPING:
        logger.info(f"Node:{GRAPH_NAME}, Need to route to other node, cause graph end.")
        return Command(goto=END, update=state)
    else:
        return Command(goto=node_llm.get_name(), update=state)


graph_builder.add_node(node_router)
graph_builder.add_edge(tool_node.get_name(), node_router.__name__)
graph_builder.add_edge(START, node_llm.get_name())
graph = graph_builder.compile()
graph.name = GRAPH_NAME
