from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from . import models  # noqa: F401

    if settings.database_url.startswith("sqlite"):
        settings.workspace_root.mkdir(parents=True, exist_ok=True)
        settings.report_root.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    await engine.dispose()
