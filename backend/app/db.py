from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = create_async_engine(get_settings().database_url, echo=False)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def init_db() -> None:
    # Phase 1: create tables directly. Alembic is wired up (see alembic/) for the
    # phase-3 SQLite -> Postgres cutover, but a bare create_all is enough while the
    # schema is still moving fast.
    async with _engine.begin() as conn:
        from app.models import submission  # noqa: F401  (register models on Base.metadata)

        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        yield session


def session_factory() -> async_sessionmaker[AsyncSession]:
    return _session_factory
