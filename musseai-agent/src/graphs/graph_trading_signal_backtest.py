from typing import Annotated, cast
from langgraph.prebuilt import tools_condition
from typing_extensions import TypedDict
from langchain_core.messages import HumanMessage

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


async def judgement_regenerate_signals(state: TradingStrategyGraphState):
    """
    Analyze backtest results and determine if signal regeneration is needed.

    Returns:
        - {"messages": []} if no regeneration needed
        - {"messages": [HumanMessage]} if regeneration required
    """
    system_prompt = """
    You are a cryptocurrency trading expert. Analyze the provided backtest results and determine if a new trading signal needs to be generated.

    ## Language Rules:
    - If user writes in Chinese → respond in Chinese
    - If user writes in English → respond in English  
    - If user writes in other languages → respond in that language
    - Match the user's communication style

    ## Assessment Criteria:
    1. **Signal Status Check**: 
       - Check if current trading signal has been completed (all positions closed)
       - If signal is completed, new signal generation is required
    
    2. **Performance Analysis**: 
       - Review performance metrics (returns, drawdown, win rate, etc.)
       - Evaluate signal effectiveness and market adaptation
       - Determine if current strategy parameters require adjustment
    
    3. **Market Conditions**:
       - Assess if market conditions have changed significantly
       - Evaluate if current strategy remains suitable

    ## Response Format:
    If signal regeneration is required (due to completion OR poor performance), conclude your response with: "**SIGNAL REGENERATION REQUIRED**"
    If no regeneration is needed, simply explain why the current signal is adequate.
    
    Be clear and decisive in your analysis.
    """

    try:
        system_template = SystemMessagePromptTemplate.from_template(system_prompt)
        system_message = system_template.format_messages()

        human = HumanMessage(
            """Please analyze the backtest results and current trading status to evaluate whether a new trading signal needs to be generated.

Assessment criteria:
1. **Signal Completion Status**: 
   - Check if the current trading signal has been completed (all positions closed)
   - If completed, signal regeneration is automatically required

2. **Performance Evaluation**: 
   - Review performance metrics (returns, drawdown, win rate, etc.)
   - Evaluate signal effectiveness and market adaptation
   - Determine if current strategy parameters require adjustment

3. **Market Adaptation**:
   - Assess if market conditions have changed significantly
   - Evaluate if current strategy remains suitable for current market

**Important**: If the trading signal has been completed (all trades finished), you MUST conclude with "**SIGNAL REGENERATION REQUIRED**" regardless of performance.

For ongoing signals, base your decision on performance analysis and market conditions.

Respond in the same language as the previous user's message, regardless of the language used in this prompt.
"""
        )

        # Get LLM analysis
        response = cast(
            AIMessage,
            await _llm.ainvoke(system_message + state["messages"] + [human]),
        )

        # Check if regeneration is required
        response_content = response.content.upper() if response.content else ""
        needs_regeneration = "**SIGNAL REGENERATION REQUIRED**" in response_content

        if needs_regeneration:
            # Return the analysis message for regeneration workflow
            logger.info("Signal regeneration required based on analysis")
            return {"messages": [HumanMessage(content=response.content)]}
        else:
            # No regeneration needed, return empty messages
            logger.info("Signal regeneration not required based on backtest analysis")
            return {"messages": []}

    except Exception as e:
        logger.error(f"Error in judgement_regenerate_signals: {str(e)}")
        # On error, assume regeneration is needed for safety
        return {
            "messages": [
                HumanMessage(
                    content="Error occurred during analysis. Proceeding with signal regeneration for safety."
                )
            ]
        }


from langgraph.prebuilt import ToolNode

tool_node = ToolNode(tools=tools, name="node_tools_trading_signal_backtest")

from langgraph.utils.runnable import RunnableCallable

node_llm = RunnableCallable(
    call_model_trading_strategy,
    acall_model_trading_strategy,
    name="node_llm_trading_signal_backtest",
)

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
graph_builder.add_edge(tool_node.get_name(), node_llm.get_name())
graph_builder.add_edge(START, node_llm.get_name())
graph = graph_builder.compile()
graph.name = GRAPH_NAME
