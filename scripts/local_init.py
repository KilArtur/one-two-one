"""Initialize local media storage before starting application services."""

import asyncio

from app.integrations.storage import get_s3_storage_client


async def main() -> None:
    """Verify the configured bucket exists."""
    await get_s3_storage_client().ensure_bucket()
    print("Media bucket ready")


if __name__ == "__main__":
    asyncio.run(main())
