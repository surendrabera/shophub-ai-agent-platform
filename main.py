
orders = [
    {
        "id": 1001,
        "customer_name": "Maria",
        "status": "PAID",
        "total": 2000
    },
    {
        "id": 1002,
        "customer_name": "Rahul",
        "status": "SHIPPED",
        "total": 1500
    }
]


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


if __name__ == "__main__":
    print("Welcome to ShopHub Order Support")

    print("\nFind order 1001:")
    print(get_order_by_id(1001))

    print("\nFind missing order 9999:")
    print(get_order_by_id(9999))

    print("\nFind paid orders:")
    print(get_orders_by_status("paid"))
