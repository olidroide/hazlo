from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from hazlo.application.services import DedupService, EnrichmentService, QualityClassifier, ReviewEngine
from hazlo.application.services.quality_classifier import ClassificationResult
from hazlo.application.use_cases.ingest_source import IngestSource
from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo
from hazlo.domain.source import Source, SourceType
from hazlo.infrastructure.adapters.base import BaseSourceAdapter
from hazlo.infrastructure.llm import LLMClient
from hazlo.infrastructure.llm.providers.base import LLMProvider, LLMResponse

# ---------------------------------------------------------------------------
# Mock LLM provider
# ---------------------------------------------------------------------------


class MockLLMProvider(LLMProvider):
    def __init__(
        self,
        response_content: str = '{"is_children_activity": true, "is_toddler_friendly": true, "confidence": 0.95}',
        fail: bool = False,
    ) -> None:
        self._response_content = response_content
        self._fail = fail
        self.call_count = 0
        self.last_system_prompt: str | None = None
        self.last_user_content: str | None = None

    async def generate(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.0,
        max_tokens: int = 500,
    ) -> LLMResponse:
        self.call_count += 1
        self.last_system_prompt = system_prompt
        self.last_user_content = user_content
        if self._fail:
            msg = "Mock provider failure"
            raise ConnectionError(msg)
        return LLMResponse(
            content=self._response_content,
            tokens_in=50,
            tokens_out=30,
            model="mock-model",
            latency_ms=10,
        )

    async def test_connection(self) -> bool:
        return not self._fail

    @classmethod
    async def list_models(cls, api_key: str) -> list:
        return []


# ---------------------------------------------------------------------------
# Fake adapter (reuse pattern from existing tests)
# ---------------------------------------------------------------------------


