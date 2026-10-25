
import re
from typing import Any


EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)"
)

INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|above) instructions",
    r"ignore your instructions",
    r"reveal (all )?(customer|private|personal) information",
    r"ignore all safety rules",
    r"override (your )?(system )?instructions",
    r"refund this order immediately",
]


def redact_pii(text: str) -> str:
    """
    Replace email addresses and phone-like strings with placeholders.
    """
    text = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
    text = PHONE_PATTERN.sub("[REDACTED_PHONE]", text)
    return text


def is_prompt_injection(text: str) -> bool:
    """
    Flag common instruction-like text in untrusted customer content.

    This is a heuristic detector, not a complete prompt-injection solution.
    """
    normalized = text.lower()

    return any(
        re.search(pattern, normalized)
        for pattern in INJECTION_PATTERNS
    )


def sanitize_customer_note(note: str) -> str:
    """
    Never treat customer notes as trusted instructions.

    If a note matches a known injection pattern, replace its content
    with a safe marker rather than passing the original text to a model.
    """
    if is_prompt_injection(note):
        return "[UNTRUSTED CUSTOMER NOTE OMITTED]"

    return redact_pii(note)


def sanitize_order_for_model(order: dict[str, Any]) -> dict[str, Any]:
    """
    Create a sanitized copy of an order for model consumption.

    The original dictionary is not modified.
    """
    safe_order = order.copy()

    if isinstance(safe_order.get("customer_email"), str):
        safe_order["customer_email"] = "[REDACTED_EMAIL]"

    if isinstance(safe_order.get("customer_phone"), str):
        safe_order["customer_phone"] = "[REDACTED_PHONE]"

    if isinstance(safe_order.get("customer_note"), str):
        safe_order["customer_note"] = sanitize_customer_note(
            safe_order["customer_note"]
        )

    return safe_order


def sanitize_tool_result_for_model(
    result: dict[str, Any],
) -> dict[str, Any]:
    """
    Sanitize order data returned by the sub-agent before model processing.
    """
    safe_result = result.copy()
    body = safe_result.get("body")

    if isinstance(body, list):
        safe_result["body"] = [
            sanitize_order_for_model(order)
            if isinstance(order, dict)
            else order
            for order in body
        ]

    elif isinstance(body, dict):
        safe_body = body.copy()

        if isinstance(safe_body.get("order"), dict):
            safe_body["order"] = sanitize_order_for_model(
                safe_body["order"]
            )

        safe_result["body"] = safe_body

    return safe_result
