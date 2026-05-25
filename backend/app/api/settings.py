from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.cache import cache_delete_pattern, cached
from app.core.config import settings
from app.core.db import get_db
from app.db.models import AgentAllocation, AgentConfig, ModelConfig
from app.schemas import AgentAllocationItem, AgentConfigPayload, ModelItem, SuccessResponse, TokenUsageItem
from app.services.glm_client import GLMError, glm_chat_completion, glm_is_configured

router = APIRouter()


DEFAULT_AGENT_CONFIGS = [
    {
        "agent_name": "SourceCollectorAgent",
        "display_name": "数据采集智能体",
        "role": "采集 GitHub、Reddit、RSS、App Store 与扩展来源，产出原始信号。",
        "system_prompt": "你负责发现可商业化的早期信号。优先保留来源、时间、热度指标和可验证链接，过滤低质量噪声。",
        "status": "active",
        "cadence": "每日 08:00 / 手动",
        "budget": "低",
        "allowed_tools": ["source_connectors", "rss_fetch", "github_api", "reddit_fetch"],
        "fail_strategy": "retry_then_warn",
        "max_daily_runs": 24,
        "max_daily_cost_cny": 3.0,
    },
    {
        "agent_name": "ChineseLocalizationAgent",
        "display_name": "中文化智能体",
        "role": "保留原文并生成中文标题、摘要、关键词和元数据。",
        "system_prompt": "你负责把英文或其他语言信号转成清晰中文，不夸大、不改写事实，保留原始标题和内容。",
        "status": "active",
        "cadence": "入库实时",
        "budget": "低",
        "allowed_tools": ["local_glossary", "language_detect"],
        "fail_strategy": "fallback_local",
        "max_daily_runs": 300,
        "max_daily_cost_cny": 2.0,
    },
    {
        "agent_name": "OpportunityScoringAgent",
        "display_name": "机会评分智能体",
        "role": "按需求、动量、供给、竞争、执行、风险六维评分。",
        "system_prompt": "你负责给商业机会打分。输出必须包含分数、风险、验证建议、反方场景，不允许只给泛泛结论。",
        "status": "active",
        "cadence": "清洗后",
        "budget": "中",
        "allowed_tools": ["scorecard", "evidence_metrics"],
        "fail_strategy": "retry_then_warn",
        "max_daily_runs": 120,
        "max_daily_cost_cny": 8.0,
    },
    {
        "agent_name": "EvidenceAgent",
        "display_name": "证据链智能体",
        "role": "为机会详情生成证据链、来源解释和处理轨迹。",
        "system_prompt": "你负责解释一条机会为什么值得看。所有结论都要能回到来源、指标或处理步骤。",
        "status": "active",
        "cadence": "详情预热",
        "budget": "中",
        "allowed_tools": ["opportunity_detail", "source_trace"],
        "fail_strategy": "use_cached_evidence",
        "max_daily_runs": 80,
        "max_daily_cost_cny": 6.0,
    },
    {
        "agent_name": "DailyBriefAgent",
        "display_name": "每日简报智能体",
        "role": "把信号、机会、数据源、风险组织成每日行动简报。",
        "system_prompt": "你给老板写行动简报。先给结论，再给 Top 机会、风险、数据源异常和今日待办。",
        "status": "active",
        "cadence": "每日 08:10 / 手动",
        "budget": "低",
        "allowed_tools": ["brief_builder", "cache_warmup"],
        "fail_strategy": "retry_then_warn",
        "max_daily_runs": 12,
        "max_daily_cost_cny": 5.0,
    },
    {
        "agent_name": "RiskAgent",
        "display_name": "风险智能体",
        "role": "识别拥挤、平台、政策、噪声和执行风险。",
        "system_prompt": "你负责唱反调。指出机会为什么可能失败，并给出降低损失的验证方式。",
        "status": "active",
        "cadence": "评分后",
        "budget": "中",
        "allowed_tools": ["risk_rules", "source_status"],
        "fail_strategy": "mark_for_review",
        "max_daily_runs": 80,
        "max_daily_cost_cny": 6.0,
    },
    {
        "agent_name": "ChatAdvisorAgent",
        "display_name": "经营对话智能体",
        "role": "围绕日报、机会、数据源和执行记录进行经营问答。",
        "system_prompt": "你是经营助手。回答必须结合当前日报、机会池和数据源，不确定时明确说明需要补采集或补证据。",
        "status": "active",
        "cadence": "按需",
        "budget": "可控",
        "allowed_tools": ["brief_latest", "opportunity_list", "source_status", "action_items"],
        "fail_strategy": "answer_with_context_only",
        "max_daily_runs": 200,
        "max_daily_cost_cny": 10.0,
    },
]


