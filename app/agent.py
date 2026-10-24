
from app.fake_llm import fake_llm
from app.tools import get_order_by_id, get_orders_by_status


TOOLS = {
    "get_order_by_id": get_order_by_id,
    "get_orders_by_status": get_orders_by_status,
}


def run_agent(user_message):
    decision = fake_llm(user_message)

    tool_name = decision.get("tool")

    if tool_name is None:
        return {
            "success": False,
            "data": None,
            "error": decision.get(
                "message",
                "No tool selected"
            )
        }

    tool = TOOLS.get(tool_name)

    if tool is None:
        return {
            "success": False,
            "data": None,
            "error": "Unknown tool"
        }

    try:
        result = tool(**decision["arguments"])
        return result
    except Exception:
        # Avoid exposing internal exception details to the user.
        return {
            "success": False,
            "data": None,
            "error": "The requested operation failed"
        }
