from typing import Annotated, cast
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic

from langchain_core.runnables import (
    RunnableConfig,
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import tools_condition


from langchain_core.messages import ToolMessage
from loggers import logger
from langgraph.types import Command

GRAPH_NAME = "graph_signal_generator"

_llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    temperature=0.7,  # Lower temperature for more consistent trading advice
    streaming=True,
    stream_usage=True,
    verbose=True,
)


class TradingStrategyGraphState(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
    time_zone: str
    symbol:str


graph_builder = StateGraph(TradingStrategyGraphState)

from tools.tools_trading_signal import tools

from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)

from langchain_core.messages import AIMessage
from langgraph.utils.runnable import RunnableCallable

from prompts.prompt_generate_signal import system_prompt

system_template = SystemMessagePromptTemplate.from_template(system_prompt)


def call_model_trading_strategy(
    state: TradingStrategyGraphState, config: RunnableConfig
) -> TradingStrategyGraphState:
    """
    Main LLM node for generating trading strategies.
    Uses enhanced prompt and specialized tools for short-term trading analysis.
    """
    llm_with_tools = _llm.bind_tools(tools)
    system_message = system_template.format_messages(
        time_zone=state["time_zone"],
    )
    response = cast(
        AIMessage, llm_with_tools.invoke(system_message + state["messages"], config)
    )

    return {"messages": [response]}


async def acall_model_trading_strategy(
    state: TradingStrategyGraphState, config: RunnableConfig
) -> TradingStrategyGraphState:
    """
    Async version of the main LLM node for trading strategy generation.
    """
    llm_with_tools = _llm.bind_tools(tools)
    system_message = system_template.format_messages(
        time_zone=state["time_zone"],
    )
    response = cast(
        AIMessage,
        await llm_with_tools.ainvoke(system_message + state["messages"], config),
    )
    return {"messages": [response]}


from langgraph.prebuilt import ToolNode

tool_node = ToolNode(tools=tools, name="node_tools_trading_signal")

from langgraph.utils.runnable import RunnableCallable

node_llm = RunnableCallable(
    call_model_trading_strategy,
    acall_model_trading_strategy,
    name="node_llm_trading_signal",
)


graph_builder.add_node(node_llm.name, node_llm)
graph_builder.add_node(tool_node.get_name(), tool_node)
graph_builder.add_conditional_edges(
    node_llm.get_name(),
    tools_condition,
    {"tools": tool_node.get_name(), END: END},
)

graph_builder.add_edge(tool_node.get_name(), node_llm.get_name())
graph_builder.add_edge(START, node_llm.get_name())
graph = graph_builder.compile()
graph.name = GRAPH_NAME
