import uuid

import pytest

from hazlo.domain.source import Source, SourceType
from hazlo.infrastructure.adapters.base import AdapterNotImplementedError
from hazlo.infrastructure.adapters.email_adapter import EmailSourceAdapter
from hazlo.infrastructure.adapters.web_adapter import WebSourceAdapter


@pytest.mark.asyncio
async def test_web_adapter_raises_adapter_not_implemented():
    adapter = WebSourceAdapter()
    source = Source(id=uuid.uuid4(), name="test", source_type=SourceType.WEB, url="https://example.com")
    with pytest.raises(AdapterNotImplementedError, match="Web source connector not implemented"):
        await adapter.fetch(source)


@pytest.mark.asyncio
async def test_web_adapter_returns_empty_without_url():
    adapter = WebSourceAdapter()
    source = Source(id=uuid.uuid4(), name="test", source_type=SourceType.WEB, url=None)
    result = await adapter.fetch(source)
    assert result == []


@pytest.mark.asyncio
async def test_email_adapter_raises_adapter_not_implemented():
    adapter = EmailSourceAdapter()
    source = Source(
        id=uuid.uuid4(),
        name="test",
        source_type=SourceType.EMAIL,
        config={"imap_host": "x", "imap_user": "x", "imap_password": "x"},
    )
    with pytest.raises(AdapterNotImplementedError, match="Email source connector not implemented"):
        await adapter.fetch(source)
