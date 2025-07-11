import os
from typing import Annotated, Optional, cast
from typing_extensions import TypedDict
from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import (
    RunnableConfig,
)
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.utils.runnable import RunnableCallable
from langgraph.types import Command
from tools.tools_agent_router import tools as tools_router

llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    stream_usage=True,
    verbose=True,
)

# llm = ChatAnthropic(
#     model="claude-3-5-sonnet-20241022",
#     max_tokens=4096,
#     temperature=0.9,
#     # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
#     streaming=True,
#     stream_usage=True,
#     verbose=True,
# ).configurable_alternatives(  # This gives this field an id
#     # When configuring the end runnable, we can then use this id to configure this field
#     ConfigurableField(id="llm"),
#     # default_key="openai_gpt_4_turbo_preview",
#     default_key="anthropic_claude_3_5_sonnet",
#     anthropic_claude_3_opus=ChatAnthropic(
#         model="claude-3-opus-20240229",
#         # max_tokens=,
#         temperature=0.9,
#         # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
#         streaming=True,
#         verbose=True,
#     ),
#     anthropic_claude_3_7_sonnet=ChatAnthropic(
#         model="claude-3-7-sonnet-20250219",
#         # max_tokens=,
#         temperature=0.9,
#         # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
#         streaming=True,
#         verbose=True,
#     ),
#     anthropic_claude_4_sonnet=ChatAnthropic(
#         model="claude-sonnet-4-20250514",
#         # max_tokens=,
#         temperature=0.9,
#         # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
#         streaming=True,
#         verbose=True,
#     ),
# )


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
    user_id: str


graph_builder = StateGraph(State)


from prompts.prompt_chatbot import system_prompt

system_template = SystemMessagePromptTemplate.from_template(system_prompt)

from tools.tools_swap import tools as tools_swap
from tools.tools_wallet import tools as tools_wallet
from tools.tools_search import tools as tools_search
from tools.tools_quote import tools as tools_quote
from tools.tools_image import tools as tools_image
from tools.tools_infura import tools as tools_infura
from tools.tools_solana import tools as tools_solana
from tools.tools_crypto_portfolios import tools as tools_crypto_portfolios

ROUTE_MAPPING = {
    "route_to_swap_agent": {
        "node_name": "node_swap_graph",
        "tools": [t.get_name() for t in tools_swap],
    },
    "route_to_wallet_agent": {
        "node_name": "node_wallet_graph",
        "tools": [t.get_name() for t in tools_wallet],
    },
    "route_to_search_agent": {
        "node_name": "node_search_graph",
        "tools": [t.get_name() for t in tools_search],
    },
    "route_to_quote_agent": {
        "node_name": "node_quote_graph",
        "tools": [t.get_name() for t in tools_quote],
    },
    "route_to_image_agent": {
        "node_name": "node_image_graph",
        "tools": [t.get_name() for t in tools_image],
    },
    "route_to_infura_agent": {
        "node_name": "node_infura_graph",
        "tools": [t.get_name() for t in tools_infura],
    },
    "route_to_solana_agent": {
        "node_name": "node_solana_graph",
        "tools": [t.get_name() for t in tools_solana],
    },
    "route_to_crypto_portfolios_agent": {
        "node_name": "node_crypto_portfolios_graph",
        "tools": [t.get_name() for t in tools_crypto_portfolios],
    },
}


def build_tool_to_node_mapping():
    """构建工具名到节点名的映射"""
    mapping = {}
    for route_key, route_info in ROUTE_MAPPING.items():
        if isinstance(route_info, dict) and "tools" in route_info:
            for tool in route_info["tools"]:
                mapping[tool] = route_info["node_name"]
    return mapping


TOOL_TO_NODE_MAPPING = build_tool_to_node_mapping()


def call_model(state: State, config: RunnableConfig):
    raise NotImplementedError()


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
    _response = await llm_configed.ainvoke(system_message + state["messages"])
    response = cast(AIMessage, _response)
    next_node = await aget_next_node(state["messages"] + [response])
    if next_node:
        return Command(
            goto=next_node,
            update=state,
        )
    else:
        return Command(
            goto=END,
            update=_response,
        )


node_llm = RunnableCallable(call_model, acall_model, name="node_llm_musseai")


