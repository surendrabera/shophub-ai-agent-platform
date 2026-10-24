
from app.data import orders


def get_order_by_id(order_id):
    if not isinstance(order_id, int) or isinstance(order_id, bool):
        raise ValueError("Order ID must be an integer")

    for order in orders:
        if order["id"] == order_id:
            return order

    return None


def get_orders_by_status(status):
    if not isinstance(status, str) or not status.strip():
        raise ValueError("Status must be a non-empty string")

    result = []

    for order in orders:
        if order["status"] == status.strip().upper():
            result.append(order)

    return result
