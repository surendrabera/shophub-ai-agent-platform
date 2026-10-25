
from app.agent import run_agent


def test_agent_remembers_previous_order():
    thread_id = "memory-debug-001"

    # First message: retrieve order 1001.
    first_result = run_agent(
        "Find order 1001",
        thread_id=thread_id,
    )

    print("\nFIRST RESULT:", first_result)

    assert first_result["success"] is True
    assert first_result["data"]["id"] == 1001

    # Second message: ask about the same order.
    second_result = run_agent(
        "What is its status?",
        thread_id=thread_id,
    )

    print("\nSECOND RESULT:", second_result)

    assert second_result["success"] is True
    assert second_result["data"]["id"] == 1001
    assert second_result["data"]["status"] == "PAID"


def test_conversations_use_separate_memory():
    conversation_a = "memory-isolation-A"
    conversation_b = "memory-isolation-B"

    # Conversation A retrieves order 1001.
    result_a = run_agent(
        "Find order 1001",
        thread_id=conversation_a,
    )

    assert result_a["success"] is True
    assert result_a["data"]["id"] == 1001

    # Conversation B has no previous order context.
    result_b = run_agent(
        "What is its status?",
        thread_id=conversation_b,
    )

    assert result_b["success"] is False
