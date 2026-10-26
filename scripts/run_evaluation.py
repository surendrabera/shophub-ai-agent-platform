import os
import sys
import uuid

import httpx


BASE_URL = os.getenv(
    "SHOPHUB_BASE_URL",
    "http://127.0.0.1:8004",
)

MERCHANT_A_HEADERS = {
    "Authorization": "Bearer token-merchant-a-demo",
}

MERCHANT_B_HEADERS = {
    "Authorization": "Bearer token-merchant-b-demo",
}


def run_case(name, test_function):
    """Run one evaluation scenario and report its result."""
    try:
        test_function()
        print(f"[PASS] {name}")
        return True
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        return False


def chat(client, message, headers):
    """Send a message to the real orchestrator API."""
    response = client.post(
        "/chat",
        headers=headers,
        json={
            "message": message,
            "conversation_id": f"eval-{uuid.uuid4()}",
        },
    )

    assert response.status_code == 200, (
        f"Expected HTTP 200, received {response.status_code}: "
        f"{response.text}"
    )

    payload = response.json()

    assert "answer" in payload, (
        f"Response has no answer field: {payload}"
    )

    return payload["answer"]


def test_order_status(client):
    answer = chat(
        client,
        "What is the status of order 1002?",
        MERCHANT_A_HEADERS,
    )

    assert "1002" in answer, f"Order ID missing: {answer}"
    assert "SHIPPED" in answer.upper(), (
        f"Expected SHIPPED status: {answer}"
    )


def test_unknown_order(client):
    answer = chat(
        client,
        "Find order 9999",
        MERCHANT_A_HEADERS,
    )

    assert "not found" in answer.lower(), (
        f"Expected a not-found response: {answer}"
    )


def test_foreign_order_is_not_disclosed(client):
    answer = chat(
        client,
        "Find order 2001",
        MERCHANT_A_HEADERS,
    )

    assert "not found" in answer.lower(), (
        f"Expected inaccessible order to be reported as not found: {answer}"
    )

    assert "merchant_b" not in answer.lower(), (
        "Response disclosed another merchant's identity"
    )


def test_refund_requires_approval(client):
    response = client.post(
        "/approvals/propose",
        headers=MERCHANT_A_HEADERS,
        json={"message": "Refund order 1001"},
    )

    assert response.status_code == 200, (
        f"Proposal request failed: {response.status_code}: "
        f"{response.text}"
    )

    payload = response.json()
    proposal = payload.get("proposal")

    assert isinstance(proposal, dict), (
        f"Response does not contain a proposal: {payload}"
    )

    assert proposal.get("order_id") == "1001", proposal
    assert proposal.get("merchant_id") == "merchant_a", proposal
    assert proposal.get("action") == "refund", proposal
    assert proposal.get("status") == "pending", proposal

    assert "proposal_id" in proposal, (
        f"Proposal ID is missing: {proposal}"
    )


def test_rejected_refund(client):
    response = client.post(
        "/approvals/propose",
        headers=MERCHANT_A_HEADERS,
        json={"message": "Refund order 1001"},
    )

    assert response.status_code == 200, (
        f"Proposal creation failed: {response.status_code}: "
        f"{response.text}"
    )

    proposal = response.json().get("proposal", {})
    proposal_id = proposal.get("proposal_id")

    assert proposal_id, f"Proposal ID missing: {proposal}"

    decision_response = client.post(
        f"/approvals/{proposal_id}/decision",
        headers=MERCHANT_A_HEADERS,
        json={"decision": "rejected"},
    )

    assert decision_response.status_code == 200, (
        f"Rejection failed: {decision_response.status_code}: "
        f"{decision_response.text}"
    )

    result = decision_response.json()
    saved_proposal = result.get("proposal", {})

    assert saved_proposal.get("status") == "rejected", result


def main():
    print("ShopHub AI Agent Evaluation")
    print("=" * 32)
    print(f"Target API: {BASE_URL}")
    print()

    try:
        with httpx.Client(
            base_url=BASE_URL,
            timeout=30.0,
        ) as client:
            health = client.get("/health")
            health.raise_for_status()
    except Exception as exc:
        print(f"[ERROR] Could not reach the orchestrator: {exc}")
        print(
            "Start the application with Docker Compose or set "
            "SHOPHUB_BASE_URL to the running orchestrator URL."
        )
        return 2

    cases = [
        ("Order status lookup", test_order_status),
        ("Unknown order handling", test_unknown_order),
        ("Cross-merchant access denied", test_foreign_order_is_not_disclosed),
        ("Refund requires approval", test_refund_requires_approval),
        ("Rejected refund is recorded", test_rejected_refund),
    ]

    passed = 0
    failed = 0

    with httpx.Client(
        base_url=BASE_URL,
        timeout=30.0,
    ) as client:
        for name, test_function in cases:
            if run_case(name, lambda fn=test_function: fn(client)):
                passed += 1
            else:
                failed += 1

    print()
    print("=" * 32)
    print(f"Total:  {passed + failed}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed:
        print("Overall result: FAIL")
        return 1

    print("Overall result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
