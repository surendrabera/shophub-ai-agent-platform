import os

import httpx


STORE_API_URL = os.getenv(
    "STORE_API_URL",
    "http://127.0.0.1:8001",
)


def get_order_by_id(
    order_id: int,
    authorization: str,
) -> dict:
    """Retrieve an order using the caller's bearer token."""

    try:
        response = httpx.get(
            f"{STORE_API_URL}/orders/lookup",
            params={"id": order_id},
            headers={"Authorization": authorization},
            timeout=5.0,
        )

        response.raise_for_status()
        payload = response.json()

        # The legacy API can return HTTP 200 for missing orders.
        if payload.get("status") is False:
            return {
                "success": False,
                "data": None,
                "error": payload.get("message", "Order not found"),
            }

        return {
            "success": True,
            "data": payload,
            "error": None,
        }

    except httpx.HTTPStatusError as exc:
        return {
            "success": False,
            "data": None,
            "error": f"Store API returned HTTP {exc.response.status_code}",
        }

    except httpx.RequestError:
        return {
            "success": False,
            "data": None,
            "error": "Could not connect to the Store API",
        }


def get_orders_by_status(
    status: str,
    authorization: str,
) -> dict:
    """Retrieve orders by status using the caller's bearer token."""

    try:
        response = httpx.get(
            f"{STORE_API_URL}/orders",
            params={"status": status},
            headers={"Authorization": authorization},
            timeout=5.0,
        )

        response.raise_for_status()

        return {
            "success": True,
            "data": response.json(),
            "error": None,
        }

    except httpx.HTTPStatusError as exc:
        return {
            "success": False,
            "data": None,
            "error": f"Store API returned HTTP {exc.response.status_code}",
        }

    except httpx.RequestError:
        return {
            "success": False,
            "data": None,
            "error": "Could not connect to the Store API",
        }