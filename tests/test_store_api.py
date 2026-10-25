from fastapi.testclient import TestClient

from app.store_api import app
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.store_api import app, ORDERS
# Keep a clean copy of the initial orders for test isolation.
ORIGINAL_ORDERS = deepcopy(ORDERS)


@pytest.fixture(autouse=True)
def reset_orders():
    """Reset order data before every test."""
    ORDERS[:] = deepcopy(ORIGINAL_ORDERS)

client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_authentication_without_token():
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_authentication_with_valid_token():
    response = client.get(
        "/auth/me",
        headers={
            "Authorization": "Bearer token_merchant_a"
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "merchant_id": "merchant_a",
    }


def test_list_orders_returns_only_own_merchant_orders():
    response = client.get(
        "/orders",
        headers={
            "Authorization": "Bearer token_merchant_a"
        },
    )

    assert response.status_code == 200

    orders = response.json()

    assert len(orders) > 0

    for order in orders:
        assert order["merchant"] == "merchant_a"


def test_merchant_cannot_access_another_merchants_order():
    response = client.get(
        "/orders/lookup?id=1002",
        headers={
            "Authorization": "Bearer token_merchant_a"
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": False,
        "message": "Order not found",
    }


def test_merchant_can_access_own_order():
    response = client.get(
        "/orders/lookup?id=1001",
        headers={
            "Authorization": "Bearer token_merchant_a"
        },
    )

    assert response.status_code == 200

    order = response.json()

    assert order["id"] == 1001
    assert order["merchant"] == "merchant_a"


def test_authentication_with_invalid_token():
    response = client.get(
        "/auth/me",
        headers={
            "Authorization": "Bearer invalid_token"
        },
    )

    assert response.status_code == 401


def test_filter_orders_by_status():
    response = client.get(
        "/orders?status=PAID",
        headers={
            "Authorization": "Bearer token_merchant_a"
        },
    )

    assert response.status_code == 200

    orders = response.json()

    for order in orders:
        assert order["merchant"] == "merchant_a"
        assert order["status"] == "PAID"

def test_refund_paid_order():
    response = client.post(
        "/orders/1001/refund",
        headers={
            "Authorization": "Bearer token_merchant_a"
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["order"]["status"] == "REFUNDED"


def test_cannot_refund_order_twice():
    headers = {
        "Authorization": "Bearer token_merchant_a"
    }

    first_response = client.post(
        "/orders/1001/refund",
        headers=headers,
    )

    second_response = client.post(
        "/orders/1001/refund",
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 409


def test_cannot_refund_another_merchants_order():
    response = client.post(
        "/orders/1002/refund",
        headers={
            "Authorization": "Bearer token_merchant_a"
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


def test_cancel_paid_order():
    response = client.post(
        "/orders/1007/cancel",
        headers={
            "Authorization": "Bearer token_merchant_a"
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["order"]["status"] == "CANCELLED"


def test_cannot_cancel_shipped_order():
    response = client.post(
        "/orders/1005/cancel",
        headers={
            "Authorization": "Bearer token_merchant_a"
        },
    )

    assert response.status_code == 409


def test_cannot_cancel_another_merchants_order():
    response = client.post(
        "/orders/1002/cancel",
        headers={
            "Authorization": "Bearer token_merchant_a"
        },
    )

    assert response.status_code == 404


def test_refund_requires_authentication():
    response = client.post("/orders/1001/refund")

    assert response.status_code == 401


def test_cancel_requires_authentication():
    response = client.post("/orders/1001/cancel")

    assert response.status_code == 401