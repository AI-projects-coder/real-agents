def classify(ticket: dict) -> tuple[str, str]:
    """Rule-based for now. In Module 5 this becomes an LLM call."""
    text = f"{ticket.get('subject', '')} {ticket.get('body', '')}".lower()
    if "refund" in text:
        return "refund", "high"
    if "cancel" in text:
        return "cancellation", "high"
    if "address" in text:
        return "address_change", "medium"
    return "order_status", "low"
