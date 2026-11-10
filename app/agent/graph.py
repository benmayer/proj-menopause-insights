from langgraph.graph import END, START, StateGraph

from app.agent import nodes
from app.agent.state import AgentState


def build_graph():
    g = StateGraph(AgentState)
    for name in ("fetch", "analyse", "retrieve", "write", "check"):
        g.add_node(name, getattr(nodes, name))
    g.add_edge(START, "fetch")
    g.add_edge("fetch", "analyse")
    g.add_edge("analyse", "retrieve")
    g.add_edge("retrieve", "write")
    g.add_edge("write", "check")
    g.add_conditional_edges("check", nodes.route_after_check, {"write": "write", "end": END})
    return g.compile()
