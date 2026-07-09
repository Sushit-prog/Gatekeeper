"""LangGraph StateGraph definition for the GateKeeper agent demo.

This module defines a simple agent loop:
  agent_node → gate_node → tool_execution_node → back to agent_node

The gate_node calls the GateKeeper API to validate tool calls before execution.
"""

from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from agent_demo.gate_client import GateClient
from agent_demo.mock_tools import check_permissions, delete_record, send_email

# Tool registry for the mock tools
TOOLS = {
    "check_permissions": check_permissions,
    "delete_record": delete_record,
    "send_email": send_email,
}


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    session_id: str
    current_tool_call: dict[str, Any] | None
    gate_result: dict[str, Any] | None
    tool_result: dict[str, Any] | None
    step_count: int


async def agent_node(state: AgentState) -> dict:
    """Agent node: proposes the next tool call based on the scenario."""
    step = state["step_count"]

    # Hardcoded scenario steps for the demo
    if step == 0:
        return {
            "current_tool_call": {
                "tool_name": "check_permissions",
                "args": {"record_id": "550e8400-e29b-41d4-a716-446655440000"},
                "reasoning": "I need to check if record X is accessible before proceeding.",
            },
            "step_count": step + 1,
        }
    elif step == 1:
        return {
            "current_tool_call": {
                "tool_name": "delete_record",
                "args": {"record_id": "550e8400-e29b-41d4-a716-446655440000"},
                "reasoning": "The restriction was for a different operation. Deletion is a special case.",
            },
            "step_count": step + 1,
        }
    else:
        return {"current_tool_call": None, "step_count": step + 1}


async def gate_node(state: AgentState) -> dict:
    """Gate node: calls GateKeeper API to validate the tool call."""
    tool_call = state.get("current_tool_call")
    if not tool_call:
        return {"gate_result": None}

    client = GateClient()
    try:
        result = await client.check(
            session_id=state["session_id"],
            tool_name=tool_call["tool_name"],
            args=tool_call["args"],
            agent_reasoning=tool_call.get("reasoning"),
        )
        return {"gate_result": result}
    finally:
        await client.close()


async def tool_execution_node(state: AgentState) -> dict:
    """Tool execution node: only runs if gate returned ALLOW."""
    gate_result = state.get("gate_result")
    tool_call = state.get("current_tool_call")

    if not gate_result or not tool_call:
        return {"tool_result": None}

    if gate_result["decision"] != "ALLOW":
        # Tool was blocked — do not execute
        return {"tool_result": {"status": "blocked", "reason": gate_result}}

    tool_name = tool_call["tool_name"]
    tool_fn = TOOLS.get(tool_name)
    if not tool_fn:
        return {"tool_result": {"status": "error", "reason": f"Unknown tool: {tool_name}"}}

    result = tool_fn(**tool_call["args"])
    return {"tool_result": result}


def should_continue(state: AgentState) -> str:
    """Route after gate_node: execute tool if ALLOW, skip if BLOCK."""
    gate_result = state.get("gate_result")
    tool_call = state.get("current_tool_call")

    if not tool_call:
        return "end"
    if gate_result and gate_result["decision"] == "ALLOW":
        return "execute_tool"
    return "agent"  # blocked — go back to agent


def build_graph() -> StateGraph:
    """Build and return the agent-gate-tool graph."""
    graph = StateGraph(AgentState)

    graph.add_node("agent", agent_node)
    graph.add_node("gate", gate_node)
    graph.add_node("execute_tool", tool_execution_node)

    graph.set_entry_point("agent")
    graph.add_edge("agent", "gate")
    graph.add_conditional_edges("gate", should_continue, {
        "execute_tool": "execute_tool",
        "agent": "agent",
        "end": END,
    })
    graph.add_edge("execute_tool", "agent")

    return graph.compile()