from graphs.graph_wallet import graph as wallet_graph
from graphs.graph_search import graph as search_graph
from graphs.graph_swap import graph as swap_graph
from graphs.graph_quote import graph as quote_graph
from graphs.graph_image import graph as image_graph
from graphs.graph_infura import graph as infura_graph
from graphs.graph_solana import graph as solana_graph
from graphs.graph_crypto_portfolios import graph as crypto_portfolios_graph


def _extract_message_content(message: AIMessage) -> Optional[str]:
    """安全提取消息内容"""
    try:
        if isinstance(message.content, str):
            return message.content
        elif isinstance(message.content, list) and len(message.content) > 0:
            first_content = message.content[0]
            if isinstance(first_content, dict) and "text" in first_content:
                return first_content["text"]
            elif isinstance(first_content, str):
                return first_content
        return None
    except (IndexError, KeyError, AttributeError):
        return None


def _parse_routing_response(response: AIMessage) -> Optional[str]:
    """解析路由响应"""
    try:
        if not response.tool_calls:
            return None

        tool_call = response.tool_calls[0]
        tool_name = tool_call.get("name")

        if tool_name in ROUTE_MAPPING:
            return ROUTE_MAPPING[tool_name]["node_name"]
        elif tool_name in TOOL_TO_NODE_MAPPING:
            return TOOL_TO_NODE_MAPPING[tool_name]

        return None
    except (IndexError, KeyError, AttributeError):
        return None


def _extract_keywords(content: str) -> list:
    """从内容中提取关键词"""
    # DeFi和加密货币相关关键词
    crypto_keywords = [
        "swap",
        "trade",
        "exchange",
        "token",
        "coin",
        "price",
        "chart",
        "wallet",
        "balance",
        "transaction",
        "defi",
        "nft",
        "staking",
        "yield",
        "liquidity",
        "ethereum",
        "bitcoin",
        "solana",
        "polygon",
        "binance",
        "uniswap",
    ]

    # 搜索相关关键词
    search_keywords = [
        "search",
        "find",
        "lookup",
        "news",
        "information",
        "latest",
        "current",
        "what is",
        "how to",
        "where can",
        "when did",
    ]

    # 图像相关关键词
    image_keywords = [
        "image",
        "picture",
        "generate",
        "create",
        "visual",
        "photo",
        "art",
        "design",
        "draw",
        "illustration",
    ]

    found_keywords = []
    content_lower = content.lower()

    for keyword in crypto_keywords + search_keywords + image_keywords:
        if keyword in content_lower:
            found_keywords.append(keyword)

    return found_keywords


def _classify_user_intent(content: str) -> str:
    """分类用户意图"""
    content_lower = content.lower()

    if any(word in content_lower for word in ["swap", "trade", "exchange", "bridge"]):
        return "swap_intent"
    elif any(word in content_lower for word in ["price", "chart", "market", "quote"]):
        return "quote_intent"
    elif any(word in content_lower for word in ["search", "find", "news"]):
        return "search_intent"
    elif any(
        word in content_lower for word in ["image", "generate", "create", "picture"]
    ):
        return "image_intent"
    elif any(word in content_lower for word in ["wallet", "connect", "balance"]):
        return "wallet_intent"
    elif any(word in content_lower for word in ["solana", "sol", "spl"]):
        return "solana_intent"
    elif any(word in content_lower for word in ["portfolio", "position", "asset"]):
        return "portfolio_intent"
    else:
        return "general_intent"


def _identify_pending_actions(content: str) -> list:
    """识别AI响应中提到的待处理操作"""
    pending_actions = []
    content_lower = content.lower()

    action_patterns = [
        ("need to check", "verification_needed"),
        ("let me search", "search_needed"),
        ("i can help you", "assistance_offered"),
        ("would you like", "user_confirmation_needed"),
        ("please provide", "additional_info_needed"),
        ("i need to", "action_required"),
    ]

    for pattern, action_type in action_patterns:
        if pattern in content_lower:
            pending_actions.append(action_type)

    return pending_actions


