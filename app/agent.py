
from app.fake_llm import fake_llm
from app.tools import get_order_by_id, get_orders_by_status


TOOL_REGISTRY = {
    "get_order_by_id": {
        "function": get_order_by_id,
        "description": "Find one order using its ID.",
        "required_arguments": {"order_id": int},
    },
    "get_orders_by_status": {
        "function": get_orders_by_status,
        "description": "Find orders matching a status.",
        "required_arguments": {"status": str},
    },
}


def execute_tool(tool_name, arguments):
    """Validate and execute one registered tool."""

    tool_definition = TOOL_REGISTRY.get(tool_name)

    if tool_definition is None:
        return {
            "success": False,
            "data": None,
            "error": "Unknown tool",
        }

    if not isinstance(arguments, dict):
        return {
            "success": False,
            "data": None,
            "error": "Tool arguments must be a dictionary",
        }

    required_arguments = tool_definition["required_arguments"]

    # Require exactly the declared arguments for this tool.
    if set(arguments) != set(required_arguments):
        return {
            "success": False,
            "data": None,
            "error": "Invalid tool arguments",
        }

    for name, expected_type in required_arguments.items():
        value = arguments[name]

        # bool is a subclass of int in Python, so reject it for integer IDs.
        if expected_type is int:
            valid = isinstance(value, int) and not isinstance(value, bool)
        else:
            valid = isinstance(value, expected_type)

        if not valid:
            return {
                "success": False,
                "data": None,
                "error": f"Invalid type for argument: {name}",
            }

    try:
        return tool_definition["function"](**arguments)
    except Exception:
        # Keep internal exception details out of the returned result.
        return {
            "success": False,
            "data": None,
            "error": "Tool execution failed",
        }


def run_agent(user_message):
    """Select a tool and execute it."""

    decision = fake_llm(user_message)

    tool_name = decision.get("tool")

    if tool_name is None:
        return {
            "success": False,
            "data": None,
            "error": decision.get(
                "message",
                "No tool selected",
            ),
        }

    return execute_tool(
        tool_name,
        decision.get("arguments", {}),
    )
