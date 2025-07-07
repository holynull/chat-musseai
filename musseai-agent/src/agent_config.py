# agent_config.py

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Union
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    BaseMessage,
    SystemMessage,
    AnyMessage,
)
from langgraph.types import Command
from langgraph.graph import END
from pydantic import BaseModel


@dataclass
class AgentConfig:
    name: str  # 专家名称
    description: str  # 专家描述
    capabilities: List[str]  # 专家具备的能力
    graph_module: str  # 对应的图模块路径
    graph_name: str  # 对应子图名称
    graph_variable: str = "graph"  # 图变量名称（默认为"graph"）
    required_env_vars: List[str] = None  # 所需的环境变量
    dependencies: List[str] = None  # 依赖的其他专家或服务


AGENT_CONFIGS: Dict[str, AgentConfig] = {
    "swap": AgentConfig(
        name="Cryptocurrency Swap Expert",
        description="Specialist in handling cryptocurrency swap operations across different chains and protocols",
        capabilities=[
            "Get the list of supported tokens for token cross chain swap functionality",
            "Get a detailed quote for token cross chain swap transaction, including expected output amount, fees, and transaction parameters",
            "Generate swap transaction data, and notify the front end to generate a button to send a token swap transaction",
            "Get transaction records using the Bridgers API",
            "Get detailed information about a specific transaction using the Bridgers API",
        ],
        graph_module="graphs.graph_swap",
        graph_name="graph_swap",
        required_env_vars=["BRIDGERS_API_KEY"],
        dependencies=["wallet"],
    ),
    "wallet": AgentConfig(
        name="Cryptocurrency Wallet Expert",
        description="Expert in cryptocurrency wallet operations and token management across multiple blockchains",
        capabilities=[
            "Notify front end to connect to wallet",
            "Notify the front end to change the connected network to the target network in wallet",
        ],
        graph_module="graphs.graph_wallet",
        graph_name="graph_wallet",
        required_env_vars=["WEB3_PROVIDER_URI", "SOLANA_RPC_URL", "TRON_GRID_API_KEY"],
    ),
    "search": AgentConfig(
        name="Search Engine Expert",
        description="Specialist in web search operations and content retrieval across multiple sources",
        capabilities=[
            "Performs a web search using Google search engine and returns formatted results",
            "Performs a news search using Google News and returns formatted results in JSON format",
            "Performs a place search using Google Places API and returns raw search results",
            "Performs an image search using Google Images and returns raw search results",
            "Access and analyze the content of web links",
            "Extract relevant information from search results",
        ],
        graph_module="graphs.graph_search",
        graph_name="graph_search",
        required_env_vars=["GOOGLE_API_KEY", "GOOGLE_CSE_ID"],
    ),
    "quote": AgentConfig(
        name="Cryptocurrency Market Analysis Expert",
        description="Expert in cryptocurrency market analysis and price quotations",
        capabilities=[
            "Retrieves the latest cryptocurrency quotation data from CoinMarketCap API",
            "Retrieves detailed metadata and information about a cryptocurrency from CoinMarketCap API",
            "Analyzes trading signals for cryptocurrency pairs against USDT using TradingView technical analysis",
            "Retrieves the latest content including news, trending coins, and educational materials",
            "Retrieves trending tokens based on community activity",
            "Provides market analysis and trading insights",
        ],
        graph_module="graphs.graph_quote",
        graph_name="graph_quote",
        required_env_vars=["COINMARKETCAP_API_KEY", "TRADINGVIEW_API_KEY"],
    ),
    "image": AgentConfig(
        name="Text-to-Image Generation Expert",
        description="Specialist in generating images from textual descriptions",
        capabilities=[
            "Generate images based on textual descriptions",
            "Return markdown format image links of generated images",
            "Support multiple image generation styles and parameters",
            "Process and optimize generated images",
            "Handle multiple image generation requests in sequence",
        ],
        graph_module="graphs.graph_image",
        graph_name="graph_image",
        required_env_vars=["STABLE_DIFFUSION_API_KEY"],
    ),
    "infura": AgentConfig(
        name="Blockchain Data Expert",
        description="Expert in accessing and analyzing blockchain data across multiple networks",
        capabilities=[
            "Getting blockchain network information for multiple networks (Ethereum, Polygon, Optimism, etc.)",
            "Checking wallet native token balances across various networks and testnets",
            "Looking up transaction details and receipts on the blockchain",
            "Viewing block information and contents including transactions and uncles",
            "Checking ERC20 token balances and contract information",
            "Estimating gas fees for transactions and creating access lists",
            "Getting contract events, logs, and storage data",
            "Calling various blockchain JSON-RPC methods directly",
            "Retrieving supported network information and chain IDs",
            "Fetching blockchain fee history and gas price information",
            "Accessing contract code and state at specific blocks",
            "Retrieving proof of account and storage data",
            "Getting transaction counts and network status information",
        ],
        graph_module="graphs.graph_infura",
        graph_name="graph_infura",
        required_env_vars=["INFURA_API_KEY", "ETHERSCAN_API_KEY"],
    ),
    "solana": AgentConfig(
        name="Solana Blockchain Expert",
        description="Specialist in Solana blockchain operations and data analysis",
        capabilities=[
            "Accessing Solana blockchain data through RPC endpoints",
            "Querying Solana account information and balances",
            "Getting information about Solana blocks and transactions",
            "Working with Solana Program accounts and tokens",
            "Analyzing Solana blockchain state and statistics",
            "Monitoring Solana network performance and status",
            "Handling Solana token operations and transfers",
            "Interacting with Solana smart contracts and programs",
        ],
        graph_module="graphs.graph_solana",
        graph_name="graph_solana",
        required_env_vars=["SOLANA_RPC_URL"],
    ),
    "crypto_portfolios": AgentConfig(
        name="Cryptocurrency Portfolio (Positions) Management Expert",
        description="Expert in managing cryptocurrency portfolios (positions) across multiple asset sources including wallets, exchanges, and DeFi protocols",
        capabilities=[
            "Retrieve and manage user's asset sources (wallets, exchanges, DeFi protocols)",
            "Add new wallet addresses as asset sources with chain type support (ETH, BSC, SOL, etc.)",
            "Add centralized exchange accounts as asset sources with validation",
            "Add DeFi protocol positions as asset sources with detailed protocol information",
            "Query and display asset positions for specific sources with real-time data",
            "Update asset positions with cost basis tracking and operation type classification",
            "Track position history with detailed change logs and sync type recording",
            "Generate comprehensive portfolio summaries with asset aggregation across all sources",
            "Support multi-chain asset balance queries through integrated blockchain tools",
            "Provide transaction recording and categorization (DEPOSIT, WITHDRAW, TRADE)",
            "Maintain detailed audit trails for all portfolio changes and operations",
            "Cross-reference with real-time blockchain data for accurate position validation",
        ],
        graph_module="graphs.graph_crypto_portfolios",
        graph_name="graph_crypto_portfolios",
        required_env_vars=["DATABASE_URL"],  # 添加数据库连接需求
        dependencies=["infura", "solana"],  # 添加依赖的区块链数据专家
    ),
}

