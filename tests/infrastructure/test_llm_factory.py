from __future__ import annotations

from hazlo.infrastructure.llm.factory import _supports_tool_calling


def test_supports_tool_calling() -> None:
    """Test tool calling detection for known models.

    Ensures compound-mini is correctly identified as not supporting tool calling,
    so it won't be placed in the primary slot for agents requiring structured output.
    """
    # Models that support tool calling
    assert _supports_tool_calling("groq", "llama-3.1-8b-instant")
    assert _supports_tool_calling("gemini", "gemini-2.0-flash-lite")
    assert _supports_tool_calling("openrouter", "baiduopenrouter")

    # Models that do NOT support tool calling (will be moved to end of fallback chain)
    assert not _supports_tool_calling("groq", "groq/compound-mini")
