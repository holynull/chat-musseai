from typing import Annotated, cast
from typing_extensions import TypedDict
from langgraph.types import Command
from langchain_core.messages import ToolMessage, HumanMessage

from langchain_anthropic import ChatAnthropic

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from loggers import logger
from langchain_core.messages import AIMessage
from graphs.trading_signal_graph.trading_backtest import graph as backtest_graph
from graphs.trading_signal_graph.trading_signal import graph as signal_graph
from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)
from langgraph.types import Command

GRAPH_NAME = "graph_trading_signal_v2"

_llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    temperature=0.1,  # Lower temperature for more consistent trading advice
    streaming=True,
    stream_usage=True,
    verbose=True,
)


class TradingStrategyGraphState(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
    symbol: str
    time_zone: str


async def node_find_history_signal(state: TradingStrategyGraphState):
    his_ai_message_size = -5
    messages = state["messages"]
    ai_messages = [
        cast(AIMessage, m)
        for m in messages
        if m.get("type") == "ai" and len(m.get("tool_calls", []) == 0)
    ]
    if len(ai_messages) == 0:
        state["messages"] = [human_message]
        return Command(goto=signal_graph.get_name(), update=state)
    last_ai_messages = ai_messages[his_ai_message_size:]
    his_ai_content = ""
    for m in last_ai_messages:
        if isinstance(m.content, str):
            his_ai_content += m.content
        elif isinstance(m, list) and len(m.content) > 0:
            his_ai_content += m.content[0].get("text", "")
        else:
            logger.error(f"AIMessage content type error: {m.content}, node_find_history_signal")
            his_ai_content += ""
    if his_ai_content == "":
        logger.error(f"No content in last {0-his_ai_message_size} AI messages. node_find_history_signal")
        return Command(END, update=state)
    system_prompt = """You are a professional cryptocurrency trading signal analyzer. Your task is to determine whether the conversation history contains complete, actionable trading signals.

## Trading Signal Requirements:
A complete trading signal MUST include ALL of the following components:
1. **Trading Direction**: Clear BUY or SELL instruction
2. **Entry Price**: Specific price level or price range for entering the position
3. **Stop Loss**: Risk management price level to limit losses
4. **Target Price(s)**: Profit-taking price level(s) or exit strategy

## Analysis Guidelines:
- Only consider signals that contain ALL four required components
- Ignore incomplete recommendations, general market analysis, or partial signals
- Focus on specific, actionable trading instructions
- Consider signals for any cryptocurrency or trading pair

## Response Format:
- If complete trading signals are found: Respond with "[SIGNAL_DETECTED]"
- If no complete signals are found: Respond with "[NO_SIGNAL]"

Be precise and thorough in your analysis."""

    # Provide your analysis and conclusion.
    human_message = HumanMessage(
        content=f"""Please analyze the entire conversation history to determine if it contains any complete trading signals.

Search for messages that include:
✓ Trading direction (BUY/SELL)
✓ Entry price or price range
✓ Stop loss level
✓ Target price(s) or profit targets

Important: Only consider COMPLETE signals with all four components present. Partial recommendations or general market analysis do not qualify as trading signals.

Respond with either:
- "[SIGNAL_DETECTED]" if complete trading signals are found
- "[NO_SIGNAL]" if no complete signals exist


Conversation History:
{his_ai_content}"""
    )

    system_template = SystemMessagePromptTemplate.from_template(system_prompt)
    system_message = system_template.format_messages()
    response = cast(
        AIMessage,
        await _llm.ainvoke(system_message + [human_message]),
    )
    # More robust detection logic
    response_content = response.content.upper() if response.content else ""
    has_complete_signal = "[SIGNAL_DETECTED]" in response_content

    if has_complete_signal:
        logger.info(
            f"Complete trading signal detected in conversation history - routing to backtest"
        )
        return Command(
            goto=backtest_graph.get_name(),
            update={
                "messages": state["messages"],
                "symbol": state["symbol"],
                "time_zone": state["time_zone"],
                "last_trading_signal_content": response.content,
            },
        )
    else:
        logger.info(f"No complete trading signal found - routing to signal generation")
        human_message = HumanMessage(
            f"""Generate a new {state['symbol']} trading signal.

**Note**:
- Previous user's message: {state['messages'][-1].content}
- Respond in the same language as the previous user's message, regardless of the language used in this prompt."""
        )
        state["messages"] = [human_message]
        return Command(goto=signal_graph.get_name(), update=state)


graph_builder = StateGraph(TradingStrategyGraphState)
graph_builder.add_node(signal_graph)
graph_builder.add_node(backtest_graph)
graph_builder.add_node(node_find_history_signal, node_find_history_signal.__name__)

graph_builder.add_edge(START, node_find_history_signal.__name__)
graph = graph_builder.compile()
graph.name = GRAPH_NAME