# 辅助函数


def get_agent_config(agent_id: str) -> Optional[AgentConfig]:
    """根据agent ID获取配置"""
    return AGENT_CONFIGS.get(agent_id)


def get_required_env_vars() -> List[str]:
    """获取所有专家所需的环境变量"""
    env_vars = set()
    for config in AGENT_CONFIGS.values():
        if config.required_env_vars:
            env_vars.update(config.required_env_vars)
    return sorted(list(env_vars))


def get_agent_dependencies(agent_id: str) -> List[str]:
    """获取指定专家的所有依赖"""
    config = get_agent_config(agent_id)
    if not config or not config.dependencies:
        return []

    all_deps = set()

    def collect_deps(aid):
        if aid not in all_deps:
            all_deps.add(aid)
            agent_config = get_agent_config(aid)
            if agent_config and agent_config.dependencies:
                for dep in agent_config.dependencies:
                    collect_deps(dep)

    for dep in config.dependencies:
        collect_deps(dep)

    return sorted(list(all_deps))


def validate_agent_config(agent_id: str) -> bool:
    """验证专家配置是否完整有效"""
    config = get_agent_config(agent_id)
    if not config:
        return False

    # 检查必要字段
    if not all(
        [config.name, config.description, config.capabilities, config.graph_module]
    ):
        return False

    # 检查依赖
    if config.dependencies:
        for dep in config.dependencies:
            if dep not in AGENT_CONFIGS:
                return False

    return True


