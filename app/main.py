
from app.agent import run_agent


def main():
    print("ShopHub Order Support")
    print("Try: Find order 1001")
    print("Try: Show paid orders")
    print("Type 'exit' to quit.")

    while True:
        user_message = input("\nYou: ").strip()

        if user_message.lower() == "exit":
            print("Goodbye!")
            break

        result = run_agent(user_message)
        print("Agent:", result)


if __name__ == "__main__":
    main()
