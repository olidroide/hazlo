from __future__ import annotations

from hazlo.domain.source import SourceType
from hazlo.infrastructure.adapters.base import BaseSourceAdapter
from hazlo.infrastructure.adapters.email_adapter import EmailSourceAdapter
from hazlo.infrastructure.adapters.rss_adapter import RssSourceAdapter
from hazlo.infrastructure.adapters.web_adapter import WebSourceAdapter

adapter_registry: dict[str, BaseSourceAdapter] = {
    SourceType.RSS.value: RssSourceAdapter(),
    SourceType.WEB.value: WebSourceAdapter(),
    SourceType.EMAIL.value: EmailSourceAdapter(),
}