def get_agent_capabilities(agent_id: str) -> List[str]:
    """获取指定专家的所有能力"""
    config = get_agent_config(agent_id)
    return config.capabilities if config else []


# 路由映射表
ROUTE_MAPPING = {
    f"route_to_{config.graph_name}": config.graph_name
    for agent_id, config in AGENT_CONFIGS.items()
}


def get_tool_name_by_agent(agent_id: str) -> Optional[str]:
    """根据agent ID获取对应的工具名称"""
    for tool_name, aid in ROUTE_MAPPING.items():
        if aid == agent_id:
            return tool_name
    return None


def get_agent_by_tool(tool_name: str) -> Optional[AgentConfig]:
    """根据工具名称获取对应的agent配置"""
    agent_id = ROUTE_MAPPING.get(tool_name)
    if agent_id:
        return get_agent_config(agent_id)
    return None


def load_graph(agent_id: str):
    """动态导入并返回指定专家的图

    Args:
        agent_id: 专家ID

    Returns:
        图对象或None（如果导入失败）
    """
    if not agent_id:
        return None

    try:
        config = get_agent_config(agent_id)
        if not config:
            return None

        # 动态导入模块
        import importlib

        module = importlib.import_module(config.graph_module)

        # 获取图变量
        graph = getattr(module, config.graph_variable, None)
        return graph
    except Exception as e:
        print(f"Error loading graph for agent {agent_id}: {e}")
        return None


def has_end_command(message: BaseMessage):
    if isinstance(message, AIMessage):
        tool_calls = message.tool_calls
        if len(tool_calls) > 0:
            tool_name = tool_calls[0].get("name", "")
            if tool_name in ROUTE_MAPPING:
                return True
    return False


def tools_condition(
    state: Union[list[AnyMessage], dict[str, Any], BaseModel],
    messages_key: str = "messages",
) -> Literal["tools", "__end__"]:
    """Use in the conditional_edge to route to the ToolNode if the last message

    has tool calls. Otherwise, route to the end.

    Args:
        state: The state to check for
            tool calls. Must have a list of messages (MessageGraph) or have the
            "messages" key (StateGraph).

    Returns:
        The next node to route to.


    Examples:
        Create a custom ReAct-style agent with tools.

        ```pycon
        >>> from langchain_anthropic import ChatAnthropic
        >>> from langchain_core.tools import tool
        ...
        >>> from langgraph.graph import StateGraph
        >>> from langgraph.prebuilt import ToolNode, tools_condition
        >>> from langgraph.graph.message import add_messages
        ...
        >>> from typing import Annotated
        >>> from typing_extensions import TypedDict
        ...
        >>> @tool
        >>> def divide(a: float, b: float) -> int:
        ...     \"\"\"Return a / b.\"\"\"
        ...     return a / b
        ...
        >>> llm = ChatAnthropic(model="claude-3-haiku-20240307")
        >>> tools = [divide]
        ...
        >>> class State(TypedDict):
        ...     messages: Annotated[list, add_messages]
        >>>
        >>> graph_builder = StateGraph(State)
        >>> graph_builder.add_node("tools", ToolNode(tools))
        >>> graph_builder.add_node("chatbot", lambda state: {"messages":llm.bind_tools(tools).invoke(state['messages'])})
        >>> graph_builder.add_edge("tools", "chatbot")
        >>> graph_builder.add_conditional_edges(
        ...     "chatbot", tools_condition
        ... )
        >>> graph_builder.set_entry_point("chatbot")
        >>> graph = graph_builder.compile()
        >>> graph.invoke({"messages": {"role": "user", "content": "What's 329993 divided by 13662?"}})
        ```
    """
    if isinstance(state, list):
        ai_message = state[-1]
    elif isinstance(state, dict) and (messages := state.get(messages_key, [])):
        ai_message = messages[-1]
    elif messages := getattr(state, messages_key, []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state to tool_edge: {state}")
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tools"
    return "__end__"
