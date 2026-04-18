from typing import Any


def sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop empty text blocks from messages.

    The Anthropic API rejects requests where a text block has cache_control set
    but an empty text value. Empty text blocks carry no content, so dropping
    them entirely is safe.
    """
    sanitized = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            new_content = [
                block
                for block in content
                if not (
                    isinstance(block, dict)
                    and block.get("type") == "text"
                    and not block.get("text")
                )
            ]
            sanitized.append({**message, "content": new_content})
        else:
            sanitized.append(message)
    return sanitized
