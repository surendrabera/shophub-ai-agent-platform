
import pytest

from app import approval_store


@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    """Give every test its own temporary SQLite database."""
    monkeypatch.setattr(
        approval_store,
        "DATABASE_PATH",
        tmp_path / "approvals.db",
    )
    approval_store.initialize_database()


def test_create_proposal_starts_pending(isolated_database):
    proposal = approval_store.create_proposal(
        order_id="1001",
        merchant_id="merchant_a",
        action="refund",
        amount=2499.0,
    )

    assert proposal["proposal_id"]
    assert proposal["order_id"] == "1001"
    assert proposal["merchant_id"] == "merchant_a"
    assert proposal["action"] == "refund"
    assert proposal["amount"] == 2499.0
    assert proposal["status"] == "pending"


def test_approve_pending_proposal(isolated_database):
    proposal = approval_store.create_proposal(
        order_id="1001",
        merchant_id="merchant_a",
        action="refund",
        amount=2499.0,
    )

    result = approval_store.decide_proposal(
        proposal["proposal_id"],
        "merchant_a",
        "approved",
    )

    assert result is not None
    assert result["status"] == "approved"
    assert result["decided_at"] is not None


def test_reject_pending_proposal(isolated_database):
    proposal = approval_store.create_proposal(
        order_id="1002",
        merchant_id="merchant_a",
        action="cancel",
    )

    result = approval_store.decide_proposal(
        proposal["proposal_id"],
        "merchant_a",
        "rejected",
    )

    assert result is not None
    assert result["status"] == "rejected"


def test_other_merchant_cannot_decide_proposal(isolated_database):
    proposal = approval_store.create_proposal(
        order_id="1001",
        merchant_id="merchant_a",
        action="refund",
        amount=2499.0,
    )

    result = approval_store.decide_proposal(
        proposal["proposal_id"],
        "merchant_b",
        "approved",
    )

    assert result is None

    unchanged = approval_store.get_proposal(
        proposal["proposal_id"]
    )
    assert unchanged["status"] == "pending"


def test_proposal_cannot_be_decided_twice(isolated_database):
    proposal = approval_store.create_proposal(
        order_id="1001",
        merchant_id="merchant_a",
        action="refund",
        amount=2499.0,
    )

    first = approval_store.decide_proposal(
        proposal["proposal_id"],
        "merchant_a",
        "approved",
    )

    second = approval_store.decide_proposal(
        proposal["proposal_id"],
        "merchant_a",
        "rejected",
    )

    assert first["status"] == "approved"
    assert second is None


def test_invalid_action_is_rejected(isolated_database):
    with pytest.raises(ValueError):
        approval_store.create_proposal(
            order_id="1001",
            merchant_id="merchant_a",
            action="delete",
        )
