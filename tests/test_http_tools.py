from fastapi.testclient import TestClient

from app import http_tools
from app.store_api import app


client = TestClient(app)


def test_get_order_by_id_success(monkeypatch):
    """An existing order should be returned successfully."""

    def mock_get(url, **kwargs):
        return client.get(
            "/orders/lookup",
            params=kwargs["params"],
            headers=kwargs["headers"],
        )

    monkeypatch.setattr(http_tools.httpx, "get", mock_get)

    result = http_tools.get_order_by_id(1001)

    assert result["success"] is True
    assert result["data"]["id"] == 1001
    assert result["error"] is None


def test_get_order_by_id_not_found(monkeypatch):
    """A missing order must be treated as a failure."""

    def mock_get(url, **kwargs):
        return client.get(
            "/orders/lookup",
            params=kwargs["params"],
            headers=kwargs["headers"],
        )

    monkeypatch.setattr(http_tools.httpx, "get", mock_get)

    result = http_tools.get_order_by_id(9999)

    assert result["success"] is False
    assert result["data"] is None
    assert result["error"] == "Order not found"


def test_get_orders_by_status_success(monkeypatch):
    """Orders can be retrieved by status."""

    def mock_get(url, **kwargs):
        return client.get(
            "/orders",
            params=kwargs["params"],
            headers=kwargs["headers"],
        )

    monkeypatch.setattr(http_tools.httpx, "get", mock_get)

    result = http_tools.get_orders_by_status("PAID")

    assert result["success"] is True
    assert isinstance(result["data"], list)
    assert all(order["status"] == "PAID" for order in result["data"])