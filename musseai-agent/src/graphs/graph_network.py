import os
from typing import Annotated, Optional, cast
from typing_extensions import TypedDict
from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import (
    RunnableConfig,
)
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    BaseMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.utils.runnable import RunnableCallable
from langgraph.types import Command
from tools.tools_agent_router import tools as tools_router
from agent_config import ROUTE_MAPPING

from prompts.prompt_chatbot import system_prompt

# import subgraph
from graphs.graph_wallet import graph as wallet_graph
from graphs.graph_search import graph as search_graph
from graphs.graph_swap import graph as swap_graph
from graphs.graph_quote import graph as quote_graph
from graphs.graph_image import graph as image_graph
from graphs.graph_infura import graph as infura_graph
from graphs.graph_solana import graph as solana_graph
from graphs.graph_crypto_portfolios import graph as crypto_portfolios_graph
from graphs.graph_trading_signal import graph as trading_signal_graph
from graphs.graph_trading_signal_backtest import graph as trading_signal_backtest_graph
from loggers import logger

GRAPH_NAME = "graph_network"

subgraphs = [
    wallet_graph,
    search_graph,
    swap_graph,
    quote_graph,
    image_graph,
    infura_graph,
    solana_graph,
    crypto_portfolios_graph,
    trading_signal_graph,
    trading_signal_backtest_graph,
]

llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    # model="claude-3-5-haiku-latest",
    max_tokens=4096,
    temperature=0.7,
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
    time_zone: str
    llm: str
    user_id: str


graph_builder = StateGraph(State)

system_template = SystemMessagePromptTemplate.from_template(system_prompt)


async def acall_model(state: State, config: RunnableConfig):
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage) and last_message.name in ROUTE_MAPPING:
        next_node = ROUTE_MAPPING[last_message.name]
        logger.info(f"Node: {GRAPH_NAME}, goto {next_node}")
        return Command(goto=next_node, update=state)
    elif isinstance(last_message, AIMessage):
        return Command(goto=END, update=state)

    llm_configed = cast(BaseChatModel, llm).bind_tools(tools_router)
    system_message = system_template.format_messages(
        wallet_is_connected=state["wallet_is_connected"],
        chain_id=state["chain_id"],
        wallet_address=state["wallet_address"],
        time_zone=state["time_zone"],
    )
    response = await llm_configed.ainvoke(system_message + state["messages"])
    ai_message = cast(AIMessage, response)
    next_node = END
    if len(ai_message.tool_calls) > 0:
        tool_call = ai_message.tool_calls[0]
        tool_name = tool_call.get("name")
        if ROUTE_MAPPING.get(tool_name, None):
            next_node = ROUTE_MAPPING[tool_name]
        else:
            logger.error(f"{GRAPH_NAME} note_router point to a route {tool_name}")
            response = await llm_configed.ainvoke(
                system_message
                + state["messages"]
                + [response, AIMessage("Sorry, I returned a wrong tool name!")]
            )
            ai_message = cast(AIMessage, response)
            if len(ai_message.tool_calls) > 0:
                tool_call = ai_message.tool_calls[0]
                tool_name = tool_call.get("name")
                if ROUTE_MAPPING.get(tool_name, None):
                    next_node = ROUTE_MAPPING[tool_name]
                else:
                    logger.error(
                        f"{GRAPH_NAME} note_router point to a route {tool_name}"
                    )
                    next_node = END
    else:
        state["messages"] += [ai_message]
    logger.info(f"Node: {GRAPH_NAME}, goto {next_node}, after llm handling.")
    return Command(
        goto=next_node,
        update=state,
    )


def call_model(state: State, config: RunnableConfig):
    raise NotImplementedError()


node_router = RunnableCallable(call_model, acall_model, name="node_router")
graph_builder.add_node(node_router)


for graph in subgraphs:
    graph_builder.add_node(graph, graph.get_name())

# add edge
graph_builder.add_edge(START, node_router.get_name())
for graph in subgraphs:
    graph_builder.add_edge(graph.get_name(), node_router.get_name())

graph = graph_builder.compile()
graph.name = GRAPH_NAME
