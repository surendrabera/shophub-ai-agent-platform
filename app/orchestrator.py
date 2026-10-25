
import re
from typing import Any, TypedDict
from app.security import sanitize_tool_result_for_model
import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from fastapi import Body
from app import approval_store
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
class ApprovalDecisionRequest(BaseModel):
    decision: str

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
@app.post("/approvals/propose")
def propose_order_action(
    request: ChatRequest,
    authorization: str | None = Header(default=None),
):
    """Create a refund or cancellation proposal without executing it."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Bearer token",
        )

    action_match = re.search(
        r"\b(refund|cancel|cancellation)\b",
        request.message.lower(),
    )

    if not action_match:
        raise HTTPException(
            status_code=400,
            detail="Please specify a refund or cancellation request.",
        )

    action = action_match.group(1)
    action = "cancel" if action in {"cancel", "cancellation"} else "refund"

    order_match = re.search(
        r"\b(?:order\s*)?(100\d|200\d|9999)\b",
        request.message.lower(),
    )

    if not order_match:
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid order ID.",
        )

    order_id = order_match.group(1)

    result = call_orders_rpc(
        "orders.lookup",
        {"id": order_id},
        authorization,
    )

    if result.get("http_status") != 200:
        raise HTTPException(
            status_code=404,
            detail="Order could not be retrieved.",
        )

    body = result.get("body", {})

    if not isinstance(body, dict) or body.get("status") is not True:
        raise HTTPException(
            status_code=404,
            detail="Order not found in your store.",
        )

    order = body["order"]
    status = order.get("status")

    if action == "refund" and status != "PAID":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot propose a refund for an order with status {status}.",
        )

    if action == "cancel" and status not in {"PLACED", "PAID"}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot propose cancellation for an order with status {status}.",
        )

    proposal = approval_store.create_proposal(
        order_id=order_id,
        merchant_id=order["merchant"],
        action=action,
        amount=order["total"] if action == "refund" else None,
    )

    return {
        "message": "Approval required. No order action has been executed.",
        "proposal": proposal,
        "order": {
            "id": order["id"],
            "merchant": order["merchant"],
            "status": order["status"],
            "amount": order["total"] if action == "refund" else None,
        },
    }

@app.post("/approvals/propose")
def propose_order_action(
    request: ChatRequest,
    authorization: str | None = Header(default=None),
):
    """Create a refund or cancellation proposal without executing it."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Bearer token",
        )

    action_match = re.search(
        r"\b(refund|cancel|cancellation)\b",
        request.message.lower(),
    )

    if not action_match:
        raise HTTPException(
            status_code=400,
            detail="Please specify a refund or cancellation request.",
        )

    action = action_match.group(1)
    action = "cancel" if action in {"cancel", "cancellation"} else "refund"

    order_match = re.search(
        r"\b(?:order\s*)?(100\d|200\d|9999)\b",
        request.message.lower(),
    )

    if not order_match:
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid order ID.",
        )

    order_id = order_match.group(1)

    result = call_orders_rpc(
        "orders.lookup",
        {"id": order_id},
        authorization,
    )

    if result.get("http_status") != 200:
        raise HTTPException(
            status_code=404,
            detail="Order could not be retrieved.",
        )

    body = result.get("body", {})

    if not isinstance(body, dict) or body.get("status") is not True:
        raise HTTPException(
            status_code=404,
            detail="Order not found in your store.",
        )

    order = body["order"]
    status = order.get("status")

    if action == "refund" and status != "PAID":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot propose a refund for an order with status {status}.",
        )

    if action == "cancel" and status not in {"PLACED", "PAID"}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot propose cancellation for an order with status {status}.",
        )

    proposal = approval_store.create_proposal(
        order_id=order_id,
        merchant_id=order["merchant"],
        action=action,
        amount=order["total"] if action == "refund" else None,
    )

    return {
        "message": "Approval required. No order action has been executed.",
        "proposal": proposal,
        "order": {
            "id": order["id"],
            "merchant": order["merchant"],
            "status": order["status"],
            "amount": order["total"] if action == "refund" else None,
        },
    }

