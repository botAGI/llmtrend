"""Manual data collection trigger.

Runs one or all collectors from the command line.  Useful for ad-hoc fetches
outside of the scheduled Celery tasks.

Usage::

    python -m scripts.run_collection            # collect from all sources
    python -m scripts.run_collection huggingface # single source
    python -m scripts.run_collection github
    python -m scripts.run_collection arxiv
"""

import asyncio
import sys

from app.services.collector_service import CollectorService


async def main() -> None:
    source = sys.argv[1] if len(sys.argv) > 1 else "all"

    if source == "all":
        print("Collecting from all sources...")
        results = await CollectorService.collect_all()
        for name, result in results.items():
            print(
                f"  {name}: fetched={result.items_fetched}, "
                f"created={result.items_created}, "
                f"updated={result.items_updated}"
            )
            if result.errors:
                for err in result.errors:
                    print(f"    ERROR: {err}")
    else:
        print(f"Collecting from {source}...")
        result = await CollectorService.collect_source(source)
        print(
            f"  {source}: fetched={result.items_fetched}, "
            f"created={result.items_created}, "
            f"updated={result.items_updated}"
        )
        if result.errors:
            for err in result.errors:
                print(f"    ERROR: {err}")


if __name__ == "__main__":
    asyncio.run(main())
