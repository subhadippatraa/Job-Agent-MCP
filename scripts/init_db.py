"""Database initialization script."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from job_search_agent.database import init_db


async def main():
    print("Initializing database...")
    await init_db()
    print("✅ Database tables created successfully!")


if __name__ == "__main__":
    asyncio.run(main())
