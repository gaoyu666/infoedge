from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SignalItem(BaseModel):
    id: str
    level: str
    score: int
    title: str
    type: str
    gap: str
    window: str
    circle: str
    region: str
    crowding: str
    risk: str
    difficulty: str
    sources: list[str]
    time: str
    roi: str
    convergence: str | None = None
    created_at: datetime


class SignalFeedbackPayload(BaseModel):
    action: str
    reason: str | None = None


class ModelItem(BaseModel):
    name: str
    provider: str
    endpoint: str
    state: str = "inactive"
    usage: str | None = None
    cost: str | float | None = None
    capabilities: dict | None = None


class AgentAllocationItem(BaseModel):
    agent_name: str
    model_name: str
    recommended_model: str


class AgentConfigPayload(BaseModel):
    agent_name: str
    display_name: str | None = None
    role: str | None = None
    system_prompt: str | None = None
    status: str = "active"
    cadence: str | None = None
    budget: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    fail_strategy: str = "retry_then_warn"
    max_daily_runs: int = 20
    max_daily_cost_cny: float = 5.0


class TokenUsageItem(BaseModel):
    skill_name: str
    model: str
    tokens: int
    cost: float


class SuccessResponse(BaseModel):
    success: bool = True
    data: Any
    error: str | None = None


class OpportunityItem(BaseModel):
    id: str
    signal_id: str
    score: int
    level: str
    dimensions: dict | None = None
    playbook: str
    playbook_name: str
    window_hours: int
    strategies: list[str] = []
    crowding_score: int
    risk_level: str
    validation_score: int
    difficulty: str
    estimated_investment: str
    estimated_return: str
    roi_ratio: str
    breakeven: str
    max_loss: str
    status: str
    execution_status: str
    created_at: datetime


class ActionItemPayload(BaseModel):
    opportunity_id: str | None = None


class OpportunityBoxPayload(BaseModel):
    opportunity_id: str | None = None
    source_type: str = "daily"
    title: str | None = None
    source: str | None = None
    score: int | None = None
    risk_level: str | None = None
    status: str = "tracking"
    rationale: list[str] = Field(default_factory=list)
    prediction: dict | None = None
    notes: str | None = None


class ActionProgressPayload(BaseModel):
    current_step: int
    note: str | None = None


class ActionReviewPayload(BaseModel):
    result: str
    amount: float | None = None
    rating: int | None = None
    notes: str | None = None


class PipelineRunPayload(BaseModel):
    steps: list[str]
    sources: list[str] = Field(default_factory=list)
    reason: str | None = None


class PreferencePayload(BaseModel):
    dimension: str
    value: str
    weight: float = 1.0


class UserProfilePayload(BaseModel):
    tier: str | None = None
    role: str | None = None
    circles: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    capital: str | None = None
    risk_appetite: str | None = None


class OnboardingPayload(BaseModel):
    role: str
    circles: list[str] = Field(default_factory=list)
    region: str
    capital: str
    risk_appetite: str | None = None


class ScenarioAnalyzePayload(BaseModel):
    scenario: str
    preset_id: str | None = None


class PipelineAnalyzePayload(BaseModel):
    steps: list[str] = Field(default_factory=lambda: ["collect", "clean", "analyze", "score"])
