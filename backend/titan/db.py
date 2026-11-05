"""Async database layer: engine, session factory, schema creation and a
lightweight forward-only migration runner.

The default profile is SQLite (zero infrastructure). Setting
`TITAN_DATABASE_URL=postgresql+asyncpg://...` switches to PostgreSQL with no
code change. Schema management is intentionally simple and explicit: the
authoritative schema lives in `models.py`; `run_migrations()` applies it and
records applied steps in `schema_migrations`.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

log = logging.getLogger("titan.db")


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.resolved_database_url,
    echo=settings.sql_echo,
    future=True,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False, "timeout": 30} if settings.is_sqlite else {},
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Transactional scope: commits on success, rolls back on error."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: unit-of-work session that commits on success."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


MIGRATIONS: list[tuple[str, str]] = [
    (
        "0001_initial",
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version VARCHAR(64) NOT NULL UNIQUE,
            applied_at TIMESTAMP NOT NULL
        );
        """,
    ),
]


async def run_migrations() -> list[str]:
    """Apply forward-only migrations. Returns the list of applied versions."""
    from . import models  # noqa: F401  (ensures metadata is populated)

    applied: list[str] = []
    async with engine.begin() as conn:
        for version, ddl in MIGRATIONS:
            await conn.execute(text(ddl))
            applied.append(version)
        await conn.run_sync(Base.metadata.create_all)
        rows = await conn.execute(text("SELECT version FROM schema_migrations"))
        existing = {r[0] for r in rows}
        for version, _ in MIGRATIONS:
            if version not in existing:
                await conn.execute(
                    text("INSERT INTO schema_migrations (version, applied_at) VALUES (:v, :t)"),
                    {"v": version, "t": datetime.now(timezone.utc)},
                )
    log.info("migrations applied: %s", applied)
    return applied


async def dispose_engine() -> None:
    await engine.dispose()
