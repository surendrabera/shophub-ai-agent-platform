
from app.tools import get_order_by_id, get_orders_by_status


def main():
    print("Welcome to ShopHub Order Support")

    print("\n--- Find existing order ---")
    print(get_order_by_id(1001))

    print("\n--- Find missing order ---")
    print(get_order_by_id(9999))

    print("\n--- Find order with invalid ID ---")
    print(get_order_by_id("abc"))

    print("\n--- Find paid orders ---")
    print(get_orders_by_status("paid"))

    print("\n--- Find orders with invalid status ---")
    print(get_orders_by_status(""))


if __name__ == "__main__":
    main()
