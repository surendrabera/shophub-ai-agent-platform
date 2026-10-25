from app.agent import run_agent


def test_agent_remembers_previous_order():
    thread_id = "memory-test-001"

    first_result = run_agent(
        "Find order 1001",
        thread_id=thread_id,
    )
    assert first_result["success"] is True

    second_result = run_agent(
        "What is its status?",
        thread_id=thread_id,
    )

    assert second_result["success"] is True
    assert second_result["data"]["id"] == 1001
    assert second_result["data"]["status"] == "PAID"