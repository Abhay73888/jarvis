"""Async engine/session factory and versioned migrations (Spec §47)."""
from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.logging import get_logger
from app.database.models import Base

log = get_logger("db")

# Numbered migrations applied in order; each entry bumps schema_version.
MIGRATIONS: tuple[tuple[int, str], ...] = (
    (1, "initial schema"),  # Base.metadata.create_all — see init_db
)


def make_engine(db_file: Path) -> AsyncEngine:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> int:
    """Create tables (idempotent) and stamp schema version. Returns version."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(sa.text(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"))
        result = await conn.execute(sa.text("SELECT version FROM schema_version"))
        version = result.scalar()
        if version is None:
            # Stamp with the latest migration; fresh installs are always current.
            await conn.execute(sa.text(f"INSERT INTO schema_version (version) VALUES ({MIGRATIONS[-1][0]})"))
            version = MIGRATIONS[-1][0]
    log.debug("database ready at schema version %s", version)
    return int(version)
