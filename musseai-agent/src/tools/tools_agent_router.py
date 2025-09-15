import datetime
from typing import Optional
from langchain_core.tools import tool
from agent_config import ROUTE_MAPPING, get_agent_by_tool, AGENT_CONFIGS, load_graph

@tool
def get_utc_time():
    """
    Useful when you need to get the current UTC time of the system.
    Returns the current UTC time in ISO format (YYYY-MM-DD HH:MM:SS.mmmmmm).
    """
    import pytz

    return datetime.datetime.now(tz=pytz.UTC).isoformat(" ")


def get_next_node(tool_name: str) -> Optional[str]:
    """获取下一个节点名称"""
    agent_config = get_agent_by_tool(tool_name)
    if not agent_config:
        print(f"No agent config found for tool: {tool_name}")
        return None

    # 动态导入子图
    agent_id = ROUTE_MAPPING.get(tool_name)
    graph = load_graph(agent_id)
    if not graph:
        print(f"Failed to load graph for agent: {agent_id}")
        return None

    return graph.get_name()


# 自动生成路由工具
def generate_routing_tools():
    """根据配置自动生成路由工具"""
    from langchain_core.tools import tool

    tools = []

    for agent_id, config in AGENT_CONFIGS.items():
        # 首先创建描述文本
        desc = f"This tool will hand over the question to a {config.name}.\nExpert capabilities include:\n"
        for cap in config.capabilities:
            desc += f"- {cap}\n"

        # 使用闭包创建唯一的函数
        def create_route_function(current_agent_id, current_config):
            tool_name = f"route_to_{current_config.graph_name}"

            @tool(name_or_callable=tool_name, description=desc)
            def route_func(query=None):
                return f"Now requesting a {current_config.name}."

            return route_func

        # 创建并添加函数
        route_func = create_route_function(agent_id, config)
        tools.append(route_func)

    return tools


# 生成所有路由工具
tools = generate_routing_tools() + [get_utc_time]  # 添加非路由工具
