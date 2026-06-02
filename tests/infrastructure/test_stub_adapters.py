import pytest

from hazlo.infrastructure.adapters.base import AdapterNotImplementedError
from hazlo.infrastructure.adapters.email_adapter import EmailSourceAdapter
from hazlo.infrastructure.adapters.web_adapter import WebSourceAdapter


@pytest.mark.asyncio
async def test_web_adapter_raises_adapter_not_implemented():
    adapter = WebSourceAdapter()
    with pytest.raises(AdapterNotImplementedError, match="Web source connector not implemented"):
        await adapter.fetch(type("Source", (), {"url": "https://example.com"})())


@pytest.mark.asyncio
async def test_web_adapter_returns_empty_without_url():
    adapter = WebSourceAdapter()
    result = await adapter.fetch(type("Source", (), {"url": None})())
    assert result == []


@pytest.mark.asyncio
async def test_email_adapter_raises_adapter_not_implemented():
    adapter = EmailSourceAdapter()
    source = type("Source", (), {"config": {"imap_host": "x", "imap_user": "x", "imap_password": "x"}})()
    with pytest.raises(AdapterNotImplementedError, match="Email source connector not implemented"):
        await adapter.fetch(source)
