from __future__ import annotations

from datetime import datetime
from sqlalchemy import JSON, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, index=True)
    level: Mapped[str] = mapped_column(String(8))
    score: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(240))
    type: Mapped[str] = mapped_column(String(80))
    gap: Mapped[str] = mapped_column(String(80))
    window: Mapped[str] = mapped_column(String(40))
    circle: Mapped[str] = mapped_column(String(80))
    region: Mapped[str] = mapped_column(String(80))
    crowding: Mapped[str] = mapped_column(String(24))
    risk: Mapped[str] = mapped_column(String(24))
    difficulty: Mapped[str] = mapped_column(String(24))
    sources: Mapped[list[str] | None] = mapped_column(JSONB, default=list)
    time_label: Mapped[str] = mapped_column(String(40))
    roi_label: Mapped[str] = mapped_column(String(80))
    convergence: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class RawItem(Base):
    __tablename__ = "raw_items"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    source_item_id: Mapped[str] = mapped_column(String(160), index=True)
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class CleanItem(Base):
    __tablename__ = "clean_items"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    raw_item_id: Mapped[str] = mapped_column(String(80), index=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    topic: Mapped[str] = mapped_column(String(80), default="general")
    circle: Mapped[str] = mapped_column(String(80), default="AI/深科技圈")
    region: Mapped[str] = mapped_column(String(80), default="全球")
    keywords: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    entities: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class ModelConfig(Base):
    __tablename__ = "model_registry"

    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    provider: Mapped[str] = mapped_column(String(80))
    endpoint: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(24), default="inactive")
    usage: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0)
    capabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=False)


class AgentAllocation(Base):
    __tablename__ = "agent_allocation"

    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(80))
    recommended_model: Mapped[str] = mapped_column(String(80))


class AgentConfig(Base):
    __tablename__ = "agent_configs"

    agent_name: Mapped[str] = mapped_column(String(80), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    role: Mapped[str] = mapped_column(Text, default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="active")
    cadence: Mapped[str] = mapped_column(String(80), default="manual")
    budget: Mapped[str] = mapped_column(String(80), default="medium")
    allowed_tools: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    fail_strategy: Mapped[str] = mapped_column(String(80), default="retry_then_warn")
    max_daily_runs: Mapped[int] = mapped_column(Integer, default=20)
    max_daily_cost_cny: Mapped[float] = mapped_column(Float, default=5.0)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    signal_id: Mapped[str] = mapped_column(String(32), index=True)
    score: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String(8))
    dimensions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    playbook: Mapped[str] = mapped_column(String(40))
    playbook_name: Mapped[str] = mapped_column(String(60))
    window_hours: Mapped[int] = mapped_column(Integer, default=24)
    strategies: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    crowding_score: Mapped[int] = mapped_column(Integer, default=30)
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    risk_factors: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    validation_score: Mapped[int] = mapped_column(Integer, default=70)
    bear_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(24), default="low")
    estimated_investment: Mapped[str] = mapped_column(String(80), default="")
    estimated_return: Mapped[str] = mapped_column(String(80), default="")
    roi_ratio: Mapped[str] = mapped_column(String(40), default="1x-1x")
    breakeven: Mapped[str] = mapped_column(String(80), default="N/A")
    max_loss: Mapped[str] = mapped_column(String(80), default="N/A")
    execution_status: Mapped[str] = mapped_column(String(24), default="not_started")
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    actual_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="new")
    user_feedback: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class OpportunityAnalysis(Base):
    __tablename__ = "opportunity_analysis"

    opportunity_id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(80), default="")
    title: Mapped[str] = mapped_column(String(240), default="")
    evidence_title: Mapped[str] = mapped_column(String(300), default="")
    analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generated_by: Mapped[str] = mapped_column(String(80), default="MerchantAnalysisAgent")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class OpportunityBoxItem(Base):
    __tablename__ = "opportunity_box"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(80), default="default", index=True)
    opportunity_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(24), default="daily")
    title: Mapped[str] = mapped_column(String(240))
    source: Mapped[str] = mapped_column(String(80), default="")
    score: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(24), default="tracking")
    rationale: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    prediction: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(80), index=True)
    user_id: Mapped[str] = mapped_column(String(80), default="default")
    playbook: Mapped[str] = mapped_column(String(60))
    total_steps: Mapped[int] = mapped_column(Integer, default=5)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    step_notes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="in_progress")
    signal_heat_at_start: Mapped[float] = mapped_column(Float, default=0.0)
    signal_heat_current: Mapped[float] = mapped_column(Float, default=0.0)
    heat_change_pct: Mapped[float] = mapped_column(Float, default=0.0)
    invested_amount: Mapped[float] = mapped_column(Float, default=0.0)
    return_amount: Mapped[float] = mapped_column(Float, default=0.0)
    result: Mapped[str] = mapped_column(String(16), default="pending")
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class BacktestCase(Base):
    __tablename__ = "backtest_cases"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    playbook: Mapped[str] = mapped_column(String(40))
    result: Mapped[str] = mapped_column(String(20))
    hit_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    win_cases: Mapped[int] = mapped_column(Integer, default=0)
    avg_roi: Mapped[str] = mapped_column(String(80), default="1.0x")
    case_year: Mapped[int] = mapped_column(Integer, default=2026)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class SourceStatus(Base):
    __tablename__ = "source_status"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="normal")
    freshness: Mapped[str] = mapped_column(String(20), default="fresh")
    last_checked: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    signal_count_24h: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class InstitutionEvent(Base):
    __tablename__ = "institution_events"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institution: Mapped[str] = mapped_column(String(80))
    institution_type: Mapped[str] = mapped_column(String(24))
    event_type: Mapped[str] = mapped_column(String(40))
    target: Mapped[str] = mapped_column(String(120))
    amount: Mapped[str | None] = mapped_column(String(80), nullable=True)
    industry: Mapped[str] = mapped_column(String(50))
    region: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text, default="")
    source_signal_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(80), index=True)
    dimension: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(80))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    tier: Mapped[str] = mapped_column(String(24), default="starter")
    role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    circles: Mapped[str | None] = mapped_column(String(200), nullable=True)
    regions: Mapped[str | None] = mapped_column(String(200), nullable=True)
    capital: Mapped[str | None] = mapped_column(String(80), nullable=True)
    risk_appetite: Mapped[str | None] = mapped_column(String(24), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(140))
    category: Mapped[str] = mapped_column(String(60))
    playbook: Mapped[str] = mapped_column(String(60))
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    steps: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="running")
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


class Brief(Base):
    __tablename__ = "daily_briefs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    date_key: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class ScenarioPreset(Base):
    __tablename__ = "scenario_presets"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    scenario: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")


class ScenarioHistory(Base):
    __tablename__ = "scenario_history"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    preset_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    scenario: Mapped[str] = mapped_column(String(120))
    result: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

