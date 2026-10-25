
import re
from typing import Any, TypedDict
from app.security import sanitize_tool_result_for_model
import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from langgraph.graph import END, START, StateGraph


AGENT_CARD_URL = "http://127.0.0.1:8002/.well-known/agent.json"


class AgentState(TypedDict, total=False):
    query: str
    authorization: str
    method: str
    params: dict[str, Any]
    result: dict[str, Any]
    answer: str
    error: str


class ChatRequest(BaseModel):
    message: str


def fake_llm_router(state: AgentState) -> dict:
    """
    Route requests deterministically without an external LLM.

    Destructive operations are detected before read-only operations.
    """
    query = state["query"]
    normalized = query.lower()

    # 1. Check destructive requests first.
    if re.search(r"\b(refund|cancel|cancellation)\b", normalized):
        return {
            "method": "unsupported_action",
            "params": {},
        }

    # 2. Detect supported order IDs.
    order_match = re.search(
        r"\b(?:order\s*)?(100\d|200\d|9999)\b",
        normalized,
    )

    # 3. Handle requests to look up a specific order.
    if order_match and any(
        word in normalized
        for word in ("lookup", "find", "details", "detail", "status", "order")
    ):
        return {
            "method": "orders.lookup",
            "params": {"id": order_match.group(1)},
        }

    # 4. Handle order listing and status filters.
    statuses = (
        "PLACED",
        "PAID",
        "SHIPPED",
        "DELIVERED",
        "CANCELLED",
        "REFUNDED",
    )

    requested_status = next(
        (status for status in statuses if status.lower() in normalized),
        None,
    )

    if any(word in normalized for word in ("list", "show", "all", "orders")):
        params = {}

        if requested_status:
            params["status"] = requested_status

        return {
            "method": "orders.list",
            "params": params,
        }

    # 5. Don't guess when the request is unclear.
    return {
        "method": "unsupported",
        "params": {},
    }



def route_node(state: AgentState) -> dict:
    """Choose the next operation using the deterministic fake LLM."""
    return fake_llm_router(state)


def call_orders_agent_node(state: AgentState) -> dict:
    """Discover the sub-agent and call its JSON-RPC endpoint."""
    method = state["method"]

    if method == "unsupported_action":
        return {
            "answer": (
                "Refunds and cancellations require an approval workflow. "
                "That workflow will be implemented in a later module."
            )
        }

    if method == "unsupported":
        return {
            "answer": (
                "I can help list orders, filter them by status, "
                "or look up an order by ID."
            )
        }

    # Discover the sub-agent from its agent card instead of importing it.
    with httpx.Client(timeout=10.0) as client:
        card_response = client.get(AGENT_CARD_URL)
        card_response.raise_for_status()
        agent_card = card_response.json()

        endpoint = agent_card.get("endpoint")
        if not endpoint:
            raise ValueError("Orders agent card has no endpoint")

        rpc_request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": state.get("params", {}),
            "id": 1,
        }

        response = client.post(
            endpoint,
            json=rpc_request,
            headers={
                "Authorization": state["authorization"],
            },
        )

        response.raise_for_status()
        rpc_response = response.json()

    if "error" in rpc_response:
        return {
            "error": rpc_response["error"].get(
                "message",
                "Orders agent returned an error",
            )
        }

    result = rpc_response.get("result", {})

    # Sanitize customer information before it can reach an LLM.
    safe_result = sanitize_tool_result_for_model(result)

    return {"result": safe_result}

def format_response_node(state: AgentState) -> dict:
    """Format the tool result as a simple human-readable answer."""
    if state.get("error"):
        return {"answer": f"The order request failed: {state['error']}"}

    result = state.get("result")

    if result is None:
        # A response may already have been produced by the routing node.
        return {}

    http_status = result.get("http_status")
    body = result.get("body")

    if http_status != 200:
        detail = body.get("detail", body) if isinstance(body, dict) else body
        return {
            "answer": f"The Store API returned HTTP {http_status}: {detail}"
        }

    # Legacy lookup returns HTTP 200 even when the order was not found.
    if isinstance(body, dict) and body.get("status") is False:
        return {"answer": "Order not found in your store."}

    if isinstance(body, dict) and "order" in body:
        order = body["order"]
        return {
            "answer": (
                f"Order {order['id']} has status {order['status']} "
                f"and a total of {order['total']:.2f}."
            )
        }

    if isinstance(body, list):
        if not body:
            return {"answer": "No matching orders were found in your store."}

        lines = [
            f"Found {len(body)} order(s):",
        ]

        for order in body:
            lines.append(
                f"- Order {order['id']}: "
                f"{order['status']}, total {order['total']:.2f}"
            )

        return {"answer": "\n".join(lines)}

    return {"answer": "The request completed, but returned an unexpected result."}


def route_after_tool(state: AgentState) -> str:
    """Skip result formatting if the router already produced an answer."""
    if state.get("answer"):
        return END
    return "format_response"


graph_builder = StateGraph(AgentState)

graph_builder.add_node("route", route_node)
graph_builder.add_node("call_orders_agent", call_orders_agent_node)
graph_builder.add_node("format_response", format_response_node)

graph_builder.add_edge(START, "route")
graph_builder.add_edge("route", "call_orders_agent")
graph_builder.add_conditional_edges(
    "call_orders_agent",
    route_after_tool,
    {
        END: END,
        "format_response": "format_response",
    },
)
graph_builder.add_edge("format_response", END)

orchestrator_graph = graph_builder.compile()


app = FastAPI(
    title="ShopHub AI Orchestrator",
    description="LangGraph-based e-commerce support orchestrator",
    version="1.0.0",
)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/chat")
def chat(
    request: ChatRequest,
    authorization: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Bearer token",
        )

    try:
        state = orchestrator_graph.invoke(
            {
                "query": request.message,
                "authorization": authorization,
            }
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Could not reach the Orders Sub-Agent",
        )
    except (ValueError, httpx.HTTPStatusError):
        raise HTTPException(
            status_code=502,
            detail="Could not complete the order request",
        )

    return {"answer": state.get("answer", "No answer was produced.")}
