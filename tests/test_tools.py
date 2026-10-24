
import pytest

from app.tools import get_order_by_id, get_orders_by_status


def test_get_existing_order():
    result = get_order_by_id(1001)

    assert result["success"] is True
    assert result["data"]["customer_name"] == "Maria"
    assert result["data"]["status"] == "PAID"
    assert result["error"] is None


def test_get_missing_order():
    result = get_order_by_id(9999)

    assert result["success"] is False
    assert result["data"] is None
    assert result["error"] == "Order not found"


def test_invalid_order_id():
    result = get_order_by_id("abc")

    assert result["success"] is False
    assert result["error"] == "Order ID must be an integer"


def test_boolean_is_not_a_valid_order_id():
    result = get_order_by_id(True)

    assert result["success"] is False
    assert result["error"] == "Order ID must be an integer"


def test_filter_orders_by_status():
    result = get_orders_by_status("PAID")

    assert result["success"] is True
    assert len(result["data"]) == 1
    assert result["data"][0]["id"] == 1001


def test_filter_status_is_case_insensitive():
    result = get_orders_by_status(" paid ")

    assert result["success"] is True
    assert result["data"][0]["status"] == "PAID"


def test_filter_status_with_no_matches():
    result = get_orders_by_status("DELIVERED")

    assert result["success"] is True
    assert result["data"] == []


def test_invalid_status():
    result = get_orders_by_status("")

    assert result["success"] is False
    assert result["data"] is None
    assert result["error"] == "Status must be a non-empty string"