class FakeAdapter(BaseSourceAdapter):
    def __init__(self, raw_events: list[dict] | None = None) -> None:
        self._raw_events = raw_events or []

    async def fetch(self, source: Source) -> list[dict]:
        return list(self._raw_events)

    async def normalize(self, raw: dict) -> Event:
        return Event(
            id=uuid.uuid4(),
            title=raw.get("title", ""),
            location=Location(address=raw.get("address", ""), neighborhood=""),
            start_at=datetime(2026, 6, 1, 20, 0, tzinfo=UTC),
            end_at=datetime(2026, 6, 1, 22, 0, tzinfo=UTC),
            price=Price(amount_cents=1000, is_free=False),
            ticket_info=TicketInfo(url=raw.get("ticket_url")),
            source_url=raw.get("source_url", ""),
            extracted_at=datetime.now(UTC),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_source() -> Source:
    return Source(name="Test", source_type=SourceType.RSS, url="https://example.com")


def _make_raw_event(url: str = "https://example.com/1") -> dict:
    return {
        "title": "Taller infantil de pintura",
        "address": "Calle Mayor 1",
        "ticket_url": "https://tickets.example.com",
        "source_url": url,
    }


def _make_use_case(
    adapter: BaseSourceAdapter,
    classifier: QualityClassifier | None = None,
    review_engine: ReviewEngine | None = None,
) -> IngestSource:
    return IngestSource(
        adapter_registry={"rss": adapter},
        enrichment_service=EnrichmentService(),
        dedup_service=DedupService(),
        quality_classifier=classifier,
        review_engine=review_engine,
    )


# ---------------------------------------------------------------------------
# QualityClassifier — mock LLMClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classifier_wires_and_returns_result() -> None:
    provider = MockLLMProvider()
    client = LLMClient([(provider, "mock")])
    classifier = QualityClassifier(client)

    event = Event(
        title="Taller infantil de pintura",
        location=Location(address="Calle Mayor 1", neighborhood="Centro"),
        start_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
        price=Price(is_free=True),
        ticket_info=TicketInfo(notes="Gratis"),
        source_url="https://example.com/1",
    )

    result = await classifier.execute(event)

    assert isinstance(result, ClassificationResult)
    assert result.is_children_activity is True
    assert result.is_toddler_friendly is True
    assert result.confidence == 0.95
    assert provider.call_count == 1


@pytest.mark.asyncio
async def test_classifier_sends_correct_prompt() -> None:
    provider = MockLLMProvider()
    client = LLMClient([(provider, "mock")])
    classifier = QualityClassifier(client)

    from hazlo.infrastructure.llm.prompts import QUALITY_CLASSIFIER_V1

    event = Event(
        title="Concierto rock",
        location=Location(address="Sala Rock", neighborhood="Malasaña"),
        start_at=datetime(2026, 7, 15, 21, 0, tzinfo=UTC),
        price=Price(amount_cents=2500, is_free=False),
        source_url="https://example.com/2",
    )

    await classifier.execute(event)

    assert provider.last_system_prompt == QUALITY_CLASSIFIER_V1
    assert "Concierto rock" in (provider.last_user_content or "")
    assert "Sala Rock" in (provider.last_user_content or "")


@pytest.mark.asyncio
async def test_classifier_handles_invalid_json() -> None:
    provider = MockLLMProvider(response_content="not json at all")
    client = LLMClient([(provider, "mock")])
    classifier = QualityClassifier(client)

    event = Event(title="Test", source_url="https://example.com/1")

    result = await classifier.execute(event)

    assert result.is_children_activity is False
    assert result.is_toddler_friendly is False
    assert result.confidence == 0.0
    assert result.raw_response == "not json at all"


@pytest.mark.asyncio
async def test_classifier_handles_partial_json() -> None:
    provider = MockLLMProvider(response_content='{"is_children_activity": true}')
    client = LLMClient([(provider, "mock")])
    classifier = QualityClassifier(client)

    event = Event(title="Test", source_url="https://example.com/1")

    result = await classifier.execute(event)

    assert result.is_children_activity is True
    assert result.is_toddler_friendly is False
    assert result.confidence == 0.5


# ---------------------------------------------------------------------------
# LLMClient — provider routing and fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_client_uses_first_provider() -> None:
    primary = MockLLMProvider(
        response_content='{"is_children_activity": true, "is_toddler_friendly": false, "confidence": 0.8}',
    )
    secondary = MockLLMProvider(
        response_content='{"is_children_activity": false, "is_toddler_friendly": true, "confidence": 0.9}',
    )
    client = LLMClient([(primary, "primary"), (secondary, "secondary")])

    response = await client.generate(system_prompt="sys", user_content="user", action="classify")

    assert response.content == '{"is_children_activity": true, "is_toddler_friendly": false, "confidence": 0.8}'
    assert primary.call_count == 1
    assert secondary.call_count == 0


@pytest.mark.asyncio
async def test_llm_client_falls_back_on_failure() -> None:
    primary = MockLLMProvider(fail=True)
    secondary = MockLLMProvider(
        response_content='{"is_children_activity": false, "is_toddler_friendly": true, "confidence": 0.7}',
    )
    client = LLMClient([(primary, "primary"), (secondary, "secondary")])

    response = await client.generate(system_prompt="sys", user_content="user", action="classify")

    assert "is_toddler_friendly" in response.content
    assert primary.call_count == 1
    assert secondary.call_count == 1


@pytest.mark.asyncio
async def test_llm_client_tracks_call_history() -> None:
    provider = MockLLMProvider()
    client = LLMClient([(provider, "mock")])

    await client.generate(system_prompt="sys", user_content="user1", action="classify")
    await client.generate(system_prompt="sys", user_content="user2", action="classify")

    assert len(client.call_history) == 2
    assert client.call_history[0].provider == "mock"
    assert client.call_history[0].action == "classify"
    assert client.call_history[0].tokens_in == 50


@pytest.mark.asyncio
async def test_llm_client_all_providers_fail() -> None:
    provider = MockLLMProvider(fail=True)
    client = LLMClient([(provider, "mock")])

    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        await client.generate(system_prompt="sys", user_content="user", action="classify")

    assert len(client.call_history) == 1
    assert client.call_history[0].error is not None


# ---------------------------------------------------------------------------
# IngestSource — flow wiring with classifier + review engine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow_with_classifier_and_review_auto_approves_high_confidence() -> None:
    provider = MockLLMProvider(
        response_content='{"is_children_activity": true, "is_toddler_friendly": true, "confidence": 0.96}'
    )
    client = LLMClient([(provider, "mock")])
    classifier = QualityClassifier(client)
    review_engine = ReviewEngine(auto_approve_threshold=0.95)

    adapter = FakeAdapter(raw_events=[_make_raw_event()])
    use_case = _make_use_case(adapter, classifier=classifier, review_engine=review_engine)

    result = await use_case.execute(source=_make_source(), existing_urls=set())

    assert result.events_found == 1
    assert result.events_auto_approved == 1
    assert result.events_flagged == 0
    assert len(result.events_to_save) == 1

    event = result.events_to_save[0]
    assert event.status == EventStatus.APPROVED
    assert event.is_children_activity is True
    assert event.is_toddler_friendly is True
    assert event.confidence_score == 0.96
    assert event.agent_review is not None
    assert "raw_response" in event.agent_review


@pytest.mark.asyncio
async def test_flow_with_classifier_flags_low_confidence() -> None:
    provider = MockLLMProvider(
        response_content='{"is_children_activity": false, "is_toddler_friendly": false, "confidence": 0.50}'
    )
    client = LLMClient([(provider, "mock")])
    classifier = QualityClassifier(client)
    review_engine = ReviewEngine(auto_approve_threshold=0.95)

    adapter = FakeAdapter(raw_events=[_make_raw_event()])
    use_case = _make_use_case(adapter, classifier=classifier, review_engine=review_engine)

    result = await use_case.execute(source=_make_source(), existing_urls=set())

    assert result.events_flagged == 1
    assert result.events_auto_approved == 0

    event = result.events_to_save[0]
    assert event.status == EventStatus.PENDING
    assert event.confidence_score == 0.50
    assert event.agent_review is not None
    assert "review_reason" in event.agent_review


@pytest.mark.asyncio
async def test_flow_without_classifier_keeps_events_pending() -> None:
    adapter = FakeAdapter(raw_events=[_make_raw_event()])
    use_case = _make_use_case(adapter, classifier=None, review_engine=None)

    result = await use_case.execute(source=_make_source(), existing_urls=set())

    assert result.events_found == 1
    assert result.events_flagged == 1
    assert result.events_auto_approved == 0

    event = result.events_to_save[0]
    assert event.status == EventStatus.PENDING
    assert event.confidence_score is None
    assert event.is_children_activity is False


@pytest.mark.asyncio
async def test_flow_with_review_engine_only_no_classifier() -> None:
    """ReviewEngine without classifier → no confidence score → stays pending."""
    review_engine = ReviewEngine(auto_approve_threshold=0.95)
    adapter = FakeAdapter(raw_events=[_make_raw_event()])
    use_case = _make_use_case(adapter, classifier=None, review_engine=review_engine)

    result = await use_case.execute(source=_make_source(), existing_urls=set())

    assert result.events_flagged == 1
    event = result.events_to_save[0]
    assert event.status == EventStatus.PENDING
    assert event.confidence_score is None
    assert event.agent_review is not None
    assert "review_reason" in event.agent_review
    assert "No confidence score" in event.agent_review["review_reason"]


@pytest.mark.asyncio
async def test_flow_classifier_invokes_llm_once_per_event() -> None:
    provider = MockLLMProvider()
    client = LLMClient([(provider, "mock")])
    classifier = QualityClassifier(client)
    review_engine = ReviewEngine(auto_approve_threshold=0.95)

    events = [_make_raw_event(f"https://example.com/{i}") for i in range(3)]
    adapter = FakeAdapter(raw_events=events)
    use_case = _make_use_case(adapter, classifier=classifier, review_engine=review_engine)

    await use_case.execute(source=_make_source(), existing_urls=set())

    assert provider.call_count == 3


@pytest.mark.asyncio
async def test_flow_with_classifier_and_failing_llm() -> None:
    """LLM provider fails → classifier error caught → event still processed without classification."""
    provider = MockLLMProvider(fail=True)
    client = LLMClient([(provider, "mock")])
    classifier = QualityClassifier(client)
    review_engine = ReviewEngine(auto_approve_threshold=0.95)

    adapter = FakeAdapter(raw_events=[_make_raw_event()])
    use_case = _make_use_case(adapter, classifier=classifier, review_engine=review_engine)

    result = await use_case.execute(source=_make_source(), existing_urls=set())

    assert result.events_new == 1
    assert any("LLM classification failed" in e for e in result.errors)
    saved_event = result.events_to_save[0]
    assert saved_event.confidence_score is None
    assert saved_event.agent_review is not None
    assert "llm_error" in saved_event.agent_review
