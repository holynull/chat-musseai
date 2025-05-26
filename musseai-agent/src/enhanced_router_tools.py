import logging
import time
from datetime import datetime
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import ToolNode, tools_condition

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_router")


# 增强router_tools节点
class EnhancedRouterTools(ToolNode):
    def __init__(self, tools, name):
        super().__init__(tools=tools, name=name)
        self.routing_stats = {}

    def invoke(self, state, config=None):
        start_time = time.time()
        tool_name = None

        try:
            # 记录调用前信息
            if state["messages"] and len(state["messages"]) > 0:
                last_user_message = next(
                    (
                        m
                        for m in reversed(state["messages"])
                        if isinstance(m, HumanMessage)
                    ),
                    None,
                )
                if last_user_message:
                    logger.info(
                        f"Routing request: {last_user_message.content[:100]}..."
                    )

            # 调用原始工具节点
            result = super().invoke(state, config)

            # 分析结果，找出被调用的工具
            if isinstance(result, dict) and "messages" in result:
                last_message = result["messages"][-1] if result["messages"] else None
                if isinstance(last_message, ToolMessage):
                    tool_name = last_message.name

            # 记录路由统计
            elapsed = time.time() - start_time
            if tool_name:
                if tool_name not in self.routing_stats:
                    self.routing_stats[tool_name] = {"count": 0, "total_time": 0}
                self.routing_stats[tool_name]["count"] += 1
                self.routing_stats[tool_name]["total_time"] += elapsed
                logger.info(f"Routed to {tool_name} in {elapsed:.2f}s")

            return result
        except Exception as e:
            logger.error(f"Error in router tools: {e}")
            raise

    def get_stats(self):
        """获取路由统计信息"""
        return {
            "total_routes": sum(s["count"] for s in self.routing_stats.values()),
            "tools": {
                k: {
                    "count": v["count"],
                    "avg_time": v["total_time"] / v["count"] if v["count"] > 0 else 0,
                }
                for k, v in self.routing_stats.items()
            },
            "timestamp": datetime.now().isoformat(),
        }
