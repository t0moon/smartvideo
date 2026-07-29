from __future__ import annotations

from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import DATA_DIR

DB_PATH = DATA_DIR / 'smartvideo.db'
DATABASE_URL = f'sqlite+aiosqlite:///{DB_PATH}'

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        from storage.mysql.models import ProjectModel, RunModel, AssetModel, ReviewModel  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()
