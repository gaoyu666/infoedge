from typing import AsyncGenerator
import logging

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings
from app.db.models import Base, Opportunity, SourceStatus
from app.seed import (
    seed_actions_if_empty,
    seed_briefs_if_empty,
    seed_institutions_if_empty,
    seed_knowledge_if_empty,
    seed_models_if_empty,
    seed_opportunities_if_empty,
    seed_pipeline_if_empty,
    seed_preferences_if_empty,
    seed_scenarios_if_empty,
    seed_signals_if_empty,
    seed_sources_if_empty,
    seed_user_profile_if_empty,
    seed_allocations_if_empty,
    seed_backtest_cases_if_empty,
)


logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    connect_args={"timeout": 15},
)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            signal_sources_type = await conn.scalar(
                text(
                    """
                    SELECT data_type
                    FROM information_schema.columns
                    WHERE table_name = 'signals' AND column_name = 'sources'
                    """
                )
            )
            if signal_sources_type != "jsonb":
                await conn.execute(text("ALTER TABLE signals ALTER COLUMN sources TYPE jsonb USING sources::jsonb"))
            await conn.execute(text("SELECT 1"))

        async with SessionLocal() as session:
            existing_opportunities = await session.scalar(select(func.count(Opportunity.id)))
            existing_sources = await session.scalar(select(func.count(SourceStatus.id)))
            if existing_opportunities and existing_sources:
                return
            await seed_signals_if_empty(session)
            await seed_models_if_empty(session)
            await seed_allocations_if_empty(session)
            await seed_opportunities_if_empty(session)
            await seed_actions_if_empty(session)
            await seed_backtest_cases_if_empty(session)
            await seed_sources_if_empty(session)
            await seed_institutions_if_empty(session)
            await seed_preferences_if_empty(session)
            await seed_user_profile_if_empty(session)
            await seed_knowledge_if_empty(session)
            await seed_pipeline_if_empty(session)
            await seed_briefs_if_empty(session)
            await seed_scenarios_if_empty(session)
            await session.commit()
    except Exception as exc:
        logger.warning("Database bootstrap skipped: %s", exc)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.close()


def get_redis_url() -> str:
    return settings.redis_url
