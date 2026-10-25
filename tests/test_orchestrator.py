
from fastapi.testclient import TestClient

from app.orchestrator import app, fake_llm_router

client = TestClient(app)

MERCHANT_A_HEADERS = {
    "Authorization": "Bearer token-merchant-a-demo"
}


def test_router_lists_paid_orders():
    result = fake_llm_router({
        "query": "Show me all paid orders",
    })

    assert result["method"] == "orders.list"
    assert result["params"] == {"status": "PAID"}


def test_router_looks_up_specific_order():
    result = fake_llm_router({
        "query": "Find order 1001",
    })

    assert result["method"] == "orders.lookup"
    assert result["params"] == {"id": "1001"}


def test_router_detects_refund_before_order_lookup():
    result = fake_llm_router({
        "query": "Refund order 1001",
    })

    assert result["method"] == "unsupported_action"


def test_router_detects_cancellation_before_order_lookup():
    result = fake_llm_router({
        "query": "Cancel order 1001",
    })

    assert result["method"] == "unsupported_action"


def test_router_handles_unsupported_request():
    result = fake_llm_router({
        "query": "Tell me a joke",
    })

    assert result["method"] == "unsupported"


def test_chat_requires_bearer_token():
    response = client.post(
        "/chat",
        json={"message": "Show me all orders"},
    )

    assert response.status_code == 401


def test_refund_request_is_not_executed_automatically():
    response = client.post(
        "/chat",
        headers=MERCHANT_A_HEADERS,
        json={"message": "Refund order 1001"},
    )

    assert response.status_code == 200
    assert "approval workflow" in response.json()["answer"].lower()


def test_cancel_request_is_not_executed_automatically():
    response = client.post(
        "/chat",
        headers=MERCHANT_A_HEADERS,
        json={"message": "Cancel order 1001"},
    )

    assert response.status_code == 200
    assert "approval workflow" in response.json()["answer"].lower()


def test_unsupported_request_does_not_call_sub_agent():
    response = client.post(
        "/chat",
        headers=MERCHANT_A_HEADERS,
        json={"message": "Tell me a joke"},
    )

    assert response.status_code == 200
    assert "list orders" in response.json()["answer"].lower()
