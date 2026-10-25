
import sqlite3
from typing import TypedDict, Any

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.fake_llm import fake_llm
from app.http_tools import get_order_by_id, get_orders_by_status



TOOL_REGISTRY = {
    "get_order_by_id": {
        "function": get_order_by_id,
        "required_arguments": {"order_id": int},
    },
    "get_orders_by_status": {
        "function": get_orders_by_status,
        "required_arguments": {"status": str},
    },
}


# 2. Define the graph's shared state.
class AgentState(TypedDict, total=False):
    user_message: str
    tool_name: str | None
    arguments: dict[str, Any]
    result: dict[str, Any]
    last_order_id: int
    authorization: str

# 3. Validate and execute a registered tool.
def execute_selected_tool(state: AgentState):
    tool_name = state["tool_name"]
    arguments = state.get("arguments", {})
    authorization = state.get("authorization")

    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        return {
            "result": {
                "success": False,
                "data": None,
                "error": "Missing or invalid authorization header",
            }
        }

    tool_definition = TOOL_REGISTRY.get(tool_name)

    if tool_definition is None:
        return {
            "result": {
                "success": False,
                "data": None,
                "error": "Unknown tool",
            }
        }

    if not isinstance(arguments, dict):
        return {
            "result": {
                "success": False,
                "data": None,
                "error": "Tool arguments must be a dictionary",
            }
        }

    required_arguments = tool_definition["required_arguments"]

    if set(arguments) != set(required_arguments):
        return {
            "result": {
                "success": False,
                "data": None,
                "error": "Invalid tool arguments",
            }
        }

    for name, expected_type in required_arguments.items():
        value = arguments[name]

        if expected_type is int:
            valid = isinstance(value, int) and not isinstance(value, bool)
        else:
            valid = isinstance(value, expected_type)

        if not valid:
            return {
                "result": {
                    "success": False,
                    "data": None,
                    "error": f"Invalid type for argument: {name}",
                }
            }

    try:
        result = tool_definition["function"](
            **arguments,
            authorization=authorization,
        )
    except Exception:
        result = {
            "success": False,
            "data": None,
            "error": "Tool execution failed",
        }

    updates = {"result": result}

    if (
        result.get("success")
        and isinstance(result.get("data"), dict)
        and "id" in result["data"]
    ):
        updates["last_order_id"] = result["data"]["id"]

    return updates

# 4. Node: Select a tool using the fake LLM.
def select_tool(state: AgentState):
    decision = fake_llm(state["user_message"])
    tool_name = decision.get("tool")

    updates = {
        "tool_name": tool_name,
        "arguments": decision.get("arguments", {}),
    }

    if tool_name is None:
        updates["result"] = {
            "success": False,
            "data": None,
            "error": decision.get(
                "message",
                "No tool selected",
            ),
        }

    return updates


# 5. Node: Execute the selected tool.
def execute_selected_tool(state: AgentState):
    result = execute_tool(
        state["tool_name"],
        state.get("arguments", {}),
    )

    return {"result": result}


# 6. Build the LangGraph workflow.
builder = StateGraph(AgentState)

builder.add_node("select_tool", select_tool)
builder.add_node("execute_tool", execute_selected_tool)

builder.add_edge(START, "select_tool")


# Route based on whether a tool was selected.
def route_after_selection(state: AgentState):
    if state.get("tool_name") is None:
        return END

    return "execute_tool"


builder.add_conditional_edges(
    "select_tool",
    route_after_selection,
    {
        "execute_tool": "execute_tool",
        END: END,
    },
)

builder.add_edge("execute_tool", END)


# 7. Set up the SQLite checkpointer.
conn = sqlite3.connect(
    "shophub_checkpoints.sqlite",
    check_same_thread=False,
)

checkpointer = SqliteSaver(conn)

agent_graph = builder.compile(
    checkpointer=checkpointer,
)


# 8. Invoke the graph.
def run_agent(
    user_message: str,
    authorization: str,
    thread_id: str = "default",
):
    final_state = agent_graph.invoke(
        {"user_message": user_message, "authorization": authorization},
        config={
            "configurable": {
                "thread_id": thread_id,
            }
        },
    )

    return final_state["result"]
