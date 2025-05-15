from typing import Annotated, cast
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic

from langchain_core.runnables import (
    RunnableConfig,
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

_llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
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
    network: str
    network_type: str


graph_builder = StateGraph(State)

from tools.tools_infura import tools

from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.utils.runnable import RunnableCallable


def format_messages(state: State) -> list[BaseMessage]:
    system_prompt = """You are a helpful blockchain assistant with access to Infura's blockchain data.
    Please provide accurate and helpful information about blockchain data.
    """
    system_template = SystemMessagePromptTemplate.from_template(system_prompt)
    system_message = system_template.format_messages()
    return system_message + state["messages"]


def call_model_infura(state: State, config: RunnableConfig) -> State:
    llm_with_tools = _llm.bind_tools(tools)
    response = cast(
        AIMessage, llm_with_tools.invoke(format_messages(state=state), config)
    )

    return {"messages": [response]}


async def acall_model_infura(state: State, config: RunnableConfig) -> State:
    llm_with_tools = _llm.bind_tools(tools)
    response = cast(
        AIMessage, await llm_with_tools.ainvoke(format_messages(state), config)
    )

    return {"messages": [response]}


from langgraph.prebuilt import ToolNode, tools_condition

tool_node = ToolNode(tools=tools, name="node_tools_infura")

from langgraph.utils.runnable import RunnableCallable

node_llm = RunnableCallable(
    call_model_infura, acall_model_infura, name="node_llm_infura"
)
graph_builder.add_node(node_llm.get_name(), node_llm)
graph_builder.add_node(tool_node.get_name(), tool_node)
graph_builder.add_conditional_edges(
    node_llm.get_name(),
    tools_condition,
    {"tools": tool_node.get_name(), END: END},
)
graph_builder.add_edge(tool_node.get_name(), node_llm.get_name())
graph_builder.add_edge(START, node_llm.get_name())
graph = graph_builder.compile()
graph.name = "graph_infura"
