
from app.fake_llm import fake_llm
from app.agent import run_agent


def test_fake_llm_selects_order_lookup():
    decision = fake_llm("Find order 1001")

    assert decision["tool"] == "get_order_by_id"
    assert decision["arguments"]["order_id"] == 1001


def test_fake_llm_selects_status_filter():
    decision = fake_llm("Show paid orders")

    assert decision["tool"] == "get_orders_by_status"
    assert decision["arguments"]["status"] == "paid"


def test_fake_llm_handles_unknown_request():
    decision = fake_llm("Tell me a joke")

    assert decision["tool"] is None


def test_agent_executes_selected_tool():
    result = run_agent("Find order 1001")

    assert result["success"] is True
    assert result["data"]["id"] == 1001


def test_agent_handles_missing_order():
    result = run_agent("Find order 9999")

    assert result["success"] is False
    assert result["error"] == "Order not found"