def _build_enhanced_routing_prompt(
    ai_message: AIMessage, context: dict, recent_messages: list
) -> HumanMessage:
    """构建增强的路由判断提示"""

    ai_content = _extract_message_content(ai_message)
    if not ai_content:
        return None

    # 构建上下文信息
    context_info = f"""
    Recent conversation context:
    - User intents: {', '.join(context.get('user_intents', []))}
    - Key topics mentioned: {', '.join(context.get('mentioned_keywords', []))}
    - Tools recently used: {', '.join(context.get('tool_usage_history', []))}
    - Pending actions: {', '.join(context.get('pending_actions', []))}
    """

    # 构建最近消息摘要
    recent_conversation = ""
    for i, msg in enumerate(recent_messages[-3:]):
        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
        content = (
            msg.content
            if isinstance(msg.content, str)
            else str(msg.content)[:200] + "..."
        )
        recent_conversation += f"\n{role}: {content}"

    prompt_text = f"""
    You are a smart routing agent that determines if the AI response requires specialized processing.
    
    Current AI Response: {ai_content}
    
    {context_info}
    
    Recent Conversation:{recent_conversation}
    
    Available specialized agents and their capabilities:
    
    1. Swap Agent - Token swapping, cross-chain transactions, bridging
    2. Wallet Agent - Wallet connection, network switching, account management  
    3. Search Agent - Web search, news lookup, content retrieval
    4. Quote Agent - Price data, market analysis, trading signals
    5. Image Agent - Image generation, visual content creation
    6. Infura Agent - Blockchain data, transaction details, smart contract interaction
    7. Solana Agent - Solana-specific operations, SPL tokens, Solana DeFi
    8. Crypto Portfolios Agent - Portfolio management, asset tracking, position analysis
    
    Analysis Guidelines:
    1. Consider the FULL conversation context, not just the last message
    2. Look for incomplete information that needs specialized processing
    3. Identify if user intent requires specific domain expertise
    4. Check if the AI response mentions actions requiring specialized tools
    5. Consider follow-up questions that might need expert knowledge
    
    If routing is needed, call the appropriate routing tool. If the response is complete and no specialized processing is required, do not call any tools.
    """

    return HumanMessage(content=prompt_text)


async def _enhanced_intelligent_routing(messages: list) -> Optional[str]:
    """
    增强的智能路由决策引擎
    """
    try:
        # 分析对话上下文
        context = await _analyze_conversation_context(messages)

        # 获取最后一条AI消息
        last_ai_message = None
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break

        if not last_ai_message:
            return None

        # 构建增强的路由提示
        enhanced_prompt = _build_enhanced_routing_prompt(
            last_ai_message, context, messages[-3:] if len(messages) >= 3 else messages
        )

        # 使用轻量级LLM进行路由决策
        router_llm = ChatAnthropic(
            model="claude-3-5-haiku-latest",
            temperature=0.1,
            max_tokens=150,
        )

        llm_with_tools = router_llm.bind_tools(tools_router)
        response = await llm_with_tools.ainvoke([enhanced_prompt])

        return _parse_routing_response(response)

    except Exception as e:
        print(f"Error in enhanced intelligent routing: {e}")
        return None


async def _analyze_conversation_context(messages: list, window_size: int = 5) -> dict:
    """
    分析对话上下文，提取关键信息用于路由决策

    Args:
        messages: 完整消息历史
        window_size: 分析的消息窗口大小

    Returns:
        包含上下文信息的字典
    """
    # 获取最近的消息窗口
    recent_messages = (
        messages[-window_size:] if len(messages) > window_size else messages
    )

    context = {
        "user_intents": [],
        "mentioned_keywords": [],
        "tool_usage_history": [],
        "conversation_flow": [],
        "pending_actions": [],
    }

    # 分析每条消息
    for msg in recent_messages:
        if isinstance(msg, HumanMessage):
            # 提取用户意图关键词
            content = (
                msg.content.lower()
                if isinstance(msg.content, str)
                else str(msg.content).lower()
            )
            context["mentioned_keywords"].extend(_extract_keywords(content))
            context["user_intents"].append(_classify_user_intent(content))

        elif isinstance(msg, AIMessage):
            # 分析AI响应中的工具使用
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    context["tool_usage_history"].append(tool_call.get("name"))

            # 分析AI是否提到了需要进一步处理的内容
            ai_content = _extract_message_content(msg)
            if ai_content:
                context["pending_actions"].extend(_identify_pending_actions(ai_content))

    return context


