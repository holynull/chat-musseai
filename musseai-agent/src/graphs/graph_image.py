from typing import Annotated, cast
from agent_config import ROUTE_MAPPING, tools_condition
from typing_extensions import TypedDict
from langgraph.types import Command

from langchain_anthropic import ChatAnthropic

from langchain_core.runnables import (
    RunnableConfig,
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import ToolMessage

_llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    stream_usage=True,
    verbose=True,
)


class GraphState(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(GraphState)

from tools.tools_image import tools
from tools.tools_agent_router import generate_routing_tools

from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)

from langchain_core.messages import AIMessage
from langgraph.utils.runnable import RunnableCallable

from prompts.prompt_image import system_prompt

system_template = SystemMessagePromptTemplate.from_template(system_prompt)


def call_model_swap(state: GraphState, config: RunnableConfig) -> GraphState:
    llm_with_tools = _llm.bind_tools(tools + generate_routing_tools())
    system_message = system_template.format_messages()
    response = cast(
        AIMessage, llm_with_tools.invoke(system_message + state["messages"], config)
    )

    return {"messages": [response]}


async def acall_model_swap(state: GraphState, config: RunnableConfig) -> GraphState:
    llm_with_tools = _llm.bind_tools(tools + generate_routing_tools())
    system_message = system_template.format_messages()
    response = cast(
        AIMessage,
        await llm_with_tools.ainvoke(system_message + state["messages"], config),
    )
    return {"messages": [response]}


from langgraph.prebuilt import ToolNode

tool_node = ToolNode(tools=tools + generate_routing_tools(), name="node_tools_image")

from langgraph.utils.runnable import RunnableCallable

node_llm = RunnableCallable(call_model_swap, acall_model_swap, name="node_llm_image")
graph_builder.add_node(node_llm.name, node_llm)
graph_builder.add_node(tool_node.get_name(), tool_node)
graph_builder.add_conditional_edges(
    node_llm.get_name(),
    tools_condition,
    {"tools": tool_node.get_name(), END: END},
)


def node_router(state: GraphState):
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage) and last_message.name in ROUTE_MAPPING:
        return Command(goto=END, update=state)
    else:
        return Command(goto=node_llm.get_name(), update=state)


graph_builder.add_node(node_router)
graph_builder.add_edge(tool_node.get_name(), node_router.__name__)
graph_builder.add_edge(START, node_llm.get_name())
graph = graph_builder.compile()
graph.name = "graph_image"
