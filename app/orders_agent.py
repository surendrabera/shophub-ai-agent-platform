
import os
from typing import Any

import httpx
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse

app = FastAPI(
    title="ShopHub Orders Sub-Agent",
    description="JSON-RPC interface for ShopHub order operations",
    version="1.0.0",
)

STORE_API_URL = os.getenv(
    "STORE_API_URL",
    "http://127.0.0.1:8001",
)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/.well-known/agent.json")
async def agent_card():
    """
    Publish metadata that allows the orchestrator to discover this agent.
    """
    return {
        "name": "ShopHub Orders Agent",
        "description": (
            "Handles order listing, order lookup, refund requests, "
            "and cancellation requests."
        ),
        "version": "1.0.0",
        "protocol": "JSON-RPC 2.0",
        "endpoint": "http://127.0.0.1:8002/rpc",
        "skills": [
            {
                "id": "orders.list",
                "name": "List Orders",
                "description": "List orders, optionally filtered by status.",
            },
            {
                "id": "orders.lookup",
                "name": "Look Up Order",
                "description": "Look up an order by its ID.",
            },
            {
                "id": "orders.refund",
                "name": "Refund Order",
                "description": "Request a refund for an eligible order.",
            },
            {
                "id": "orders.cancel",
                "name": "Cancel Order",
                "description": "Request cancellation of an eligible order.",
            },
                        {
                "id": "orders.me",
                "name": "Identify Caller",
                "description": "Identify the authenticated user and merchant.",
            },
        ],
    }


async def call_store_api(
    method: str,
    path: str,
    bearer_token: str,
    params: dict | None = None,
    json_body: dict | None = None,
) -> dict[str, Any]:
    """
    Call the Store API using the caller's original Bearer token.

    We deliberately do not create, replace, or cache credentials.
    """
    headers = {
        "Authorization": bearer_token,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.request(
            method=method,
            url=f"{STORE_API_URL}{path}",
            headers=headers,
            params=params,
            json=json_body,
        )

    # Preserve the Store API's response body, including HTTP error details.
    try:
        body = response.json()
    except ValueError:
        body = {"message": response.text}

    return {
        "http_status": response.status_code,
        "body": body,
    }

async def execute_tool(
    method: str,
    params: dict,
    bearer_token: str,
):
    if method == "orders.me":
        return await call_store_api(
            method="GET",
            path="/auth/me",
            bearer_token=bearer_token,
        )

    if method == "orders.list":
        return await call_store_api(
            method="GET",
            path="/orders",
            bearer_token=bearer_token,
            params=params,
        )

    if method == "orders.lookup":
        return await call_store_api(
            method="GET",
            path="/orders/lookup",
            bearer_token=bearer_token,
            params=params,
        )

    if method == "orders.refund":
        return await call_store_api(
            method="POST",
            path="/orders/refund",
            bearer_token=bearer_token,
            json_body=params,
        )

    if method == "orders.cancel":
        return await call_store_api(
            method="POST",
            path="/orders/cancel",
            bearer_token=bearer_token,
            json_body=params,
        )

    raise ValueError(f"Unsupported tool: {method}")



@app.post("/rpc")
async def json_rpc_endpoint(
    request: dict[str, Any],
    authorization: str | None = Header(default=None),
):
    """
    Handle JSON-RPC 2.0 requests.

    Example request:
    {
        "jsonrpc": "2.0",
        "method": "orders.list",
        "params": {"status": "PAID"},
        "id": 1
    }
    """

    request_id = request.get("id")

    def rpc_error(code: int, message: str, status_code: int = 200):
        return JSONResponse(
            status_code=status_code,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": code,
                    "message": message,
                },
                "id": request_id,
            },
        )

    if request.get("jsonrpc") != "2.0":
        return rpc_error(-32600, "Invalid Request")

    method = request.get("method")
    if not isinstance(method, str) or not method:
        return rpc_error(-32600, "Invalid Request")

    params = request.get("params", {})
    if not isinstance(params, dict):
        return rpc_error(-32602, "Invalid params")

    # JSON-RPC requests need a caller identity. Forward it unchanged.
    if not authorization or not authorization.startswith("Bearer "):
        return rpc_error(
            -32001,
            "Missing or invalid Bearer token",
            status_code=401,
        )

    try:
        result = await execute_tool(
            method=method,
            params=params,
            bearer_token=authorization,
        )

        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": request_id,
        }

    except ValueError as exc:
        return rpc_error(-32602, str(exc))

    except LookupError as exc:
        return rpc_error(-32601, str(exc))

    except httpx.RequestError:
        return rpc_error(
            -32000,
            "Store API is unavailable",
            status_code=502,
        )
