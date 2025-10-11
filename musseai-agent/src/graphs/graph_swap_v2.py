from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages
from langgraph.types import interrupt, Command
from langgraph.graph import StateGraph, START, END

GRAPH_NAME = "graph_swap_v2"


class SwapGraphState(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]


def node_check_transfer(state: SwapGraphState):
    value = interrupt("I'm waiting for your transfering configrations.")
    state["interrupt_value"] = value
    return state


graph_builder = StateGraph(SwapGraphState)
graph_builder.add_node(node_check_transfer)
graph_builder.add_edge(START, node_check_transfer.__name__)
graph_builder.add_edge(node_check_transfer.__name__, END)

graph = graph_builder.compile()
graph.name = GRAPH_NAME