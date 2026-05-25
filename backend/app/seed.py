from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ActionItem,
    AgentAllocation,
    BacktestCase,
    Brief,
    InstitutionEvent,
    KnowledgeArticle,
    ModelConfig,
    Opportunity,
    PipelineRun,
    ScenarioPreset,
    Signal,
    SourceStatus,
    UserPreference,
    UserProfile,
)


SEED_SIGNALS = [
    {
        "id": "s-92",
        "level": "S",
        "score": 92,
        "title": "TikTok 美区 MagSafe 充电宝",
        "type": "跨境电商",
        "gap": "US->CN",
        "window": "72h",
        "circle": "跨境圈",
        "region": "美国",
        "crowding": "蓝海",
        "risk": "低风险",
        "difficulty": "低门槛",
        "sources": ["TikTok", "微博", "1688"],
        "time_label": "2 分钟前",
        "roi_label": "1.6x-4x",
        "convergence": "三源共振",
        "created_at": datetime.utcnow(),
    },
    {
        "id": "a-85",
        "level": "A",
        "score": 85,
        "title": "AI 视频工作流的 Sora 替代品需求上升",
        "type": "需求发现",
        "gap": "Dev->大众",
        "window": "48h",
        "circle": "AI/深科技圈",
        "region": "全球",
        "crowding": "早期",
        "risk": "中风险",
        "difficulty": "中门槛",
        "sources": ["HN", "Reddit", "X"],
        "time_label": "15 分钟前",
        "roi_label": "1.2x-2.8x",
        "convergence": "强共振",
        "created_at": datetime.utcnow(),
    },
]

SEED_MODELS = [
    {
        "name": "GLM-5.1",
        "provider": "OpenAI-compatible",
        "endpoint": "http://47.250.90.185:3212/v1",
        "state": "active",
        "usage": 1200000,
        "cost": 8.5,
        "capabilities": {"inference": True, "vision": False, "tools": True},
        "is_active": True,
    },
    {
        "name": "GPT-4o-mini",
        "provider": "OpenAI",
        "endpoint": "https://api.openai.com/v1",
        "state": "inactive",
        "usage": 0,
        "cost": 0.0,
        "capabilities": {"inference": True, "vision": False, "tools": True},
        "is_active": False,
    },
]

SEED_ALLOCATIONS = [
    {
        "name": "lead_agent",
        "model_name": "GLM-5.1",
        "recommended_model": "GLM-5.1",
    },
]

SEED_OPPORTUNITIES = [
    {
        "id": "o-301",
        "signal_id": "s-92",
        "score": 83,
        "level": "S",
        "dimensions": {
            "momentum": 0.92,
            "crowding": 0.21,
            "risk": 0.12,
            "pricing": 0.86,
            "execution": 0.79,
        },
        "playbook": "cross_border",
        "playbook_name": "跨境爆品推进",
        "window_hours": 72,
        "strategies": [
            "确认利润率区间",
            "快速锁定 3 个供应商样品",
            "首发 20 单试探",
            "根据转化率复盘调整选品",
        ],
        "crowding_score": 15,
        "risk_level": "low",
        "risk_factors": ["供应商交期波动", "平台流量波动"],
        "validation_score": 88,
        "bear_case": "平台限流或政策变化会使传播周期提前失效。",
        "difficulty": "low",
        "estimated_investment": "8,000-20,000 元",
        "estimated_return": "8,000-30,000 元 (30天)",
        "roi_ratio": "1.6x - 4x",
        "breakeven": "售出 80 件",
        "max_loss": "8,000 元库存回收",
        "execution_status": "not_started",
        "current_step": 0,
        "status": "new",
        "created_at": datetime.utcnow(),
    },
    {
        "id": "o-420",
        "signal_id": "a-85",
        "score": 76,
        "level": "A",
        "dimensions": {
            "momentum": 0.78,
            "crowding": 0.30,
            "risk": 0.22,
            "pricing": 0.72,
            "execution": 0.66,
        },
        "playbook": "content",
        "playbook_name": "内容工作流",
        "window_hours": 48,
        "strategies": ["制作横向教学内容", "同步社区种草", "监控需求扩散"],
        "crowding_score": 32,
        "risk_level": "medium",
        "risk_factors": ["技术更新频率高", "高客单替代品竞争"],
        "validation_score": 71,
        "bear_case": "内容同质化严重，拉新成本可能上升。",
        "difficulty": "medium",
        "estimated_investment": "3,000-6,000 元",
        "estimated_return": "5,000-12,000 元 (30天)",
        "roi_ratio": "1.2x - 2.8x",
        "breakeven": "完成 40 次转化",
        "max_loss": "3,000 元广告预算",
        "execution_status": "not_started",
        "current_step": 0,
        "status": "new",
        "created_at": datetime.utcnow(),
    },
]

