
from app.agent import execute_tool, run_agent


def test_valid_tool_execution():
    result = execute_tool(
        "get_order_by_id",
        {"order_id": 1001},
    )

    assert result["success"] is True
    assert result["data"]["id"] == 1001


def test_unknown_tool_is_rejected():
    result = execute_tool("delete_everything", {})

    assert result["success"] is False
    assert result["error"] == "Unknown tool"


def test_missing_argument_is_rejected():
    result = execute_tool("get_order_by_id", {})

    assert result["success"] is False
    assert result["error"] == "Invalid tool arguments"


def test_extra_argument_is_rejected():
    result = execute_tool(
        "get_order_by_id",
        {"order_id": 1001, "merchant": "other"},
    )

    assert result["success"] is False
    assert result["error"] == "Invalid tool arguments"


def test_wrong_argument_type_is_rejected():
    result = execute_tool(
        "get_order_by_id",
        {"order_id": "1001"},
    )

    assert result["success"] is False
    assert result["error"] == "Invalid type for argument: order_id"


def test_boolean_order_id_is_rejected():
    result = execute_tool(
        "get_order_by_id",
        {"order_id": True},
    )

    assert result["success"] is False
    assert result["error"] == "Invalid type for argument: order_id"


def test_agent_still_handles_user_requests():
    result = run_agent("Find order 1001")

    assert result["success"] is True
    assert result["data"]["customer_name"] == "Maria"
