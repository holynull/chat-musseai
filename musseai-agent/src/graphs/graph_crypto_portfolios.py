from typing import Annotated, cast
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from tools.tools_crypto_portfolios import tools

# Initialize LLM
_llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    max_tokens=4096,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    stream_usage=True,
    verbose=True,
)


# Define state type
class State(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    wallet_is_connected: bool
    chain_id: int
    wallet_address: str


# Create graph builder
graph_builder = StateGraph(State)

from langchain_core.prompts import SystemMessagePromptTemplate
from langchain_core.messages import AIMessage, BaseMessage


def format_messages(state: State) -> list[BaseMessage]:
    """Format system prompt and messages"""
    # Get wallet connection status
    wallet_status = (
        "Connected" if state.get("wallet_is_connected", False) else "Not Connected"
    )

    system_prompt = f"""You are a cryptocurrency asset position management expert who helps users analyze and optimize their digital asset portfolios across multiple sources including wallets and exchanges.


    Current user information:
    - User ID: {state.get("user_id", "Unknown")}
    - Wallet Status: {wallet_status}
    {f"- Chain ID: {state.get('chain_id')}" if state.get('chain_id') else ""}
    {f"- Wallet Address: {state.get('wallet_address')}" if state.get('wallet_address') else ""}
    
    You can:
    1. Manage multiple asset sources (wallets, exchanges, DeFi protocols)
    2. Add and monitor wallet addresses across different chains
    3. Connect exchange accounts via API
    4. Track portfolio positions and balances
    5. Monitor position changes and transaction history
    6. Generate portfolio analysis and recommendations
    7. Compare performance across different sources
    
    Your focus is on comprehensive portfolio management across all sources. Consider:
    - Asset allocation and diversification
    - Risk management across different platforms
    - Cost basis and performance tracking
    - Transaction history and patterns
    - Market conditions and trends
    
    Important: 
    - If no source is selected, guide the user to add or select an asset source
    - Maintain security best practices when handling API credentials
    - Consider the specific features and limitations of each source type
    """
    system_template = SystemMessagePromptTemplate.from_template(system_prompt)
    system_message = system_template.format_messages()
    return system_message + state["messages"]


def call_model(state: State, config: RunnableConfig) -> State:
    """Call LLM to process user requests"""
    llm_with_tools = _llm.bind_tools(tools)
    response = cast(
        AIMessage, llm_with_tools.invoke(format_messages(state=state), config)
    )

    return {"messages": [response]}


async def acall_model(state: State, config: RunnableConfig) -> State:
    """Asynchronously call LLM to process user requests"""
    llm_with_tools = _llm.bind_tools(tools)
    response = cast(
        AIMessage, await llm_with_tools.ainvoke(format_messages(state), config)
    )

    return {"messages": [response]}


# Add tool node
from langgraph.prebuilt import ToolNode, tools_condition

tool_node = ToolNode(tools=tools, name="node_tools_crypto_portfolios")

# Set up LLM node
from langgraph.utils.runnable import RunnableCallable

node_llm = RunnableCallable(call_model, acall_model, name="node_llm_crypto_portfolios")

# Build the graph
graph_builder.add_node(node_llm.get_name(), node_llm)
graph_builder.add_node(tool_node.get_name(), tool_node)

# Add edges and conditions
graph_builder.add_conditional_edges(
    node_llm.get_name(), tools_condition, {"tools": tool_node.get_name(), END: END}
)
graph_builder.add_edge(tool_node.get_name(), node_llm.get_name())
graph_builder.add_edge(START, node_llm.get_name())

# Compile the graph
graph = graph_builder.compile()
graph.name = "graph_crypto_portflios"
