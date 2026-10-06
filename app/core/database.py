from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
from app.core.logging import logger


class Base(DeclarativeBase):
    pass


# Async engine configured from settings
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncSession:
    """FastAPI dependency for yielding async db sessions."""
    async with async_session() as session:
        try:
            yield session
        except Exception as err:
            await session.rollback()
            logger.error(f"Database session error: {err}")
            raise
        finally:
            await session.close()
