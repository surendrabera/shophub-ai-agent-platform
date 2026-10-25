
from fastapi.testclient import TestClient

from app.store_api import app

client = TestClient(app)

MERCHANT_A_HEADERS = {
    "Authorization": "Bearer token-merchant-a-demo"
}

MERCHANT_B_HEADERS = {
    "Authorization": "Bearer token-merchant-b-demo"
}

UNASSIGNED_HEADERS = {
    "Authorization": "Bearer token-no-merchant-demo"
}


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_auth_me_returns_merchant_a():
    response = client.get(
        "/auth/me",
        headers=MERCHANT_A_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "user": "support_agent_a",
        "merchant": "merchant_a",
    }


def test_merchant_a_can_list_own_orders():
    response = client.get(
        "/orders",
        headers=MERCHANT_A_HEADERS,
    )

    assert response.status_code == 200

    orders = response.json()

    assert len(orders) == 6
    assert all(order["merchant"] == "merchant_a" for order in orders)


def test_merchant_b_can_list_own_orders():
    response = client.get(
        "/orders",
        headers=MERCHANT_B_HEADERS,
    )

    assert response.status_code == 200

    orders = response.json()

    assert len(orders) == 6
    assert all(order["merchant"] == "merchant_b" for order in orders)


def test_merchant_a_can_filter_paid_orders():
    response = client.get(
        "/orders?status=PAID",
        headers=MERCHANT_A_HEADERS,
    )

    assert response.status_code == 200

    orders = response.json()

    assert len(orders) > 0
    assert all(order["merchant"] == "merchant_a" for order in orders)
    assert all(order["status"] == "PAID" for order in orders)


def test_merchant_a_can_lookup_own_order():
    response = client.get(
        "/orders/lookup?id=1001",
        headers=MERCHANT_A_HEADERS,
    )

    assert response.status_code == 200

    result = response.json()

    assert result["status"] is True
    assert result["order"]["id"] == "1001"
    assert result["order"]["merchant"] == "merchant_a"


def test_merchant_a_cannot_lookup_merchant_b_order():
    response = client.get(
        "/orders/lookup?id=2001",
        headers=MERCHANT_A_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": False,
        "message": "Order not found",
    }


def test_unknown_order_lookup_uses_failure_envelope():
    response = client.get(
        "/orders/lookup?id=9999",
        headers=MERCHANT_A_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": False,
        "message": "Order not found",
    }


def test_request_without_token_is_rejected():
    response = client.get("/orders")

    assert response.status_code == 401


def test_request_with_invalid_token_is_rejected():
    response = client.get(
        "/orders",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_unassigned_merchant_token_is_rejected_for_orders():
    response = client.get(
        "/orders",
        headers=UNASSIGNED_HEADERS,
    )

    assert response.status_code == 403
def test_merchant_can_refund_paid_order():
    response = client.post(
        "/orders/refund",
        headers=MERCHANT_A_HEADERS,
        json={"id": "1003"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["order"]["status"] == "REFUNDED"


def test_merchant_can_cancel_placed_order():
    response = client.post(
        "/orders/cancel",
        headers=MERCHANT_A_HEADERS,
        json={"id": "1005"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["order"]["status"] == "CANCELLED"


def test_cannot_refund_shipped_order():
    response = client.post(
        "/orders/refund",
        headers=MERCHANT_A_HEADERS,
        json={"id": "1002"},
    )

    assert response.status_code == 409


def test_cannot_cancel_shipped_order():
    response = client.post(
        "/orders/cancel",
        headers=MERCHANT_A_HEADERS,
        json={"id": "1002"},
    )

    assert response.status_code == 409


def test_merchant_cannot_refund_another_merchants_order():
    response = client.post(
        "/orders/refund",
        headers=MERCHANT_A_HEADERS,
        json={"id": "2001"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


def test_refund_requires_authentication():
    response = client.post(
        "/orders/refund",
        json={"id": "1001"},
    )

    assert response.status_code == 401