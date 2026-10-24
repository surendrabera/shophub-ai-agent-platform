
import pytest

from app.tools import get_order_by_id, get_orders_by_status


def test_get_existing_order():
    order = get_order_by_id(1001)

    assert order is not None
    assert order["customer_name"] == "Maria"
    assert order["status"] == "PAID"


def test_get_missing_order():
    order = get_order_by_id(9999)

    assert order is None


def test_filter_orders_by_status():
    orders = get_orders_by_status("PAID")

    assert len(orders) == 1
    assert orders[0]["id"] == 1001


def test_filter_status_is_case_insensitive():
    orders = get_orders_by_status("paid")

    assert len(orders) == 1
    assert orders[0]["status"] == "PAID"


def test_invalid_order_id():
    with pytest.raises(ValueError):
        get_order_by_id("abc")


def test_invalid_status():
    with pytest.raises(ValueError):
        get_orders_by_status("")
