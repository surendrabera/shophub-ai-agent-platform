
from app.tools import get_order_by_id, get_orders_by_status


def main():
    print("Welcome to ShopHub Order Support")

    print("\nFind order 1001:")
    print(get_order_by_id(1001))

    print("\nFind missing order 9999:")
    print(get_order_by_id(9999))

    print("\nFind paid orders:")
    print(get_orders_by_status("paid"))


if __name__ == "__main__":
    main()
