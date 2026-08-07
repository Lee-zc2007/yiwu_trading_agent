"""LangGraph 扩展入口预留。

第一版不引入 LangGraph 依赖。未来可将 tool_router、human_confirmation、final_answer
三个节点接入此模块，但工具白名单和人工确认边界必须保持不变。
"""


def graph_status() -> dict:
    return {"enabled": False, "reason": "MVP 使用轻量 Tool Calling 服务，LangGraph 仅预留接口"}
