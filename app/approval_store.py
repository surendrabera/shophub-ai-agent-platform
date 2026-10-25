import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATABASE_PATH = Path(
    os.getenv("APPROVAL_DB_PATH", "data/approvals.db")
)


def get_connection() -> sqlite3.Connection:
    """Create a SQLite connection and ensure the database directory exists."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    """Create the approval proposals table if it does not exist."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_proposals (
                proposal_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                merchant_id TEXT NOT NULL,
                action TEXT NOT NULL
                    CHECK (action IN ('refund', 'cancel')),
                amount REAL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (
                        status IN (
                            'pending',
                            'approved',
                            'rejected',
                            'executed'
                        )
                    ),
                created_at TEXT NOT NULL,
                decided_at TEXT
            )
            """
        )


def get_proposal(proposal_id: str) -> dict[str, Any] | None:
    """Retrieve a proposal by ID."""
    initialize_database()

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM approval_proposals
            WHERE proposal_id = ?
            """,
            (proposal_id,),
        ).fetchone()

    return dict(row) if row else None


def create_proposal(
    order_id: str,
    merchant_id: str,
    action: str,
    amount: float | None = None,
) -> dict[str, Any]:
    """Create a pending proposal without executing the order action."""
    if action not in {"refund", "cancel"}:
        raise ValueError("Action must be 'refund' or 'cancel'.")

    if not order_id or not merchant_id:
        raise ValueError("Order ID and merchant ID are required.")

    if action == "refund" and amount is None:
        raise ValueError("A refund proposal must include an amount.")

    initialize_database()

    proposal_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO approval_proposals (
                proposal_id,
                order_id,
                merchant_id,
                action,
                amount,
                status,
                created_at,
                decided_at
            )
            VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL)
            """,
            (
                proposal_id,
                order_id,
                merchant_id,
                action,
                amount,
                created_at,
            ),
        )

    proposal = get_proposal(proposal_id)

    if proposal is None:
        raise RuntimeError("Failed to retrieve the created proposal.")

    return proposal


def decide_proposal(
    proposal_id: str,
    merchant_id: str,
    decision: str,
) -> dict[str, Any] | None:
    """
    Approve or reject a pending proposal belonging to the specified merchant.

    A proposal can be decided only once.
    """
    if decision not in {"approved", "rejected"}:
        raise ValueError("Decision must be 'approved' or 'rejected'.")

    initialize_database()

    decided_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE approval_proposals
            SET status = ?, decided_at = ?
            WHERE proposal_id = ?
              AND merchant_id = ?
              AND status = 'pending'
            """,
            (
                decision,
                decided_at,
                proposal_id,
                merchant_id,
            ),
        )

        if cursor.rowcount != 1:
            return None

    return get_proposal(proposal_id)


def mark_proposal_executed(proposal_id: str) -> bool:
    """Mark an approved proposal as executed exactly once."""
    initialize_database()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE approval_proposals
            SET status = 'executed'
            WHERE proposal_id = ?
              AND status = 'approved'
            """,
            (proposal_id,),
        )

    return cursor.rowcount == 1


# Initialize the database when this module is imported.
initialize_database()