SEED_ACTIONS = [
    {
        "id": "ac-01",
        "opportunity_id": "o-301",
        "user_id": "default",
        "playbook": "cross_border",
        "total_steps": 5,
        "current_step": 2,
        "step_notes": {
            "1": "已完成供应商对比：3 家可用",
            "2": "已完成首轮样品下单：2 天可到样",
        },
        "status": "in_progress",
        "signal_heat_at_start": 78.0,
        "signal_heat_current": 81.2,
        "heat_change_pct": 4.1,
        "invested_amount": 4300,
        "return_amount": 0,
        "result": "pending",
        "rating": None,
        "review_notes": None,
        "started_at": datetime.utcnow(),
        "completed_at": None,
        "reviewed_at": None,
    }
]

SEED_BACKTEST_CASES = [
    {
        "id": "bt-001",
        "playbook": "cross_border",
        "result": "profit",
        "hit_rate": 0.62,
        "total_cases": 120,
        "win_cases": 74,
        "avg_roi": "1.86x",
        "case_year": 2026,
        "notes": "跨境选品执行反馈良好",
        "created_at": datetime.utcnow(),
    }
]

SEED_SOURCES = [
    {
        "id": "src-hn",
        "source": "HackerNews",
        "status": "healthy",
        "freshness": "fresh",
        "last_checked": datetime.utcnow(),
        "signal_count_24h": 12,
        "notes": "正常抓取",
    },
    {
        "id": "src-reddit",
        "source": "Reddit",
        "status": "healthy",
        "freshness": "fresh",
        "last_checked": datetime.utcnow(),
        "signal_count_24h": 10,
        "notes": "关注度上升",
    },
    {
        "id": "src-wechat",
        "source": "微博",
        "status": "stable",
        "freshness": "moderate",
        "last_checked": datetime.utcnow(),
        "signal_count_24h": 7,
        "notes": "速率下降",
    },
]

SEED_INSTITUTIONS = [
    {
        "id": "ie-001",
        "institution": "Sequoia",
        "institution_type": "vc",
        "event_type": "investment",
        "target": "AI 创业公司 A",
        "amount": "$150m",
        "industry": "AI",
        "region": "美国",
        "description": "最新投资轮显示供应链相关产品扩展",
        "source_signal_id": "a-85",
        "detected_at": datetime.utcnow(),
    }
]

SEED_PREFERENCES = [
    {
        "id": "pref-1",
        "user_id": "default",
        "dimension": "circle",
        "value": "跨境电商",
        "weight": 1.4,
        "updated_at": datetime.utcnow(),
    },
    {
        "id": "pref-2",
        "user_id": "default",
        "dimension": "region",
        "value": "美国",
        "weight": 1.0,
        "updated_at": datetime.utcnow(),
    },
]

SEED_USER_PROFILE = [
    {
        "user_id": "default",
        "tier": "intermediate",
        "role": "indie-founder",
        "circles": "跨境,AI,内容创业",
        "regions": "美国,欧洲,中国",
        "capital": "10k-50k",
        "risk_appetite": "medium",
        "updated_at": datetime.utcnow(),
    }
]

SEED_KNOWLEDGE = [
    {
        "id": "k-001",
        "title": "从需求到执行：信息差选品流程",
        "category": "策略",
        "playbook": "cross_border",
        "content": "确认时间窗口 -> 验证供应链 -> 估算毛利 -> 小样本试跑",
        "created_at": datetime.utcnow(),
    },
    {
        "id": "k-002",
        "title": "执行追踪与复盘模板",
        "category": "实操",
        "playbook": "execution",
        "content": "记录每步产出、成本、转化率，按周复盘，迭代 playbook。",
        "created_at": datetime.utcnow(),
    },
]