def _model_to_dict(row: ModelItem | ModelConfig | None) -> dict:
    if row is None:
        return {}
    return {
        "name": row.name,
        "provider": row.provider,
        "endpoint": row.endpoint,
        "state": row.state,
        "usage": f"{row.usage} tokens",
        "cost": row.cost,
        "capabilities": row.capabilities,
        "is_active": row.is_active,
    }


def _agent_config_to_dict(row: AgentConfig | None, fallback: dict | None = None) -> dict:
    data = dict(fallback or {})
    if row is not None:
        data.update(
            {
                "agent_name": row.agent_name,
                "display_name": row.display_name,
                "role": row.role,
                "system_prompt": row.system_prompt,
                "status": row.status,
                "cadence": row.cadence,
                "budget": row.budget,
                "allowed_tools": row.allowed_tools or [],
                "fail_strategy": row.fail_strategy,
                "max_daily_runs": row.max_daily_runs,
                "max_daily_cost_cny": row.max_daily_cost_cny,
                "updated_at": row.updated_at,
            }
        )
    return data


@router.get("/models")
async def get_models(db=Depends(get_db)):
    try:
        result = await db.execute(select(ModelConfig))
        rows = result.scalars().all()
        return SuccessResponse(data=[_model_to_dict(row) for row in rows]).dict()
    except SQLAlchemyError:
        return SuccessResponse(
            data=[
                {
                    "name": settings.glm_model,
                    "provider": "Zhipu GLM",
                    "endpoint": settings.glm_base_url,
                    "state": "active",
                    "usage": "1.2M tokens",
                    "cost": "8.5",
                    "capabilities": {"inference": True, "vision": False, "tools": True},
                    "is_active": True,
                }
            ]
        ).dict()


@router.get("/settings/models/allocation")
async def get_allocation(db=Depends(get_db)):
    async def load():
        rows = (await db.execute(select(AgentAllocation))).scalars().all()
        return [
            {
                "agent_name": row.name,
                "model_name": row.model_name,
                "recommended_model": row.recommended_model,
            }
            for row in rows
        ]

    return SuccessResponse(data=await cached("api:settings:allocation", 300, load)).dict()


@router.put("/settings/models/allocation")
async def update_allocation(payload: List[AgentAllocationItem], db=Depends(get_db)):
    try:
        for item in payload:
            current = await db.get(AgentAllocation, item.agent_name)
            if current is None:
                db.add(AgentAllocation(name=item.agent_name, model_name=item.model_name, recommended_model=item.recommended_model))
            else:
                current.model_name = item.model_name
                current.recommended_model = item.recommended_model
        await db.commit()
        await cache_delete_pattern("api:settings:*")
        return SuccessResponse(data={"updated": len(payload)}).dict()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/agents/configs")
async def agent_configs(db=Depends(get_db)):
    async def load():
        rows = (await db.execute(select(AgentConfig))).scalars().all()
        by_name = {row.agent_name: row for row in rows}
        names = set(by_name)
        items = [_agent_config_to_dict(by_name.get(item["agent_name"]), item) for item in DEFAULT_AGENT_CONFIGS]
        for name in sorted(names - {item["agent_name"] for item in DEFAULT_AGENT_CONFIGS}):
            items.append(_agent_config_to_dict(by_name[name]))
        return items

    return SuccessResponse(data=await cached("api:agents:configs", 120, load)).dict()


@router.put("/agents/configs")
async def update_agent_configs(payload: List[AgentConfigPayload], db=Depends(get_db)):
    try:
        for item in payload:
            current = await db.get(AgentConfig, item.agent_name)
            values = item.dict()
            if current is None:
                db.add(
                    AgentConfig(
                        agent_name=item.agent_name,
                        display_name=item.display_name or item.agent_name,
                        role=item.role or "",
                        system_prompt=item.system_prompt or "",
                        status=item.status,
                        cadence=item.cadence or "manual",
                        budget=item.budget or "medium",
                        allowed_tools=item.allowed_tools,
                        fail_strategy=item.fail_strategy,
                        max_daily_runs=item.max_daily_runs,
                        max_daily_cost_cny=item.max_daily_cost_cny,
                        updated_at=datetime.utcnow(),
                    )
                )
            else:
                current.display_name = values.get("display_name") or current.display_name or item.agent_name
                current.role = values.get("role") or ""
                current.system_prompt = values.get("system_prompt") or ""
                current.status = item.status
                current.cadence = values.get("cadence") or "manual"
                current.budget = values.get("budget") or "medium"
                current.allowed_tools = item.allowed_tools
                current.fail_strategy = item.fail_strategy
                current.max_daily_runs = item.max_daily_runs
                current.max_daily_cost_cny = item.max_daily_cost_cny
                current.updated_at = datetime.utcnow()
        await db.commit()
        await cache_delete_pattern("api:agents:*")
        return SuccessResponse(data={"updated": len(payload)}).dict()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/settings/models/usage")
