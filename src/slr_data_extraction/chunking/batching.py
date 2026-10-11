"""Offline full-article batch planning. Character budgets are not token limits."""
BATCHING_VERSION = "1-fixed-message-character-budget"


def message_chars(request):
    return sum(len(message["content"]) for message in request["messages"])


def plan_batches(chunks, request_builder, fields, *, max_message_chars=14000):
    """Greedy document-order packing, shared by all fields and model runs.

    The longest field request controls each boundary. A chunk is never dropped
    or split here. Fail explicitly if a single chunk cannot fit. Freeze the
    returned IDs before comparing models; verify their token budgets separately.
    """
    if max_message_chars <= 0 or not fields:
        raise ValueError("Positive character budget and nonempty fields required")
    if len({c.chunk_id for c in chunks}) != len(chunks):
        raise ValueError("Duplicate chunk IDs")
    batches, current = [], []
    for chunk in chunks:
        candidate = current + [chunk]
        fits = all(message_chars(request_builder(field, candidate)) <= max_message_chars
                   for field in fields)
        if not fits:
            if not current:
                raise ValueError(f"Single chunk exceeds character budget: {chunk.chunk_id}")
            batches.append(current)
            current = [chunk]
            if any(message_chars(request_builder(field, current)) > max_message_chars
                   for field in fields):
                raise ValueError(f"Single chunk exceeds character budget: {chunk.chunk_id}")
        else:
            current = candidate
    if current:
        batches.append(current)
    return batches
