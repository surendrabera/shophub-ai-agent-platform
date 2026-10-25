
from app.agent import run_agent


def test_agent_uses_sqlite_checkpointing():
    thread_id = "persistence-test-001"

    result = run_agent(
        "Find order 1001",
        thread_id=thread_id,
    )

    assert result["success"] is True
    assert result["data"]["id"] == 1001
