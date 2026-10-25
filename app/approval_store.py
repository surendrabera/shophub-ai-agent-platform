def mark_proposal_executed(proposal_id: str) -> bool:
    """Mark an approved proposal as executed exactly once."""
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