@app.post("/approvals/{proposal_id}/decision")
def decide_order_action(
    proposal_id: str,
    request: ApprovalDecisionRequest,
    authorization: str | None = Header(default=None),
):
    """Approve or reject a proposal for the authenticated merchant."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Bearer token",
        )

    decision = request.decision.lower()

    if decision not in {"approved", "rejected"}:
        raise HTTPException(
            status_code=422,
            detail="Decision must be 'approved' or 'rejected'.",
        )

    # Identify the caller using the Store API, not a client-supplied merchant ID.
    identity_result = call_orders_rpc(
        "orders.me",
        {},
        authorization,
    )

    identity_body = identity_result.get("body", {})

    if identity_result.get("http_status") != 200:
        raise HTTPException(
            status_code=403,
            detail="Could not verify the caller's merchant.",
        )

    merchant_id = identity_body.get("merchant")

    if not merchant_id:
        raise HTTPException(
            status_code=403,
            detail="Caller is not associated with a merchant.",
        )

    proposal = approval_store.get_proposal(proposal_id)

    if proposal is None or proposal["merchant_id"] != merchant_id:
        # Do not disclose whether another merchant owns this proposal.
        raise HTTPException(
            status_code=404,
            detail="Approval proposal not found.",
        )

    decided = approval_store.decide_proposal(
        proposal_id=proposal_id,
        merchant_id=merchant_id,
        decision=decision,
    )

    if decided is None:
        raise HTTPException(
            status_code=409,
            detail="Proposal is no longer pending or has already been decided.",
        )

    if decision == "rejected":
        return {
            "message": "Proposal rejected. No order action was executed.",
            "proposal": decided,
        }

    # Re-fetch the order before executing the approved action.
    lookup_result = call_orders_rpc(
        "orders.lookup",
        {"id": proposal["order_id"]},
        authorization,
    )

    lookup_body = lookup_result.get("body", {})

    if (
        lookup_result.get("http_status") != 200
        or not isinstance(lookup_body, dict)
        or lookup_body.get("status") is not True
    ):
        raise HTTPException(
            status_code=409,
            detail="Order is no longer accessible. Action was not executed.",
        )

    current_order = lookup_body["order"]

    if current_order.get("merchant") != merchant_id:
        raise HTTPException(
            status_code=403,
            detail="Merchant ownership verification failed.",
        )

    # Verify the proposal still matches the order's current state.
    if proposal["action"] == "refund":
        if (
            current_order.get("status") != "PAID"
            or current_order.get("total") != proposal["amount"]
        ):
            raise HTTPException(
                status_code=409,
                detail="Order details changed. A new proposal is required.",
            )
        rpc_method = "orders.refund"

    else:
        if current_order.get("status") not in {"PLACED", "PAID"}:
            raise HTTPException(
                status_code=409,
                detail="Order can no longer be cancelled.",
            )
        rpc_method = "orders.cancel"

    execution_result = call_orders_rpc(
        rpc_method,
        {"id": proposal["order_id"]},
        authorization,
    )

    if execution_result.get("http_status") != 200:
        raise HTTPException(
            status_code=502,
            detail=(
                "The action could not be confirmed by the Store API. "
                "Check the order status before retrying."
            ),
        )

    execution_body = execution_result.get("body", {})

    if not isinstance(execution_body, dict) or execution_body.get("success") is not True:
        raise HTTPException(
            status_code=409,
            detail="The Store API did not confirm that the action succeeded.",
        )

    approval_store.mark_proposal_executed(proposal_id)

    return {
        "message": "Approved action executed successfully.",
        "proposal": approval_store.get_proposal(proposal_id),
        "result": execution_body,
    }