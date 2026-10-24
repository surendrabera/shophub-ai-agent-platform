
import re


def fake_llm(user_message):
    """Return a scripted tool call for a recognized request."""

    message = user_message.strip().lower()

    # Example: "Find order 1001"
    order_match = re.search(
        r"\b(?:find|lookup|look up|show)\s+order\s+(\d+)\b",
        message,
    )

    if order_match:
        return {
            "tool": "get_order_by_id",
            "arguments": {
                "order_id": int(order_match.group(1))
            },
        }

    # Example: "Show paid orders"
    status_match = re.search(
        r"\b(?:show|list|get)\s+(?:all\s+)?"
        r"(paid|shipped|delivered|placed|cancelled|refunded)"
        r"\s+orders\b",
        message,
    )

    if status_match:
        return {
            "tool": "get_orders_by_status",
            "arguments": {
                "status": status_match.group(1)
            },
        }

    return {
        "tool": None,
        "arguments": {},
        "message": "Sorry, I could not understand that request.",
    }
