from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages
from langgraph.types import interrupt
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    BaseMessage,
    SystemMessage,
    ToolMessage,
)

from typing import Annotated, cast
from langgraph.prebuilt import tools_condition
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

GRAPH_NAME = "graph_swap_v2"

_llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    stream_usage=True,
    verbose=True,
)


class SwapGraphState(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(SwapGraphState)

from tools.tools_swap_v2 import tools

from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)

from langchain_core.messages import AIMessage
from langgraph.utils.runnable import RunnableCallable
from prompts.prompt_swap_v2 import system_prompt

system_template = SystemMessagePromptTemplate.from_template(system_prompt)


def call_model_swap(state: SwapGraphState, config: RunnableConfig) -> SwapGraphState:
    llm_with_tools = _llm.bind_tools(tools)

    system_message = system_template.format_messages()
    response = cast(
        AIMessage, llm_with_tools.invoke(system_message + state["messages"], config)
    )

    return {"messages": [response]}


async def acall_model_swap(
    state: SwapGraphState, config: RunnableConfig
) -> SwapGraphState:
    llm_with_tools = _llm.bind_tools(tools)

    system_message = system_template.format_messages()
    response = cast(
        AIMessage,
        await llm_with_tools.ainvoke(system_message + state["messages"], config),
    )
    return {"messages": [response]}


from langgraph.prebuilt import ToolNode

tool_node = ToolNode(tools=tools, name="node_tools_swap_v2")

from langgraph.utils.runnable import RunnableCallable

node_llm = RunnableCallable(call_model_swap, acall_model_swap, name="node_llm_swap_v2")
graph_builder.add_node(node_llm.name, node_llm)
graph_builder.add_node(tool_node.get_name(), tool_node)


class CheckTokenTransferState(TypedDict):
    transfer_tx: list[any]
    swap_data: any


def node_swap_1_generate_wallet(state: SwapGraphState):
    last_tool_message = cast(ToolMessage, state["messages"][-1])
    if last_tool_message.name != "swap":
        return Command(goto=node_llm.get_name(), update=state)
    else:
        answer = interrupt(
            value={
                "event": "waiting_for_token_transfer",
                "data": {
                    "address": "0xzxcvbnm123456789",
                    "symbol_amount": [
                        {"symbol": "BNB", "amount": "0.00000021", "description": "Gas Fee"},
                        {"symbol": "USDT", "amount": "10.000000"},
                    ],
                },
                "text": "请在3分钟内将兑换所需的数字资产转账到我的这个地上，我会为您完成兑换。",
            }
        )
        if answer and answer["txs"] and len(answer["txs"]) > 0:
            # todo: 从toolmessage中找到swapdata传递下去
            return Command(
                goto=node_swap_2_check_token_transfer_configurations.__name__,
                # update={"transfer_tx": answer["txs"],"swap_data":{}},
                update={"transfer_tx": answer["txs"]},
            )
        else:
            last_tool_message.content = "Not found any token transfer transcations."
            state["messages"][-1] = last_tool_message
            return Command(goto=node_llm.get_name(), update=state)


def node_swap_2_check_token_transfer_configurations(state: CheckTokenTransferState):
    waiting = False
    for tx in state["transfer_tx"]:
        if tx["configrations"] < 5:
            waiting = True
            break
    if waiting:
        answer = interrupt(
            value={
                "event": "waiting_for_token_transfer_configuration",
                "data": state,
                "text": "链上交易确认数没有达到标准，请稍后...",
            }
        )
        if answer == "Done":
            return Command(goto=node_swap_3_swap.__name__, update=state)
        else:
            raise SystemError("Check Token Transfer Configuration Error")


def node_swap_3_swap(state: CheckTokenTransferState):
    # todo: swap
    return Command(node_llm.get_name)


graph_builder.add_node(
    node_swap_1_generate_wallet.__name__, node_swap_1_generate_wallet
)
graph_builder.add_node(
    node_swap_2_check_token_transfer_configurations.__name__,
    node_swap_2_check_token_transfer_configurations,
)
graph_builder.add_node(node_swap_3_swap.__name__, node_swap_3_swap)
graph_builder.add_conditional_edges(
    node_llm.get_name(),
    tools_condition,
    {"tools": tool_node.get_name(), END: END},
)

graph_builder.add_edge(tool_node.get_name(), node_swap_1_generate_wallet.__name__)

graph_builder.add_edge(START, node_llm.get_name())
graph = graph_builder.compile()
graph.name = GRAPH_NAME
