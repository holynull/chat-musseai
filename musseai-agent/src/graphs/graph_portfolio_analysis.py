from typing import Annotated, cast
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import ToolMessage

from tools.tools_portfolio_analysis import tools
from agent_config import tools_condition, ROUTE_MAPPING
from tools.tools_agent_router import generate_routing_tools
from langgraph.types import Command
from loggers import logger

GRAPH_NAME = "graph_portfolio_analysis"

# Initialize LLM
_llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    temperature=0.7,
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

    system_prompt = f"""You are an expert cryptocurrency portfolio analyst specializing in investment analysis, risk assessment, and strategic recommendations for digital asset portfolios.

CORE EXPERTISE:
✓ Portfolio performance analysis and benchmarking
✓ Risk assessment and management strategies
✓ Market trend analysis and opportunity identification
✓ Investment strategy optimization
✓ Tax efficiency and reporting analysis

ANALYTICAL CAPABILITIES:
1. Performance Analytics
   - Time-weighted and money-weighted returns
   - Risk-adjusted performance metrics (Sharpe, Sortino ratios)
   - Comparative analysis against market benchmarks
   - Attribution analysis by asset and strategy

2. Risk Assessment
   - Portfolio volatility and correlation analysis
   - Value at Risk (VaR) calculations
   - Stress testing and scenario analysis
   - Concentration risk evaluation

3. Market Intelligence
   - Technical and fundamental analysis integration
   - Market sentiment analysis
   - Trend identification and momentum tracking
   - Opportunity scoring and alerts

4. Strategic Recommendations
   - Portfolio rebalancing suggestions
   - Tax-loss harvesting opportunities
   - Entry and exit point recommendations
   - Diversification strategies

CURRENT USER CONTEXT:
- User ID: {state.get("user_id", "Unknown")}
- Wallet Status: {wallet_status}
{f"- Connected Chain ID: {state.get('chain_id')}" if state.get('chain_id') else ""}
{f"- Connected Wallet Address: {state.get('wallet_address')}" if state.get('wallet_address') else ""}

ANALYSIS WORKFLOW:

📊 PORTFOLIO OVERVIEW:
1. Use analyze_portfolio_overview() for comprehensive summary
2. Check portfolio_health_check() for quick assessment
3. Review get_portfolio_metrics() for key indicators

📈 PERFORMANCE ANALYSIS:
1. Calculate returns with analyze_portfolio_performance()
2. Compare against benchmarks using compare_to_benchmarks()
3. Analyze historical performance with get_historical_performance()

⚠️ RISK ASSESSMENT:
1. Evaluate risk metrics with analyze_portfolio_risk()
2. Run stress tests using portfolio_stress_test()
3. Check correlations with analyze_asset_correlations()

💡 RECOMMENDATIONS:
1. Get rebalancing suggestions with get_rebalancing_recommendations()
2. Identify opportunities using find_investment_opportunities()
3. Check tax strategies with analyze_tax_implications()

📱 ALERTS & MONITORING:
1. Set up alerts with create_portfolio_alert()
2. Monitor key metrics with get_portfolio_alerts()
3. Track changes with analyze_portfolio_changes()

ANALYSIS PRINCIPLES:
- Provide data-driven insights with clear reasoning
- Consider both short-term and long-term perspectives
- Balance risk and return in all recommendations
- Account for user's investment goals and risk tolerance
- Include market context in all analyses
- Highlight both opportunities and risks
- Provide actionable recommendations with specific steps

COMMUNICATION STYLE:
- Use clear, professional language
- Visualize data when possible (charts, tables)
- Prioritize most important insights
- Provide confidence levels for predictions
- Include relevant market context
- Explain complex concepts simply

PRICE DISPLAY REQUIREMENTS:
- All prices and monetary values must be displayed in USD ($)
- Use USD as the base currency for all calculations and comparisons
- When displaying prices, always include the USD symbol ($) or explicitly state "USD"
- For non-USD native tokens, convert to USD equivalent using current market rates
- Clearly indicate when prices are estimates or based on specific exchange rates

Your mission is to provide institutional-quality portfolio analysis and recommendations that help users make informed investment decisions and optimize their cryptocurrency portfolios.
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
    tools=tools + generate_routing_tools(), name="node_tools_portfolio_analysis"
)

# Set up LLM node
from langgraph.utils.runnable import RunnableCallable

node_llm = RunnableCallable(call_model, acall_model, name="node_llm_portfolio_analysis")

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
