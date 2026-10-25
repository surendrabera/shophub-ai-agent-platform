
from fastapi.testclient import TestClient

from app import approval_store
from app import orchestrator


client = TestClient(orchestrator.app)

MERCHANT_A_HEADERS = {
    "Authorization": "Bearer token-merchant-a-demo"
}


def fake_graph_result(answer):
    return {
        "answer": answer,
        "error": None,
        "result": None,
    }


def test_eval_01_lookup_order_status(monkeypatch):
    """A chat response can report an order's status."""

    def fake_invoke(state):
        assert state["query"] == "What is the status of order 1002?"
        assert state["authorization"] == MERCHANT_A_HEADERS["Authorization"]
        return fake_graph_result(
            "Order 1002 has status SHIPPED and a total of 799.00."
        )

    monkeypatch.setattr(
        orchestrator.orchestrator_graph,
        "invoke",
        fake_invoke,
    )

    response = client.post(
        "/chat",
        headers=MERCHANT_A_HEADERS,
        json={"message": "What is the status of order 1002?"},
    )

    assert response.status_code == 200
    assert "1002" in response.json()["answer"]
    assert "SHIPPED" in response.json()["answer"]


def test_eval_02_unknown_order_is_not_found(monkeypatch):
    """Unknown orders receive a not-found response."""

    def fake_invoke(state):
        return fake_graph_result("Order 9999 was not found.")

    monkeypatch.setattr(
        orchestrator.orchestrator_graph,
        "invoke",
        fake_invoke,
    )

    response = client.post(
        "/chat",
        headers=MERCHANT_A_HEADERS,
        json={"message": "Find order 9999"},
    )

    assert response.status_code == 200
    assert "not found" in response.json()["answer"].lower()


def test_eval_03_foreign_order_is_not_disclosed(monkeypatch):
    """The response does not disclose another merchant's order."""

    def fake_invoke(state):
        assert state["authorization"] == MERCHANT_A_HEADERS["Authorization"]
        return fake_graph_result("Order 2001 was not found.")

    monkeypatch.setattr(
        orchestrator.orchestrator_graph,
        "invoke",
        fake_invoke,
    )

    response = client.post(
        "/chat",
        headers=MERCHANT_A_HEADERS,
        json={"message": "Find order 2001"},
    )

    assert response.status_code == 200
    answer = response.json()["answer"].lower()
    assert "not found" in answer
    assert "merchant_b" not in answer


def test_eval_04_refund_requires_approval(monkeypatch, tmp_path):
    """Creating a refund proposal does not execute the refund."""

    monkeypatch.setattr(
        approval_store,
        "DATABASE_PATH",
        tmp_path / "evaluation_approvals.db",
    )
    approval_store.initialize_database()

    calls = []

    def fake_rpc(method, params, authorization):
        calls.append(method)

        assert authorization == MERCHANT_A_HEADERS["Authorization"]

        if method == "orders.lookup":
            assert params == {"id": "1001"}
            return {
                "http_status": 200,
                "body": {
                    "status": True,
                    "order": {
                        "id": "1001",
                        "merchant": "merchant_a",
                        "status": "PAID",
                        "total": 1499.0,
                    },
                },
            }

        raise AssertionError(f"Unexpected RPC call: {method}")

    monkeypatch.setattr(
        orchestrator,
        "call_orders_rpc",
        fake_rpc,
    )

    response = client.post(
        "/approvals/propose",
        headers=MERCHANT_A_HEADERS,
        json={"message": "Refund order 1001"},
    )

    assert response.status_code == 200
    payload = response.json()
    proposal = payload["proposal"]

    assert proposal["order_id"] == "1001"
    assert proposal["merchant_id"] == "merchant_a"
    assert proposal["action"] == "refund"
    assert proposal["status"] == "pending"
    assert proposal["amount"] == 1499.0
    assert calls == ["orders.lookup"]


def test_eval_05_rejected_refund_is_not_executed(monkeypatch, tmp_path):
    """Rejecting a proposal does not execute a refund."""

    monkeypatch.setattr(
        approval_store,
        "DATABASE_PATH",
        tmp_path / "evaluation_rejection.db",
    )
    approval_store.initialize_database()

    proposal = approval_store.create_proposal(
        order_id="1001",
        merchant_id="merchant_a",
        action="refund",
        amount=1499.0,
    )

    calls = []

    def fake_rpc(method, params, authorization):
        calls.append(method)

        assert authorization == MERCHANT_A_HEADERS["Authorization"]

        if method == "orders.me":
            return {
                "http_status": 200,
                "body": {
                    "user": "support_agent_a",
                    "merchant": "merchant_a",
                },
            }

        raise AssertionError(
            f"Unexpected RPC call after rejection: {method}"
        )

    monkeypatch.setattr(
        orchestrator,
        "call_orders_rpc",
        fake_rpc,
    )

    response = client.post(
        f"/approvals/{proposal['proposal_id']}/decision",
        headers=MERCHANT_A_HEADERS,
        json={"decision": "rejected"},
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["proposal"]["status"] == "rejected"
    assert "orders.refund" not in calls

    saved = approval_store.get_proposal(proposal["proposal_id"])
    assert saved["status"] == "rejected"

