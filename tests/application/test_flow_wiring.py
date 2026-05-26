from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic_ai import ModelResponse
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from hazlo.application.services import DedupService, EnrichmentService, ReviewEngine
from hazlo.application.use_cases.ingest_source import IngestSource
from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo
from hazlo.domain.llm_output import ClassificationResult
from hazlo.domain.source import Source, SourceType
from hazlo.infrastructure.adapters.base import BaseSourceAdapter
from hazlo.infrastructure.llm.agents import QualityClassifierAgent

# ---------------------------------------------------------------------------
# Mock LLM model using FunctionModel
# ---------------------------------------------------------------------------


def create_mock_model(
    is_children_activity: bool = True,
    is_toddler_friendly: bool = True,
    confidence: float = 0.95,
    fail: bool = False,
) -> FunctionModel:
    """Create a FunctionModel that returns structured classification output."""

    def mock_generate(messages: list, info: AgentInfo) -> ModelResponse:
        if fail:
            raise ConnectionError("Mock model failure")

        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args={
                        "is_children_activity": is_children_activity,
                        "is_toddler_friendly": is_toddler_friendly,
                        "confidence": confidence,
                    },
                )
            ]
        )

    return FunctionModel(mock_generate)


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
    classifier: QualityClassifierAgent | None = None,
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
# QualityClassifierAgent — mock FunctionModel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classifier_wires_and_returns_result() -> None:
    model = create_mock_model(is_children_activity=True, is_toddler_friendly=True, confidence=0.95)
    classifier = QualityClassifierAgent(model)

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


@pytest.mark.asyncio
async def test_classifier_handles_low_confidence() -> None:
    model = create_mock_model(is_children_activity=False, is_toddler_friendly=False, confidence=0.30)
    classifier = QualityClassifierAgent(model)

    event = Event(title="Test", source_url="https://example.com/1")

    result = await classifier.execute(event)

    assert result.is_children_activity is False
    assert result.is_toddler_friendly is False
    assert result.confidence == 0.30


# ---------------------------------------------------------------------------
# IngestSource — flow wiring with classifier + review engine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow_with_classifier_and_review_auto_approves_high_confidence() -> None:
    model = create_mock_model(is_children_activity=True, is_toddler_friendly=True, confidence=0.96)
    classifier = QualityClassifierAgent(model)
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
    model = create_mock_model(is_children_activity=False, is_toddler_friendly=False, confidence=0.50)
    classifier = QualityClassifierAgent(model)
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
    call_count = 0

    def counting_generate(messages: list, info: AgentInfo) -> ModelResponse:
        nonlocal call_count
        call_count += 1
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args={"is_children_activity": True, "is_toddler_friendly": True, "confidence": 0.95},
                )
            ]
        )

    model = FunctionModel(counting_generate)
    classifier = QualityClassifierAgent(model)
    review_engine = ReviewEngine(auto_approve_threshold=0.95)

    events = [_make_raw_event(f"https://example.com/{i}") for i in range(3)]
    adapter = FakeAdapter(raw_events=events)
    use_case = _make_use_case(adapter, classifier=classifier, review_engine=review_engine)

    await use_case.execute(source=_make_source(), existing_urls=set())

    assert call_count == 3


@pytest.mark.asyncio
async def test_flow_with_classifier_and_failing_llm() -> None:
    """LLM model fails → classifier returns fallback → event processed with confidence=0.0."""
    model = create_mock_model(fail=True)
    classifier = QualityClassifierAgent(model, retries=1)
    review_engine = ReviewEngine(auto_approve_threshold=0.95)

    adapter = FakeAdapter(raw_events=[_make_raw_event()])
    use_case = _make_use_case(adapter, classifier=classifier, review_engine=review_engine)

    result = await use_case.execute(source=_make_source(), existing_urls=set())

    assert result.events_new == 1
    saved_event = result.events_to_save[0]
    assert saved_event.confidence_score == 0.0
    assert saved_event.is_children_activity is False
    assert saved_event.is_toddler_friendly is False
