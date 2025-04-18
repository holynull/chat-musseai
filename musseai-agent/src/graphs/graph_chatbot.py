import os
from typing import Annotated, Literal, cast
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatPerplexity

from langchain_core.runnables import ConfigurableField
from langchain_core.runnables import (
    RunnableConfig,
)
from langchain_core.language_models import BaseChatModel

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)
from langchain_core.messages import ToolMessage

from langchain_core.messages import AIMessage
from langgraph.utils.runnable import RunnableCallable
from langgraph.types import Command
from langgraph.prebuilt import ToolNode, tools_condition

from tools.tools_agent_router import tools as tools_router, get_next_node


from graphs.graph_swap import graph as swap_graph
from graphs.graph_wallet import graph as wallet_graph
from graphs.graph_search import graph as search_webpage_graph
from graphs.graph_quote import graph as quote_graph
from graphs.graph_image import graph as image_graph

llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    max_tokens=4096,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    stream_usage=True,
    verbose=True,
).configurable_alternatives(  # This gives this field an id
    # When configuring the end runnable, we can then use this id to configure this field
    ConfigurableField(id="llm"),
    # default_key="openai_gpt_4_turbo_preview",
    default_key="anthropic_claude_3_5_sonnet",
    anthropic_claude_3_opus=ChatAnthropic(
        model="claude-3-opus-20240229",
        # max_tokens=,
        temperature=0.9,
        # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
        streaming=True,
        verbose=True,
    ),
    anthropic_claude_3_7_sonnet=ChatAnthropic(
        model="claude-3-7-sonnet-20250219",
        # max_tokens=,
        temperature=0.9,
        # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
        streaming=True,
        verbose=True,
    ),
    openai_gpt_4o=ChatOpenAI(
        temperature=0.9,
        model="gpt-4o",
        verbose=True,
        streaming=True,
    ),
    openai_gpt_3_5_turbo_1106=ChatOpenAI(
        model="gpt-3.5-turbo-1106",
        verbose=True,
        streaming=True,
        temperature=0.9,
    ),
    openai_gpt_4_turbo_preview=ChatOpenAI(
        temperature=0.9,
        model="gpt-4-turbo-preview",
        verbose=True,
        streaming=True,
    ),
    openai_gpt_4o_mini=ChatOpenAI(
        temperature=0.9,
        model="gpt-4o-mini",
        verbose=True,
        streaming=True,
    ),
    pplx_sonar_medium_chat=ChatPerplexity(
        model="sonar-medium-chat", temperature=0.9, verbose=True, streaming=True
    ),
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


graph_builder = StateGraph(State)


# def format_messages(state: State):
#     from prompts.prompt_chatbot import system_prompt

#     system_template = SystemMessagePromptTemplate.from_template(system_prompt)
#     system_message = system_template.format_messages(
#         wallet_is_connected=state["wallet_is_connected"],
#         chain_id=state["chain_id"],
#         wallet_address=state["wallet_address"],
#         time_zone=state["time_zone"],
#     )
#     return system_message + state["messages"]


# system_message = RunnableCallable(format_messages)
from prompts.prompt_chatbot import system_prompt

system_template = SystemMessagePromptTemplate.from_template(system_prompt)


def call_model(state: State, config: RunnableConfig):
    llm_configed = (
        cast(BaseChatModel, llm)
        .bind_tools(tools_router)
        .with_config(
            {
                "configurable": {"llm": state["llm"]},
            }
        )
    )
    system_message = system_template.format_messages(
        wallet_is_connected=state["wallet_is_connected"],
        chain_id=state["chain_id"],
        wallet_address=state["wallet_address"],
        time_zone=state["time_zone"],
    )
    response = cast(
        AIMessage,
        llm_configed.invoke(system_message + state["messages"], config),
    )
    state["messages"].append(response)
    return state


async def acall_model(state: State, config: RunnableConfig):
    llm_configed = (
        cast(BaseChatModel, llm)
        .bind_tools(tools_router)
        .with_config(
            {
                "configurable": {"llm": state["llm"]},
            }
        )
    )

    system_message = system_template.format_messages(
        wallet_is_connected=state["wallet_is_connected"],
        chain_id=state["chain_id"],
        wallet_address=state["wallet_address"],
        time_zone=state["time_zone"],
    )
    _response = await llm_configed.ainvoke(system_message + state["messages"], config)

    response = cast(AIMessage, _response)
    state["messages"].append(response)
    return state


router_tools = ToolNode(tools=tools_router, name="node_tools_router")


def node_router(state: State):
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage):
        next_node = get_next_node(last_message.name)
        if next_node:
            return Command(
                goto=next_node,
                update={
                    "messages": state["messages"],
                    "wallet_is_connected": state["wallet_is_connected"],
                    "chain_id": state["chain_id"],
                    "wallet_address": state["wallet_address"],
                    "llm": state["llm"],
                },
            )
        else:
            return Command(
                goto=node_llm.get_name(),
                update={
                    "messages": state["messages"],
                    "wallet_is_connected": state["wallet_is_connected"],
                    "chain_id": state["chain_id"],
                    "wallet_address": state["wallet_address"],
                    "llm": state["llm"],
                },
            )
    else:
        return Command(
            goto=node_llm.get_name(),
            update={
                "messages": state["messages"],
                "wallet_is_connected": state["wallet_is_connected"],
                "chain_id": state["chain_id"],
                "wallet_address": state["wallet_address"],
                "llm": state["llm"],
            },
        )


node_llm = RunnableCallable(call_model, acall_model, name="node_llm_musseai")
graph_builder.add_node(node_llm.get_name(), node_llm)
graph_builder.add_node(node_router)

graph_builder.add_node(swap_graph.get_name(), swap_graph)
graph_builder.add_node(wallet_graph.get_name(), wallet_graph)
graph_builder.add_node(search_webpage_graph.get_name(), search_webpage_graph)
graph_builder.add_node(quote_graph.get_name(), quote_graph)
graph_builder.add_node(image_graph)

graph_builder.add_node(router_tools.get_name(), router_tools)
graph_builder.add_edge(START, node_llm.get_name())
graph_builder.add_conditional_edges(
    node_llm.get_name(),
    tools_condition,
    {"tools": router_tools.get_name(), END: END},
)
graph_builder.add_edge(router_tools.get_name(), node_router.__name__)
graph_builder.add_edge(swap_graph.get_name(), node_llm.get_name())
graph_builder.add_edge(wallet_graph.get_name(), node_llm.get_name())
graph_builder.add_edge(search_webpage_graph.get_name(), node_llm.get_name())
graph_builder.add_edge(quote_graph.get_name(), node_llm.get_name())
graph_builder.add_edge(image_graph.get_name(), node_llm.get_name())
from langgraph.store.memory import InMemoryStore
from langchain_ollama import OllamaEmbeddings
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()


in_memory_store = InMemoryStore(
    index={
        "embed": OllamaEmbeddings(model="llama3"),
        "dims": 1536,
    }
)

# graph = graph_builder.compile(checkpointer=memory, debug=False, store=in_memory_store)
graph = graph_builder.compile()
graph.name = "mussai_agent"
