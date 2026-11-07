"""Separate explicit model reasoning from the final JSON without repairing output."""

def separate_content(message, thinking):
    content = message.get('content') or ''
    reasoning = message.get('reasoning_content') or message.get('reasoning') or ''
    if '</think>' in content:
        if content.count('</think>') != 1:
            raise ValueError('Ambiguous reasoning boundary')
        prefix, content = content.split('</think>', 1)
        reasoning = prefix.removeprefix('<think>').strip()
    elif '<think>' in content:
        raise ValueError('Unfinished reasoning block')
    if thinking and not reasoning.strip():
        raise ValueError('Thinking requested but no reasoning captured')
    return reasoning, content.strip()

