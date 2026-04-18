from src.utils.message_utils import sanitize_messages


def test_removes_empty_text_block_with_cache_control():
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "", "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": "Hello"},
            ],
        }
    ]
    result = sanitize_messages(messages)
    assert result[0]["content"] == [{"type": "text", "text": "Hello"}]


def test_removes_empty_text_block_without_cache_control():
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": ""},
                {"type": "text", "text": "World"},
            ],
        }
    ]
    result = sanitize_messages(messages)
    assert result[0]["content"] == [{"type": "text", "text": "World"}]


def test_preserves_non_empty_blocks_with_cache_control():
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "System prompt",
                    "cache_control": {"type": "ephemeral"},
                },
            ],
        }
    ]
    result = sanitize_messages(messages)
    assert result == messages


def test_string_content_unchanged():
    messages = [{"role": "user", "content": "Plain string content"}]
    result = sanitize_messages(messages)
    assert result == messages


def test_empty_list_unchanged():
    messages = [{"role": "user", "content": []}]
    result = sanitize_messages(messages)
    assert result == messages
