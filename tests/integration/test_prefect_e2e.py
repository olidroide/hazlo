"""End-to-end test of Prefect flow with content hash dedup."""

import asyncio
import uuid

from hazlo.domain.source import Source, SourceType
from hazlo.infrastructure.db.repositories import SourceRepository
from hazlo.infrastructure.db.session import async_session_factory
from hazlo.infrastructure.prefect.flows import ingest_single_source_flow


async def test_prefect_flow_e2e():
    """Test Prefect flow end-to-end with real database."""
    print("=== Prefect Flow E2E Test ===\n")

    # Get or create a test source
    async with async_session_factory() as session:
        source_repo = SourceRepository(session)
        sources = await source_repo.list_all()

        if not sources:
            print("Creating test source...")
            source = Source(
                id=uuid.uuid4(),
                name="Test RSS Feed",
                source_type=SourceType.RSS,
                url="https://www.esmadrid.com/agenda/rss",
                is_active=True,
                fetch_interval_minutes=60,
            )
            source = await source_repo.save(source)
            await session.commit()
            print(f"Created source: {source.id}\n")
        else:
            source = sources[0]
            print(f"Using existing source: {source.name} ({source.id})\n")

    # Run the flow
    print("Running ingest_single_source_flow...")
    result = await ingest_single_source_flow(str(source.id))

    print("\n=== Results ===")
    print(f"Events found: {result['events_found']}")
    print(f"Events new: {result['events_new']}")
    print(f"Events skipped: {result['events_skipped']}")
    print(f"Events auto-approved: {result['events_auto_approved']}")
    print(f"Events flagged: {result['events_flagged']}")
    print(f"Errors: {len(result['errors'])}")

    if result["errors"]:
        print("\nFirst 5 errors:")
        for error in result["errors"][:5]:
            print(f"  - {error}")

    # Run again to test dedup
    print("\n=== Running again to test dedup ===")
    result2 = await ingest_single_source_flow(str(source.id))

    print(f"\nSecond run - Events skipped: {result2['events_skipped']}")
    print(f"Second run - Events new: {result2['events_new']}")

    if result2["events_skipped"] > 0:
        print("\n✅ Dedup working: events were skipped on second run")
    else:
        print("\n⚠️  No events skipped - check if source has duplicates")

    return result


if __name__ == "__main__":
    asyncio.run(test_prefect_flow_e2e())
