from __future__ import annotations

import logging

from sqlalchemy import func, select

from app.core.cache import cache_delete_pattern, cache_set
from app.db.models import Brief, CleanItem, Opportunity, OpportunityAnalysis, PipelineRun, RawItem, Signal, SourceStatus


logger = logging.getLogger(__name__)


def _serialize(model) -> dict:
    if model is None:
        return {}
    return {
        "id": getattr(model, "id", None) or getattr(model, "user_id", None),
        **{
            k: v
            for k, v in model.__dict__.items()
            if not k.startswith("_") and not callable(v)
        },
    }


async def invalidate_runtime_cache() -> None:
    for pattern in (
        "api:dashboard:*",
        "api:circles:*",
        "api:regions:*",
        "api:opportunities:*",
        "api:opportunity:*",
        "api:opportunity-box:*",
        "api:sources:*",
        "api:brief:*",
        "api:pipeline:*",
    ):
        await cache_delete_pattern(pattern)


async def warm_core_cache(session) -> dict[str, int]:
    warmed: dict[str, int] = {}

    source_rows = (await session.execute(select(SourceStatus).order_by(SourceStatus.source))).scalars().all()
    await cache_set("api:sources:status", {"items": [_serialize(r) for r in source_rows], "total": len(source_rows)}, 60)
    warmed["sources"] = len(source_rows)

    opportunity_rows = (
        await session.execute(
            select(
                Opportunity.id,
                Opportunity.signal_id,
                Opportunity.score,
                Opportunity.level,
                Opportunity.dimensions,
                Opportunity.playbook,
                Opportunity.playbook_name,
                Opportunity.window_hours,
                Opportunity.strategies,
                Opportunity.crowding_score,
                Opportunity.risk_level,
                Opportunity.validation_score,
                Opportunity.difficulty,
                Opportunity.estimated_investment,
                Opportunity.execution_status,
                Opportunity.current_step,
                Opportunity.status,
                Opportunity.created_at,
                OpportunityAnalysis.title.label("analysis_title"),
                OpportunityAnalysis.evidence_title.label("analysis_evidence_title"),
                OpportunityAnalysis.source.label("analysis_source"),
                func.count(Opportunity.id).over().label("total_count"),
            )
            .outerjoin(
                OpportunityAnalysis,
                OpportunityAnalysis.opportunity_id == Opportunity.id,
            )
            .where(Opportunity.status != "filtered")
            .order_by(Opportunity.created_at.desc())
            .limit(50)
        )
    ).all()
    from app.api.full import _opportunity_list_payload_from_row

    warmed_items = []
    for row in opportunity_rows:
        warmed_items.append(_opportunity_list_payload_from_row(row))
    total_all = int(opportunity_rows[0].total_count or 0) if opportunity_rows else 0
    await cache_set(
        "api:opportunities:list:v5:evidence_at:all:all:all:all:all:all:50",
        {"items": warmed_items, "total": total_all, "total_all": total_all},
        60,
    )
    warmed["opportunities"] = len(opportunity_rows)

    warmed["opportunity_details"] = 0

    latest_run = (await session.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(1))).scalars().first()
    await cache_set("api:pipeline:status", _serialize(latest_run) if latest_run else {"status": "idle"}, 15)
    warmed["pipeline"] = 1 if latest_run else 0

    latest_brief = (await session.execute(select(Brief).order_by(Brief.created_at.desc()).limit(1))).scalars().first()
    await cache_set("api:brief:latest", _serialize(latest_brief) if latest_brief else {"summary": "", "items": []}, 90)
    warmed["brief"] = 1 if latest_brief else 0

    await _warm_dashboard_stats(session)
    warmed["dashboard"] = 1
    return warmed


async def _warm_dashboard_stats(session) -> None:
    from datetime import datetime, timedelta

    since = datetime.utcnow() - timedelta(hours=24)
    result = await session.execute(
        select(
            func.count(Signal.id).label("total"),
            func.count(Signal.id).filter(Signal.level.in_(["S", "A"])).label("high_level"),
        ).where(Signal.created_at >= since)
    )
    row = result.one()
    active_sources = (
        await session.execute(
            select(func.count(SourceStatus.id)).where(SourceStatus.status.in_(["healthy", "normal", "stable"]))
        )
    ).scalar_one()
    data_volume = (
        await session.execute(select(func.count(RawItem.id)).where(RawItem.fetched_at >= since))
    ).scalar_one()
    await cache_set(
        "api:dashboard:stats",
        {
            "win_rate": 62,
            "signals_24h": int(row.total),
            "high_level_signals": int(row.high_level),
            "active_sources": int(active_sources),
            "source_health": "良好",
            "data_volume": int(data_volume),
        },
        60,
    )


async def _warm_opportunity_detail(session, opportunity: Opportunity) -> None:
    from app.api.full import (
        _evidence_payload,
        _find_clean_for_signal,
        _get_or_create_opportunity_analysis,
        _opportunity_payload,
        _opportunity_oci_payload,
        _opportunity_risk_payload,
        _opportunity_roi_payload,
        _opportunity_validation_payload,
    )

    signal = await session.get(Signal, opportunity.signal_id)
    dimensions = opportunity.dimensions or {}
    clean = await session.get(CleanItem, dimensions.get("clean_item_id")) if dimensions.get("clean_item_id") else None
    raw = await session.get(RawItem, dimensions.get("raw_item_id")) if dimensions.get("raw_item_id") else None
    if clean is None:
        clean = await _find_clean_for_signal(session, opportunity.signal_id, signal)
    if raw is None and clean is not None:
        raw = await session.get(RawItem, clean.raw_item_id)
    source_rows = (await session.execute(select(SourceStatus))).scalars().all()
    source_statuses = {row.source: row for row in source_rows}
    analysis_row = await _get_or_create_opportunity_analysis(session, opportunity, signal, clean, raw)
    await cache_set(
        f"api:opportunity:detail:v6:{opportunity.id}",
        {
            "opportunity": _opportunity_payload(opportunity, signal, source_statuses, clean, raw),
            "signal": _serialize(signal) if signal else None,
            "evidence": _evidence_payload(
                opportunity=opportunity,
                signal=signal,
                clean=clean,
                raw=raw,
                merchant_analysis=analysis_row.analysis if analysis_row else None,
            ),
            "analysis": _serialize(analysis_row),
            "risk": _opportunity_risk_payload(opportunity),
            "validation": _opportunity_validation_payload(opportunity),
            "roi": _opportunity_roi_payload(opportunity),
            "oci": _opportunity_oci_payload(opportunity),
        },
        120,
    )