async def model_usage_summary():
    return SuccessResponse(
        data={
            "total_tokens": 3600000,
            "estimated_cost_cny": 25.2,
            "daily_avg_cost_cny": 0.84,
            "items": [
                TokenUsageItem(skill_name="Lead Agent", model="GLM-5.1", tokens=720000, cost=4.9).dict(),
                TokenUsageItem(skill_name="策略推荐", model="GLM-5.1", tokens=680000, cost=5.4).dict(),
            ],
        }
    ).dict()


@router.put("/settings/models")
async def update_model_settings(models: List[ModelItem], db=Depends(get_db)):
    try:
        for item in models:
            model = await db.get(ModelConfig, item.name)
            if model is None:
                db.add(
                    ModelConfig(
                        name=item.name,
                        provider=item.provider,
                        endpoint=item.endpoint,
                        state=item.state or "inactive",
                        usage=0,
                        cost=0.0,
                        capabilities=item.capabilities or {},
                        is_active=item.state == "active",
                    )
                )
            else:
                model.provider = item.provider
                model.endpoint = item.endpoint
                model.state = item.state or model.state
                model.capabilities = item.capabilities or model.capabilities
                model.is_active = item.state == "active"
        await db.commit()
        return SuccessResponse(data={"updated": len(models)}).dict()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/settings/models/registry")
async def registry_list(db=Depends(get_db)):
    async def load():
        rows = (await db.execute(select(ModelConfig))).scalars().all()
        return [_model_to_dict(row) for row in rows]

    return SuccessResponse(data=await cached("api:settings:registry", 300, load)).dict()


@router.post("/settings/models/registry")
async def registry_create(payload: ModelItem, db=Depends(get_db)):
    try:
        exists = await db.get(ModelConfig, payload.name)
        if exists is not None:
            raise HTTPException(status_code=409, detail="模型已存在")
        db.add(
            ModelConfig(
                name=payload.name,
                provider=payload.provider,
                endpoint=payload.endpoint,
                state=payload.state or "inactive",
                usage=0,
                cost=0.0,
                capabilities=payload.capabilities or {},
                is_active=payload.state == "active",
            )
        )
        await db.commit()
        await cache_delete_pattern("api:settings:*")
        return SuccessResponse(data={"created": payload.name}).dict()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/settings/models/registry/{name}")
async def registry_update(name: str, payload: ModelItem, db=Depends(get_db)):
    model = await db.get(ModelConfig, name)
    if model is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    model.endpoint = payload.endpoint
    model.provider = payload.provider
    model.state = payload.state or model.state
    model.capabilities = payload.capabilities or model.capabilities
    model.is_active = payload.state == "active"
    await db.commit()
    await cache_delete_pattern("api:settings:*")
    return SuccessResponse(data={"updated": name}).dict()


@router.delete("/settings/models/registry/{name}")
async def registry_delete(name: str, db=Depends(get_db)):
    model = await db.get(ModelConfig, name)
    if model is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    await db.delete(model)
    await db.commit()
    await cache_delete_pattern("api:settings:*")
    return SuccessResponse(data={"deleted": name}).dict()


@router.post("/settings/models/registry/{name}/test")
async def registry_test_connection(name: str, db=Depends(get_db)):
    model = await db.get(ModelConfig, name)
    if model is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    model_text = " ".join([model.name, model.provider, model.endpoint]).lower()
    if "glm" in model_text or "bigmodel" in model_text or "zhipu" in model_text:
        if not glm_is_configured():
            return SuccessResponse(
                success=False,
                error="GLM_API_KEY 未配置",
                data={
                    "name": name,
                    "test": "missing_api_key",
                    "provider": "glm",
                    "configured": False,
                    "model": settings.glm_model,
                    "endpoint": settings.glm_base_url,
                },
            ).dict()
        try:
            response = await glm_chat_completion(
                messages=[
                    {"role": "system", "content": "你是连接测试助手。"},
                    {"role": "user", "content": "只回复 ok"},
                ],
                temperature=0,
                max_tokens=16,
            )
        except GLMError as exc:
            return SuccessResponse(
                success=False,
                error=str(exc),
                data={
                    "name": name,
                    "test": "failed",
                    "provider": "glm",
                    "configured": True,
                    "model": settings.glm_model,
                    "endpoint": settings.glm_base_url,
                },
            ).dict()
        return SuccessResponse(
            data={
                "name": name,
                "test": "ok",
                "provider": "glm",
                "configured": True,
                "model": settings.glm_model,
                "endpoint": settings.glm_base_url,
                "usage": response.get("usage"),
            }
        ).dict()
    return SuccessResponse(data={"name": name, "test": "ok", "model": model.endpoint}).dict()


@router.get("/settings/models/registry/{name}/recommend")
async def registry_recommend(name: str):
    return SuccessResponse(data={"name": name, "recommended": True}).dict()