SEED_PIPELINE = [
    {
        "id": "pl-001",
        "steps": ["collect", "clean", "analyze", "score", "strategy"],
        "status": "success",
        "started_at": datetime.utcnow(),
        "finished_at": datetime.utcnow(),
        "message": "首次初始化演示运行完成",
    }
]

SEED_BRIEFS = [
    {
        "id": "brief-001",
        "date_key": "2026-04-29",
        "title": "今日简报：美欧跨境与 AI 工具并行上升",
        "summary": "跨境商品信号与 AI 工具需求在 24 小时内持续升温，建议优先关注低拥挤低风险场景。",
        "payload": {
            "signals": ["s-92", "a-85"],
            "opportunities": ["o-301", "o-420"],
        },
        "created_at": datetime.utcnow(),
    }
]

SEED_SCENARIOS = [
    {
        "id": "sc-001",
        "name": "供应链波动",
        "scenario": "lead_time_shock",
        "description": "当供应链配送周期上升 20%以上，优先降级选择高周转 SKU。",
    },
    {
        "id": "sc-002",
        "name": "平台流量下滑",
        "scenario": "platform_decay",
        "description": "流量下降背景下，优先转向高意向垂类词包。",
    },
]


async def _seed_generic(db: AsyncSession, model_cls, key_name: str, seed_rows: list[dict]) -> None:
    keys = [r[key_name] for r in seed_rows]
    if not keys:
        return
    existing = await db.execute(select(getattr(model_cls, key_name)).where(getattr(model_cls, key_name).in_(keys)))
    exists = set(existing.scalars().all())
    for row in seed_rows:
        if row[key_name] not in exists:
            db.add(model_cls(**row))


async def seed_signals_if_empty(db: AsyncSession) -> None:
    await _seed_generic(db, Signal, "id", SEED_SIGNALS)


async def seed_models_if_empty(db: AsyncSession) -> None:
    await _seed_generic(db, ModelConfig, "name", SEED_MODELS)


async def seed_allocations_if_empty(db: AsyncSession) -> None:
    await _seed_generic(db, AgentAllocation, "name", SEED_ALLOCATIONS)


async def seed_opportunities_if_empty(db: AsyncSession) -> None:
    await _seed_generic(db, Opportunity, "id", SEED_OPPORTUNITIES)


async def seed_actions_if_empty(db: AsyncSession) -> None:
    await _seed_generic(db, ActionItem, "id", SEED_ACTIONS)


async def seed_backtest_cases_if_empty(db: AsyncSession) -> None:
    await _seed_generic(db, BacktestCase, "id", SEED_BACKTEST_CASES)


async def seed_sources_if_empty(db: AsyncSession) -> None:
    await _seed_generic(db, SourceStatus, "id", SEED_SOURCES)


async def seed_institutions_if_empty(db: AsyncSession) -> None:
    await _seed_generic(db, InstitutionEvent, "id", SEED_INSTITUTIONS)


async def seed_preferences_if_empty(db: AsyncSession) -> None:
    await _seed_generic(db, UserPreference, "id", SEED_PREFERENCES)


async def seed_user_profile_if_empty(db: AsyncSession) -> None:
    await _seed_generic(db, UserProfile, "user_id", SEED_USER_PROFILE)


async def seed_knowledge_if_empty(db: AsyncSession) -> None:
    await _seed_generic(db, KnowledgeArticle, "id", SEED_KNOWLEDGE)


async def seed_pipeline_if_empty(db: AsyncSession) -> None:
    await _seed_generic(db, PipelineRun, "id", SEED_PIPELINE)


async def seed_briefs_if_empty(db: AsyncSession) -> None:
    await _seed_generic(db, Brief, "id", SEED_BRIEFS)


async def seed_scenarios_if_empty(db: AsyncSession) -> None:
    await _seed_generic(db, ScenarioPreset, "id", SEED_SCENARIOS)


async def seed_scenario_history_if_empty(db: AsyncSession) -> None:
    # 历史记录按需创建，不作为必备种子
    return
