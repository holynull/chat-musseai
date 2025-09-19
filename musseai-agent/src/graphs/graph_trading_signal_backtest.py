from typing import Annotated, cast
from agent_config import ROUTE_MAPPING
from langgraph.prebuilt import tools_condition
from langgraph.types import Command
from typing_extensions import TypedDict
from langchain_core.messages import HumanMessage,ToolMessage

from langchain_anthropic import ChatAnthropic

from langchain_core.runnables import (
    RunnableConfig,
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from loggers import logger

GRAPH_NAME = "graph_signal_backtest"

_llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    temperature=0.3,  # Lower temperature for more consistent trading advice
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


graph_builder = StateGraph(TradingStrategyGraphState)

from tools.tools_trading_signal_backtest import tools
from tools.tools_agent_router import generate_routing_tools

from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)

from langchain_core.messages import AIMessage
from langgraph.utils.runnable import RunnableCallable

from prompts.prompt_signal_backtest import system_prompt

system_template = SystemMessagePromptTemplate.from_template(system_prompt)


def call_model_trading_strategy(
    state: TradingStrategyGraphState, config: RunnableConfig
) -> TradingStrategyGraphState:
    """
    Main LLM node for generating trading strategies.
    Uses enhanced prompt and specialized tools for short-term trading analysis.
    """
    llm_with_tools = _llm.bind_tools(tools + generate_routing_tools())
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
    llm_with_tools = _llm.bind_tools(tools + generate_routing_tools())
    system_message = system_template.format_messages(
        time_zone=state["time_zone"],
    )
    response = cast(
        AIMessage,
        await llm_with_tools.ainvoke(system_message + state["messages"], config),
    )
    return {"messages": [response]}


async def judgement_regenerate_signals(state: TradingStrategyGraphState):
    # llm_with_tools = _llm.bind_tools(tools)
    system_prompt = """
    You are a cryptocurrency trading expert. Provide simple, direct trading signals.

    ## Language Rules:
    - If user writes in Chinese → respond in Chinese
    - If user writes in English → respond in English  
    - If user writes in other languages → respond in that language
    - Match the user's communication style

    If regenerating signal is necessary, regenerate the new signal automatically.
    """
    system_template = SystemMessagePromptTemplate.from_template(system_prompt)
    system_message = system_template.format_messages()
    human = HumanMessage(
        """Please analyze whether a new trading signal needs to be generated based on current market conditions and data.

If signal regeneration is required, conclude your response with: "**SIGNAL REGENERATION REQUIRED**"

Important: Respond in the same language as the previous user's message, regardless of the language used in this prompt.
"""
    )
    # last_ai_message=cast(AIMessage,state["messages"][-1])
    response = cast(
        AIMessage,
        await _llm.ainvoke(system_message + state["messages"] + [human]),
    )
    # last_ai_message = cast(AIMessage, state["messages"][-1])
    # last_ai_message.content += response.content
    return {"messages": [HumanMessage(content=response.content)]}


from langgraph.prebuilt import ToolNode

tool_node = ToolNode(
    tools=tools + generate_routing_tools(), name="node_tools_trading_signal_backtest"
)

from langgraph.utils.runnable import RunnableCallable

node_llm = RunnableCallable(
    call_model_trading_strategy,
    acall_model_trading_strategy,
    name="node_llm_trading_signal_backtest",
)
def node_router(state: TradingStrategyGraphState):
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage) and last_message.name in ROUTE_MAPPING:
        logger.info(f"Node:{GRAPH_NAME}, Need to route to other node, cause graph end.")
        return Command(goto=END, update=state)
    else:
        return Command(goto=node_llm.get_name(), update=state)
graph_builder.add_node(node_router)
graph_builder.add_node(node_llm.name, node_llm)
graph_builder.add_node(tool_node.get_name(), tool_node)
graph_builder.add_conditional_edges(
    node_llm.get_name(),
    tools_condition,
    {"tools": tool_node.get_name(), END: judgement_regenerate_signals.__name__},
)
graph_builder.add_edge(judgement_regenerate_signals.__name__, END)
graph_builder.add_node(
    judgement_regenerate_signals, judgement_regenerate_signals.__name__
)
graph_builder.add_edge(tool_node.get_name(), node_router.__name__)
graph_builder.add_edge(START, node_llm.get_name())
graph = graph_builder.compile()
graph.name = GRAPH_NAME
