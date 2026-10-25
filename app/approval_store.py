
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
    """Create a connection to the SQLite database."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    """Create the proposals table if necessary."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_proposals (
                proposal_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                merchant_id TEXT NOT NULL,
                action TEXT NOT NULL
                    CHECK(action IN ('refund', 'cancel')),
                amount REAL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN (
                        'pending', 'approved', 'rejected', 'executed'
                    )),
                created_at TEXT NOT NULL,
                decided_at TEXT
            )
            """
        )


def create_proposal(
    order_id: str,
    merchant_id: str,
    action: str,
    amount: float | None = None,
) -> dict[str, Any]:
    """Save a proposal without executing the action."""
    if action not in {"refund", "cancel"}:
        raise ValueError("Action must be 'refund' or 'cancel'.")

    proposal_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO approval_proposals (
                proposal_id, order_id, merchant_id,
                action, amount, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
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

    return get_proposal(proposal_id)


def get_proposal(proposal_id: str) -> dict[str, Any] | None:
    """Retrieve a proposal by ID."""
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


def decide_proposal(
    proposal_id: str,
    merchant_id: str,
    decision: str,
) -> dict[str, Any] | None:
    """Approve or reject a pending proposal for its own merchant."""
    if decision not in {"approved", "rejected"}:
        raise ValueError("Decision must be 'approved' or 'rejected'.")

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
