import asyncio
import logging
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.api.dashboard import router as dashboard_router
from app.api.full import router as full_router
from app.api.signal import router as signal_router
from app.api.settings import router as settings_router
from app.db.models import PipelineRun
from app.services.cache_warmup import invalidate_runtime_cache, warm_core_cache
from app.services.real_pipeline import run_real_pipeline


from contextlib import asynccontextmanager


logger = logging.getLogger(__name__)
DAILY_PIPELINE_HOUR = 8


def _seconds_until_daily_run(hour: int = DAILY_PIPELINE_HOUR) -> float:
    now = datetime.now()
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


async def _scheduled_pipeline_loop() -> None:
    while True:
        await asyncio.sleep(_seconds_until_daily_run())
        run_id = f"pipe-scheduled-{uuid4().hex[:8]}"
        async with SessionLocal() as session:
            run = PipelineRun(
                id=run_id,
                steps=["sources", "clean", "signals", "opportunities"],
                status="running",
                started_at=datetime.utcnow(),
                message="daily scheduled pipeline queued",
            )
            session.add(run)
            await session.commit()
            try:
                summary = await run_real_pipeline(session)
                run.status = "success" if not summary.get("errors") else "partial_failed"
                run.finished_at = datetime.utcnow()
                run.message = (
                    "daily scheduled pipeline executed: "
                    f"{summary['raw_inserted']} raw, "
                    f"{summary['signals_inserted']} signals, "
                    f"{summary.get('signals_merged', 0)} merged signals, "
                    f"{summary['opportunities_inserted']} opportunities, "
                    f"{summary.get('opportunities_merged', 0)} merged opportunities, "
                    f"{summary['rejected']} filtered, "
                    f"{summary.get('historical_duplicates_filtered', 0)} historical duplicates, "
                    f"{summary.get('opportunities_scorecards_backfilled', 0)} scorecards backfilled, "
                    f"{summary.get('chinese_localization_backfilled', 0)} chinese localizations"
                )
                await session.commit()
                await invalidate_runtime_cache()
                await warm_core_cache(session)
            except Exception as exc:
                await session.rollback()
                failed = await session.get(PipelineRun, run_id)
                if failed is not None:
                    failed.status = "failed"
                    failed.finished_at = datetime.utcnow()
                    failed.message = f"daily scheduled pipeline failed: {exc}"
                    await session.commit()
                logger.exception("Scheduled pipeline failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async def warmup_background() -> None:
        async with SessionLocal() as session:
            try:
                warmed = await warm_core_cache(session)
                logger.info("Warmed runtime cache: %s", warmed)
            except Exception:
                logger.exception("Runtime cache warmup failed")

    warmup = asyncio.create_task(warmup_background())
    scheduler = asyncio.create_task(_scheduled_pipeline_loop())
    try:
        yield
    finally:
        warmup.cancel()
        scheduler.cancel()
        try:
            await warmup
        except asyncio.CancelledError:
            pass
        try:
            await scheduler
        except asyncio.CancelledError:
            pass


def _build_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="3.4.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(dashboard_router, prefix="/api")
    app.include_router(full_router, prefix="/api")
    app.include_router(signal_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    return app


app = _build_app()