async def aget_next_node(messages: list) -> Optional[str]:
    """
    增强版路由决策函数

    Args:
        messages: 消息历史列表

    Returns:
        下一个节点名称，如果不需要路由则返回None
    """
    try:
        if not messages:
            return None

        # 获取最后一个AI消息
        last_ai_message = None
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break

        if not last_ai_message:
            return None

        # 1. 首先检查直接的工具调用
        if hasattr(last_ai_message, "tool_calls") and last_ai_message.tool_calls:
            for tool_call in last_ai_message.tool_calls:
                tool_name = tool_call.get("name")
                if tool_name:
                    # 从路由映射获取节点
                    if tool_name in ROUTE_MAPPING:
                        return ROUTE_MAPPING[tool_name]["node_name"]
                    elif tool_name in TOOL_TO_NODE_MAPPING:
                        return TOOL_TO_NODE_MAPPING[tool_name]

        # 2. 如果没有直接工具调用，使用增强的智能路由
        return await _enhanced_intelligent_routing(messages)

    except Exception as e:
        print(f"Error in enhanced get_next_node: {e}")
        return None


async def node_swap_graph(state: State):
    _response = await swap_graph.ainvoke(state)
    next_node = await aget_next_node(_response["messages"])
    if next_node and next_node != node_swap_graph.__name__:
        _response["messages"].pop()
        return Command(
            goto=next_node,
            update=_response,
        )
    else:
        return Command(
            goto=END,
            update=_response,
        )


async def node_wallet_graph(state: State):
    _response = await wallet_graph.ainvoke(state)
    next_node = await aget_next_node(_response["messages"])
    if next_node and next_node != node_wallet_graph.__name__:
        _response["messages"].pop()
        return Command(
            goto=next_node,
            update=_response,
        )
    else:
        return Command(
            goto=END,
            update=_response,
        )


async def node_search_graph(state: State):
    _response = await search_graph.ainvoke(state)
    next_node = await aget_next_node(_response["messages"])
    if next_node and next_node != node_search_graph.__name__:
        _response["messages"].pop()
        return Command(
            goto=next_node,
            update=_response,
        )
    else:
        return Command(
            goto=END,
            update=_response,
        )


async def node_quote_graph(state: State):
    _response = await quote_graph.ainvoke(state)
    next_node = await aget_next_node(_response["messages"])
    if next_node and next_node != node_quote_graph.__name__:
        _response["messages"].pop()
        return Command(
            goto=next_node,
            update=_response,
        )
    else:
        return Command(
            goto=END,
            update=_response,
        )


async def node_image_graph(state: State):
    _response = await image_graph.ainvoke(state)
    next_node = await aget_next_node(_response["messages"])
    if next_node and next_node != node_image_graph.__name__:
        _response["messages"].pop()
        return Command(
            goto=next_node,
            update=_response,
        )
    else:
        return Command(
            goto=END,
            update=_response,
        )


async def node_infura_graph(state: State):
    _response = await infura_graph.ainvoke(state)
    next_node = await aget_next_node(_response["messages"])
    if next_node and next_node != node_infura_graph.__name__:
        _response["messages"].pop()
        return Command(
            goto=next_node,
            update=_response,
        )
    else:
        return Command(
            goto=END,
            update=_response,
        )


async def node_solana_graph(state: State):
    _response = await solana_graph.ainvoke(state)
    next_node = await aget_next_node(_response["messages"])
    if next_node and next_node != node_solana_graph.__name__:
        _response["messages"].pop()
        return Command(
            goto=next_node,
            update=_response,
        )
    else:
        return Command(
            goto=END,
            update=_response,
        )


async def node_crypto_portfolios_graph(state: State):
    _response = await crypto_portfolios_graph.ainvoke(state)
    next_node = await aget_next_node(_response["messages"])
    if next_node and next_node != node_crypto_portfolios_graph.__name__:
        _response["messages"].pop()
        return Command(
            goto=next_node,
            update=_response,
        )
    else:
        return Command(
            goto=END,
            update=_response,
        )


graph_builder.add_node(node_llm.get_name(), node_llm)
# graph_builder.add_node(node_chatbot)
graph_builder.add_node(node_swap_graph)
graph_builder.add_node(node_wallet_graph)
graph_builder.add_node(node_search_graph)
graph_builder.add_node(node_quote_graph)
graph_builder.add_node(node_image_graph)
graph_builder.add_node(node_infura_graph)
graph_builder.add_node(node_solana_graph)
graph_builder.add_node(node_crypto_portfolios_graph)

# add edge
graph_builder.add_edge(START, node_llm.get_name())


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
