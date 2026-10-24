
from app.data import orders


def make_result(success, data=None, error=None):
    """Return a consistent structure for tool results."""
    return {
        "success": success,
        "data": data,
        "error": error
    }


def get_order_by_id(order_id):
    """Find an order by its ID."""
    if not isinstance(order_id, int) or isinstance(order_id, bool):
        return make_result(
            False,
            error="Order ID must be an integer"
        )

    for order in orders:
        if order["id"] == order_id:
            return make_result(True, data=order)

    return make_result(False, error="Order not found")


def get_orders_by_status(status):
    """Return all orders matching a status."""
    if not isinstance(status, str) or not status.strip():
        return make_result(
            False,
            error="Status must be a non-empty string"
        )

    normalized_status = status.strip().upper()

    result = [
        order
        for order in orders
        if order["status"] == normalized_status
    ]

    return make_result(True, data=result)
