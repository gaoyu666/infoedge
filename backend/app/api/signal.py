from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import get_db
from app.db.models import Signal
from app.schemas import SignalFeedbackPayload, SignalItem, SuccessResponse

router = APIRouter()


def _to_dict(signal: Signal) -> dict:
    return {
        "id": signal.id,
        "level": signal.level,
        "score": signal.score,
        "title": signal.title,
        "type": signal.type,
        "gap": signal.gap,
        "window": signal.window,
        "circle": signal.circle,
        "region": signal.region,
        "crowding": signal.crowding,
        "risk": signal.risk,
        "difficulty": signal.difficulty,
        "sources": signal.sources or [],
        "time": signal.time_label,
        "roi": signal.roi_label,
        "convergence": signal.convergence,
        "created_at": signal.created_at,
    }


@router.get("/signals", response_model=SuccessResponse)
async def list_signals(
    type: Optional[str] = Query(default=None),
    circle: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default=None),
    level: Optional[str] = Query(default=None),
    limit: int = 20,
    offset: int = 0,
    db=Depends(get_db),
):
    try:
        stmt = select(Signal)
        if type:
            stmt = stmt.where(Signal.type == type)
        if circle:
            stmt = stmt.where(Signal.circle == circle)
        if region:
            stmt = stmt.where(Signal.region == region)
        if level:
            stmt = stmt.where(Signal.level == level)
        stmt = stmt.order_by(Signal.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        rows = result.scalars().all()
        payload = {"items": [_to_dict(row) for row in rows], "total": len(rows)}
        return SuccessResponse(data=payload)
    except SQLAlchemyError:
        fallback = {
            "items": [
                SignalItem(
                    id="s-92",
                    level="S",
                    score=92,
                    title="TikTok 美区 MagSafe 充电宝",
                    type="跨境电商",
                    gap="US->CN",
                    window="72h",
                    circle="跨境圈",
                    region="美国",
                    crowding="蓝海",
                    risk="低风险",
                    difficulty="低门槛",
                    sources=["TikTok", "微博", "1688"],
                    time="2 分钟前",
                    roi="1.6x-4x",
                    convergence="三源共振",
                    created_at=datetime.utcnow() - timedelta(minutes=2),
                ),
                SignalItem(
                    id="a-85",
                    level="A",
                    score=85,
                    title="AI 视频工作流的 Sora 替代品需求上升",
                    type="需求发现",
                    gap="Dev->大众",
                    window="48h",
                    circle="AI/深科技圈",
                    region="全球",
                    crowding="早期",
                    risk="中风险",
                    difficulty="中门槛",
                    sources=["HN", "Reddit", "X"],
                    time="15 分钟前",
                    roi="1.2x-2.8x",
                    convergence="强共振",
                    created_at=datetime.utcnow() - timedelta(minutes=15),
                ),
            ],
            "total": 2,
        }
        return SuccessResponse(data=fallback)


@router.get("/signals/{signal_id}", response_model=SuccessResponse)
async def get_signal(signal_id: str, db=Depends(get_db)):
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    row = result.scalar_one_or_none()
    if not row:
        return SuccessResponse(success=False, error="信号不存在", data={})
    return SuccessResponse(data=_to_dict(row))


@router.post("/signals/{signal_id}/feedback", response_model=SuccessResponse)
async def feedback_signal(signal_id: str, payload: SignalFeedbackPayload, db=Depends(get_db)):
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    if result.scalar_one_or_none() is None:
        return SuccessResponse(success=False, error="信号不存在", data={"signal_id": signal_id})

    if payload.action not in {"like", "dislike"}:
        return SuccessResponse(success=False, error="action must be like or dislike", data={"signal_id": signal_id})

    return SuccessResponse(
        data={
            "signal_id": signal_id,
            "action": payload.action,
            "reason": payload.reason,
            "status": "submitted",
            "submitted_at": datetime.utcnow().isoformat(),
        }
    )
