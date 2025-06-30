from typing import Annotated, cast
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import ToolMessage

from tools.tools_crypto_portfolios import tools
from agent_config import tools_condition, ROUTE_MAPPING
from tools.tools_agent_router import generate_routing_tools
from langgraph.types import Command
from loggers import logger

GRAPH_NAME = "graph_crypto_portfolios"

# Initialize LLM
_llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
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
    # 检查用户是否有任何资产来源

    # Get wallet connection status
    wallet_status = (
        "Connected" if state.get("wallet_is_connected", False) else "Not Connected"
    )

    system_prompt = f"""You are a cryptocurrency asset portfolio management expert who helps users analyze and optimize their digital asset portfolios across multiple sources.
    
    IMPORTANT SYSTEM ARCHITECTURE:
    The system manages asset portfolios through a multi-source architecture where:
    
    1. ASSET SOURCES: Each portfolio position belongs to a specific asset source, not directly to the connected wallet
       - WALLET: Blockchain wallet addresses (different chains: ETH, BSC, SOL, etc.)
       - EXCHANGE: Cryptocurrency exchange accounts (Binance, Coinbase, etc.)  
       - DEFI: DeFi protocol positions (Uniswap, Aave, Curve, etc.)
    
    2. ASSET POSITIONS: Each position is linked to an asset source via source_id
       - Users can have multiple sources of the same type
       - Each source can hold multiple asset positions
       - Positions are tracked with quantity, cost basis, and additional metadata
    
    3. CONNECTED WALLET vs MANAGED PORTFOLIO:
       - Connected wallet (Chain ID: {state.get('chain_id')}, Address: {state.get('wallet_address')}) is for frontend interaction
       - Portfolio management covers ALL asset sources, not just the connected wallet
       - Users must explicitly add asset sources to track their positions
    
    Current user information:
    - User ID: {state.get("user_id", "Unknown")}
    - Wallet Status: {wallet_status}
    {f"- Connected Chain ID: {state.get('chain_id')}" if state.get('chain_id') else ""}
    {f"- Connected Wallet Address: {state.get('wallet_address')}" if state.get('wallet_address') else ""}
    
    WORKFLOW GUIDANCE:
    When users want to add or manage positions:
    
    1. FIRST: Check existing asset sources using get_user_asset_sources()
    2. IF NO SOURCES: Guide user to add asset sources:
       - add_wallet_source() for blockchain wallets
       - add_exchange_source() for exchange accounts  
       - add_defi_source() for DeFi protocol positions
    
    3. THEN: Manage positions within those sources:
       - get_source_positions() to view positions for a source
       - update_position() to add/modify positions
       - get_position_history() to track changes
    
    KEY CAPABILITIES:
    ✓ Multi-source portfolio management (wallets, exchanges, DeFi)
    ✓ Cross-chain asset tracking and aggregation
    ✓ Position history and transaction recording
    ✓ Portfolio analysis and performance tracking
    ✓ Real-time balance queries for supported chains
    ✓ Cost basis and P&L calculations
    
    IMPORTANT DISTINCTIONS:
    - Asset sources are user-defined portfolio components
    - Connected wallet is just for authentication/interaction
    - Each asset source maintains its own set of positions
    - Portfolio analysis aggregates across all sources
    - Users can track assets they don't directly control (e.g., exchange balances)
    
    Always clarify the difference between connected wallet and managed portfolio sources when users seem confused about adding assets or positions.
    """

    system_template = SystemMessagePromptTemplate.from_template(system_prompt)
    system_message = system_template.format_messages()
    return system_message + state["messages"]


def call_model(state: State, config: RunnableConfig) -> State:
    """Call LLM to process user requests"""
    llm_with_tools = _llm.bind_tools(tools + generate_routing_tools())
    response = cast(
        AIMessage, llm_with_tools.invoke(format_messages(state=state), config)
    )

    return {"messages": [response]}


async def acall_model(state: State, config: RunnableConfig) -> State:
    """Asynchronously call LLM to process user requests"""
    llm_with_tools = _llm.bind_tools(tools + generate_routing_tools())
    response = cast(
        AIMessage, await llm_with_tools.ainvoke(format_messages(state), config)
    )
    return {"messages": [response]}


# Add tool node
from langgraph.prebuilt import ToolNode

tool_node = ToolNode(
    tools=tools + generate_routing_tools(), name="node_tools_crypto_portfolios"
)

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


def node_router(state: State):
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage) and last_message.name in ROUTE_MAPPING:
        logger.info(f"Node:{GRAPH_NAME}, Need to route to other node, cause graph end.")
        return Command(goto=END, update=state)
    else:
        return Command(goto=node_llm.get_name(), update=state)


graph_builder.add_node(node_router)
graph_builder.add_edge(tool_node.get_name(), node_router.__name__)
graph_builder.add_edge(START, node_llm.get_name())

# Compile the graph
graph = graph_builder.compile()
graph.name = GRAPH_NAME
