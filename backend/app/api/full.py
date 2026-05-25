from datetime import datetime, timedelta
import hashlib
import json
import re
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.cache import cache_delete_pattern, cached
from app.core.config import settings
from app.core.db import SessionLocal, get_db
from app.db.models import (
    ActionItem,
    BacktestCase,
    Brief,
    CleanItem,
    InstitutionEvent,
    KnowledgeArticle,
    Opportunity,
    OpportunityAnalysis,
    OpportunityBoxItem,
    PipelineRun,
    RawItem,
    ScenarioHistory,
    ScenarioPreset,
    Signal,
    SourceStatus,
    UserPreference,
    UserProfile,
)
from app.schemas import (
    ActionItemPayload,
    ActionProgressPayload,
    ActionReviewPayload,
    OpportunityItem,
    OpportunityBoxPayload,
    OnboardingPayload,
    PipelineRunPayload,
    PreferencePayload,
    ScenarioAnalyzePayload,
    SuccessResponse,
    UserProfilePayload,
)
from app.services.real_pipeline import run_real_pipeline
from app.services.cache_warmup import invalidate_runtime_cache, warm_core_cache
from app.services.glm_client import GLMError, glm_is_configured, glm_json_completion

router = APIRouter()
DEFAULT_USER = "default"
FRESH_SOURCE_HOURS = 24
EXPIRED_SOURCE_HOURS = 72
STRONG_DEMAND_SOURCES = (
    "Amazon",
    "Apple App Store",
    "Google Play",
    "Google Trends",
    "Product Hunt",
    "Shopify",
)


async def _execute_pipeline_run(run_id: str, target_sources: list[str] | None = None) -> None:
    async with SessionLocal() as session:
        run = await session.get(PipelineRun, run_id)
        if not run:
            return
        try:
            summary = await run_real_pipeline(session, target_sources=target_sources)
            errors = summary.get("errors") or []
            run.status = "partial_failed" if errors else "success"
            run.finished_at = datetime.utcnow()
            target_note = (
                f"{len(target_sources or [])} target sources, "
                if target_sources
                else ""
            )
            run.message = (
                "real pipeline executed: "
                f"{target_note}"
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
            run.status = "failed"
            run.finished_at = datetime.utcnow()
            run.message = f"real pipeline failed: {exc}"
            await session.commit()


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


def _hours_since(value: datetime | None, now: datetime | None = None) -> float | None:
    if value is None:
        return None
    return round(((now or datetime.utcnow()) - value).total_seconds() / 3600, 1)


def _source_config_status(source: SourceStatus) -> str:
    if source.status == "restricted":
        return "restricted"
    if source.status == "third_party":
        return "third_party"
    if source.status == "needs_config" or source.freshness == "not_configured":
        return "needs_config"
    return "configured"


def _source_collection_status(source: SourceStatus) -> str:
    config_status = _source_config_status(source)
    if config_status != "configured":
        return "not_ready"
    if source.status in {"warning", "offline", "failed"} or source.freshness == "offline":
        notes = (source.notes or "").lower()
        if "rate" in notes or "429" in notes or "limit" in notes:
            return "rate_limited"
        if "captcha" in notes or "blocked" in notes or "robot" in notes:
            return "blocked"
        return "failed"
    if source.status in {"experimental", "degraded"}:
        return "degraded"
    return "healthy"


def _source_effective_freshness(source: SourceStatus, now: datetime | None = None) -> tuple[str, str | None]:
    config_status = _source_config_status(source)
    collection_status = _source_collection_status(source)
    if config_status != "configured":
        return "not_configured", "source is not configured for live collection"
    if collection_status in {"failed", "rate_limited", "blocked"}:
        return "unknown", "latest collection attempt failed; no successful freshness timestamp is tracked"
    age_hours = _hours_since(source.last_checked, now)
    if age_hours is None:
        return "unknown", "source has no collection timestamp"
    if age_hours > EXPIRED_SOURCE_HOURS:
        return "expired", f"source has not refreshed for {age_hours} hours"
    if age_hours > FRESH_SOURCE_HOURS:
        return "stale", f"source has not refreshed for {age_hours} hours"
    return "fresh", None


def _source_yield_status(source: SourceStatus) -> str:
    config_status = _source_config_status(source)
    collection_status = _source_collection_status(source)
    if config_status != "configured":
        return "not_applicable"
    if collection_status in {"failed", "rate_limited", "blocked", "not_ready"}:
        return "unknown"
    if int(source.signal_count_24h or 0) > 0:
        return "productive"
    return "no_new"


def _source_operational_state(source: SourceStatus, freshness: str | None = None) -> str:
    config_status = _source_config_status(source)
    collection_status = _source_collection_status(source)
    yield_status = _source_yield_status(source)
    freshness_status = freshness or _source_effective_freshness(source)[0]
    if config_status in {"needs_config", "third_party"}:
        return "configure_needed"
    if config_status == "restricted":
        return "restricted"
    if collection_status in {"rate_limited", "blocked"}:
        return collection_status
    if collection_status == "failed":
        return "retry_needed"
    if freshness_status == "expired":
        return "expired"
    if freshness_status == "stale":
        return "refresh_due"
    if freshness_status == "unknown":
        return "pending_sync"
    if yield_status == "no_new":
        return "no_new"
    if collection_status == "degraded":
        return "degraded"
    return "ready"


def _source_status_payload(source: SourceStatus, now: datetime | None = None) -> dict:
    payload = _serialize(source)
    freshness, reason = _source_effective_freshness(source, now)
    age_hours = _hours_since(source.last_checked, now)
    config_status = _source_config_status(source)
    collection_status = _source_collection_status(source)
    yield_status = _source_yield_status(source)
    operational_state = _source_operational_state(source, freshness)
    payload["freshness"] = freshness
    payload["effective_freshness"] = freshness
    payload["freshness_status"] = freshness
    payload["config_status"] = config_status
    payload["collection_status"] = collection_status
    payload["yield_status"] = yield_status
    payload["operational_state"] = operational_state
    payload["is_fresh"] = freshness == "fresh"
    payload["is_ready"] = operational_state == "ready"
    payload["age_hours"] = age_hours
    payload["freshness_reason"] = reason
    return payload


def _opportunity_sources(opportunity: Opportunity, signal: Signal | None = None) -> list[str]:
    dimensions = opportunity.dimensions or {}
    sources = dimensions.get("evidence_sources") or dimensions.get("sources") or []
    if isinstance(sources, str):
        sources = [sources]
    if not sources and signal is not None:
        sources = signal.sources or []
    return [str(source) for source in sources if source]


def _has_strong_demand_source(sources: list[str]) -> bool:
    return any(any(source.startswith(prefix) for prefix in STRONG_DEMAND_SOURCES) for source in sources)


def _opportunity_gate(
    opportunity: Opportunity,
    signal: Signal | None,
    source_statuses: dict[str, SourceStatus],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.utcnow()
    dimensions = opportunity.dimensions or {}
    sources = _opportunity_sources(opportunity, signal)
    evidence_count = max(
        len(sources),
        int(dimensions.get("evidence_count", 1) or 1),
    )
    matched_sources = [source_statuses[source] for source in sources if source in source_statuses]
    last_checked_values = [source.last_checked for source in matched_sources if source.last_checked]
    last_checked = max(last_checked_values) if last_checked_values else None
    if last_checked is None and opportunity.created_at:
        last_checked = opportunity.created_at
    age_hours = _hours_since(last_checked, now)
    source_freshness = [_source_effective_freshness(source, now)[0] for source in matched_sources]
    if not sources:
        evidence_freshness = "unknown"
    elif not matched_sources:
        evidence_freshness = "unknown" if age_hours is None else ("expired" if age_hours > EXPIRED_SOURCE_HOURS else "stale" if age_hours > FRESH_SOURCE_HOURS else "fresh")
    elif "expired" in source_freshness:
        evidence_freshness = "expired"
    elif "not_configured" in source_freshness or "unknown" in source_freshness:
        evidence_freshness = "unknown"
    elif "stale" in source_freshness:
        evidence_freshness = "stale"
    else:
        evidence_freshness = "fresh"

    blockers: list[str] = []
    if evidence_freshness != "fresh":
        blockers.append("核心证据源未在 24 小时内刷新")
    if evidence_count < 2 and not _has_strong_demand_source(sources):
        blockers.append("证据不足：需要至少 2 个来源或 1 个强需求/交易来源")
    if not (opportunity.strategies and len(opportunity.strategies) > 0):
        blockers.append("缺少明确的第一步验证动作")
    if not opportunity.estimated_investment or opportunity.estimated_investment in {"N/A", "--"}:
        blockers.append("缺少预算范围")
    if opportunity.risk_level == "high":
        blockers.append("风险等级过高，需先降级为观察")

    reasons: list[str] = []
    if evidence_freshness == "fresh":
        reasons.append("核心证据源 24 小时内已刷新")
    if evidence_count >= 2:
        reasons.append(f"{evidence_count} 个证据来源可交叉验证")
    elif _has_strong_demand_source(sources):
        reasons.append("包含强需求/交易类来源")
    if opportunity.strategies:
        reasons.append("已有可执行的最小验证步骤")
    if opportunity.estimated_investment:
        reasons.append("已有预算区间")

    if not blockers and opportunity.validation_score >= 70:
        stage = "executable"
    elif evidence_freshness != "expired" and len(blockers) <= 2:
        stage = "needs_validation"
    else:
        stage = "watch"

    return {
        "opportunity_stage": stage,
        "execution_gate_passed": stage == "executable",
        "execution_blockers": blockers,
        "execution_reasons": reasons,
        "evidence_freshness": evidence_freshness,
        "evidence_last_checked": last_checked,
        "evidence_age_hours": age_hours,
        "evidence_sources": sources,
        "evidence_count_effective": evidence_count,
    }


def _content_recency(published_at: datetime | None, now: datetime) -> tuple[str, float | None]:
    if published_at is None:
        return "unknown", None
    age_hours = _hours_since(published_at, now)
    if age_hours is None:
        return "unknown", None
    if age_hours <= 24:
        return "fresh", age_hours
    if age_hours <= 72:
        return "recent", age_hours
    if age_hours <= 168:
        return "stale", age_hours
    return "expired", age_hours


def _opportunity_evidence_time_payload(
    opportunity: Opportunity,
    signal: Signal | None = None,
    clean: CleanItem | None = None,
    raw: RawItem | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.utcnow()
    evidence_at = None
    if clean is not None and clean.published_at:
        evidence_at = clean.published_at
    elif raw is not None and raw.published_at:
        evidence_at = raw.published_at
    elif signal is not None and signal.created_at:
        evidence_at = signal.created_at
    elif opportunity.created_at:
        evidence_at = opportunity.created_at
    recency, content_age_hours = _content_recency(evidence_at, now)
    return {
        "data_type": "live" if opportunity.id.startswith("op-live-") else "demo",
        "evidence_published_at": evidence_at,
        "content_age_hours": content_age_hours,
        "content_recency": recency,
    }


def _compact_title(value: str | None, limit: int = 46) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: max(8, limit - 3)].rstrip()}..."


def _display_evidence_title(source: str, value: str | None) -> str:
    text = " ".join((value or "").split())
    localized_prediction = _localized_prediction_market_title(text)
    if localized_prediction:
        return localized_prediction
    if source.startswith("CoinGecko"):
        text = re.sub(r"\s+(trending|趋势ing)\s+on\s+CoinGecko\b", " 在 CoinGecko 热门", text, flags=re.IGNORECASE)
    if source.startswith("Google Trends"):
        text = text.replace("趋势ing", "趋势")
    return text


def _localized_source_name(source: str | None) -> str:
    text = _nonempty_text(source, "公开数据源")
    lower = text.lower()
    if "github" in lower:
        return "GitHub 开源社区"
    if "product hunt" in lower:
        return "Product Hunt 新品社区"
    if "google trends" in lower:
        return "Google Trends 搜索趋势"
    if "reddit" in lower:
        return "Reddit 垂直社区"
    if "coingecko" in lower:
        return "CoinGecko 加密市场"
    if "amazon" in lower:
        return "Amazon 电商平台"
    if "shopify" in lower:
        return "Shopify 独立站生态"
    if "app store" in lower:
        return "App Store 应用榜单"
    if "google play" in lower:
        return "Google Play 应用榜单"
    if "arxiv" in lower:
        return "arXiv 论文库"
    if "cisa" in lower:
        return "CISA 网络安全公告"
    if "sec edgar" in lower:
        return "SEC 披露文件"
    if "36kr" in lower:
        return "36Kr 创投新闻"
    if "gdacs" in lower or "usgs" in lower:
        return "灾害和供应链预警源"
    return text


def _translate_identifier_words(value: str) -> str:
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    words = re.sub(r"[^A-Za-z0-9]+", " ", words).split()
    glossary = {
        "ai": "AI",
        "api": "接口",
        "app": "应用",
        "agent": "智能体",
        "browser": "浏览器",
        "chat": "聊天",
        "cloud": "云",
        "code": "代码",
        "cube": "立方体",
        "data": "数据",
        "db": "数据库",
        "dev": "开发",
        "doc": "文档",
        "docs": "文档",
        "image": "图像",
        "kit": "工具包",
        "model": "模型",
        "monitor": "监控",
        "sandbox": "沙箱",
        "search": "搜索",
        "security": "安全",
        "server": "服务器",
        "tool": "工具",
        "tools": "工具",
        "video": "视频",
        "web": "网页",
        "workflow": "工作流",
    }
    translated = [glossary.get(word.lower(), "") for word in words]
    translated = [word for word in translated if word]
    return "".join(translated)


def _localized_object_label(source: str, value: str | None) -> str:
    text = _opportunity_object_label(source, value)
    lower_source = source.lower()
    repo_match = re.search(r"\b([A-Za-z][A-Za-z0-9_-]{2,})/([A-Za-z][A-Za-z0-9_.-]{2,})\b", text)
    if ("github" in lower_source or "open_source" in lower_source) and repo_match:
        owner, repo = repo_match.groups()
        owner_map = {
            "tencentcloud": "腾讯云",
            "microsoft": "微软",
            "google": "谷歌",
            "meta": "Meta",
            "facebook": "Meta",
            "openai": "OpenAI",
            "anthropic": "Anthropic",
            "apple": "苹果",
            "alibaba": "阿里巴巴",
            "bytedance": "字节跳动",
        }
        owner_label = owner_map.get(owner.lower(), "")
        repo_label = _translate_identifier_words(repo)
        if repo_label:
            return _compact_title(f"{owner_label}{repo_label}开源项目", 54)
        if owner_label:
            return _compact_title(f"{owner_label}开源项目", 54)
        return "开源项目产品化线索"
    return text


def _localized_playbook_name(playbook: str | None, playbook_name: str | None = None, source: str | None = None) -> str:
    text = f"{playbook or ''} {playbook_name or ''} {source or ''}".lower()
    if "prediction_market" in text or "prediction market" in text or "polymarket" in text:
        return "预测市场事件预警"
    if "open_source" in text or "github" in text:
        return "开源项目产品化"
    if "crypto" in text or "coingecko" in text:
        return "加密叙事监控"
    if "global_situation" in text or "bbc" in text or "al jazeera" in text or "gdelt" in text:
        return "国际局势影响清单"
    if "disruption" in text or "gdacs" in text or "usgs" in text:
        return "供应链风险预警"
    if "cyber" in text or "cisa" in text:
        return "安全修复服务机会"
    if "funding" in text or "institution" in text or "ipo" in text or "36kr" in text:
        return "投融资线索机会"
    if "app_trend" in text or "app store" in text or "google play" in text:
        return "应用榜单拆解"
    if "ecommerce" in text or "amazon" in text or "shopify" in text:
        return "电商选品验证"
    if "search" in text or "google trends" in text:
        return "搜索需求承接"
    if "community" in text or "reddit" in text:
        return "社区痛点产品化"
    if "research" in text or "arxiv" in text:
        return "技术转化验证"
    return _nonempty_text(playbook_name, "商业验证")


def _localized_prediction_market_title(value: str | None) -> str:
    text = " ".join((value or "").split())
    if not text:
        return ""
    lower = text.lower()
    if "hantavirus" in lower and "pandemic" in lower:
        return "2026 年汉坦病毒是否会被世界卫生组织正式定性为“大流行”？"
    if "u.s." in lower and "invade iran" in lower:
        return "2027 年前美国是否会入侵伊朗？"
    if "us x iran" in lower and "peace deal" in lower:
        date_match = re.search(r"by\s+(.+?)\??$", text, flags=re.IGNORECASE)
        deadline = f"在 {date_match.group(1)} 前" if date_match else "在指定期限前"
        return f"美国和伊朗是否会{deadline}达成永久和平协议？"
    if "prime minister of hungary" in lower:
        name_match = re.search(r"be\s+(.+?)\??$", text, flags=re.IGNORECASE)
        name = name_match.group(1).strip() if name_match else "某位候选人"
        return f"匈牙利下一任总理是否会是 {name}？"
    if "bernie sanders" in lower and "2028" in lower:
        return "伯尼·桑德斯是否会赢得 2028 年民主党总统候选人提名？"
    if lower.startswith("will "):
        cleaned = text.rstrip("?")
        cleaned = re.sub(r"^Will\s+", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.replace("U.S.", "美国").replace("US", "美国").replace("Iran", "伊朗")
        cleaned = cleaned.replace("before", "在此前").replace(" by ", " 在期限前 ")
        return _compact_title(f"预测问题：{cleaned} 是否会发生？", 72)
    return ""


def _localized_prediction_market_excerpt(title: str, content: str) -> str:
    localized_title = _localized_prediction_market_title(title) or title
    lower = f"{title} {content}".lower()
    if "hantavirus" in lower and "pandemic" in lower:
        return (
            "这条 Polymarket 盘口约定：如果世界卫生组织在 2026 年 12 月 31 日美东时间 23:59 前，"
            "在官方声明、报告、发布会或出版物中明确把汉坦病毒、汉坦病毒肺综合征、肾综合征出血热，"
            "或相关暴发称为“大流行”，盘口结算为 Yes；否则结算为 No。"
            "仅被宣布为“国际关注的突发公共卫生事件”还不够，必须同时被明确称为“大流行”。"
            "主要结算依据是世卫组织官方沟通，可信媒体共识只能作为辅助依据。"
        )
    if "polymarket" in lower or "resolve to" in lower:
        return (
            f"这条预测市场盘口交易的问题是「{localized_title}」。要关注的不是英文标题本身，"
            "而是盘口规则、概率变化、成交量、流动性和官方结算来源。"
            "如果这些指标连续变化，并且能映射到投研、采购、供应链、内容选题或风控动作，才可能变成商业机会。"
        )
    return content


def _core_topic_from_title(title: str | None) -> str:
    text = _nonempty_text(title)
    if "｜" in text:
        parts = [part.strip() for part in text.split("｜") if part.strip()]
        if len(parts) >= 2:
            return parts[1]
    return text


def _specific_prediction_action_summary(
    *,
    title_text: str,
    source_name: str,
    score: Any,
    validation_score: Any,
    window_hours: Any,
    budget: str,
    estimated_return: str,
    roi: str,
    breakeven: str,
    max_loss: str,
    gate: dict[str, Any] | None,
    risk_level: str,
) -> dict[str, Any]:
    core_title = _core_topic_from_title(title_text)
    localized_title = _localized_prediction_market_title(core_title) or core_title
    localized_title_sentence = localized_title if localized_title.endswith(("？", "?", "。")) else f"{localized_title}。"
    is_hantavirus = "汉坦病毒" in localized_title or "hantavirus" in core_title.lower()
    source_label = _localized_source_name(source_name)
    if is_hantavirus:
        topic = "汉坦病毒是否会被世卫组织正式定性为“大流行”"
        affected = "公共卫生、医疗防护用品、旅行保险、跨境供应链、宏观事件研究和内容选题"
        official_sources = "世卫组织官方沟通、各国疾控机构公告和可信媒体追踪"
    else:
        topic = localized_title
        affected = "投研、跨境经营、供应链、政策风险、内容选题或行业情绪"
        official_sources = "官方公告、主流新闻、行业数据和第二个独立市场信号"

    opportunity_text = (
        f"这条机会来自「{source_label}」上的预测盘口，核心问题是：{localized_title_sentence}"
        f"它不是让你去下注，也不是把英文标题翻译一下就当项目，而是把盘口里的概率、成交量、流动性和结算规则转成中文事件监控产品。"
        f"以这条线索为例，真正可卖的是一份围绕“{topic}”的持续跟踪页或简报：每天记录盘口概率变化，核对{official_sources}，"
        f"并把变化翻译成对{affected}的影响清单。"
        f"现阶段机会分 {score}、验证分 {validation_score}、窗口 {int(window_hours or 72)} 小时，说明它值得先做验证；"
        f"但如果找不到第二来源、官方触发条件没有进展，或者目标客户不需要这种提前量，就应该降级观察。"
    )
    info_gap = (
        f"信息差不在“{topic}一定会发生”这个结论，而在多数人还只看到英文盘口时，先看懂它的结算条件、概率变化和资金深度。"
        f"如果盘口概率、成交量或流动性连续变化，同时{official_sources}出现同向证据，就可以比普通新闻读者更早整理出行业影响、应对动作和客户名单。"
        f"如果这些指标只是单笔噪声，就不能包装成机会。"
    )
    what_to_sell = (
        f"卖一份中文事件监控页或周更简报：主题是“{topic}”，内容包括盘口概率曲线、成交量和流动性变化、官方触发条件核对、"
        f"相关行业影响清单、客户应对动作和“不成立时”的退出提示。"
    )
    who_pays = (
        "会付钱的人不是泛泛的“投资者”，而是需要提前做判断的人：事件驱动投研人员、跨境采购或卖家负责人、"
        "医疗防护/保险/旅行等相关业务负责人、以及需要快速写出可信专题的内容团队。"
    )
    first_step = (
        f"先做一页中文事件卡：写清楚「{localized_title}」的盘口规则、当前概率、成交量、流动性、结算来源和官方触发条件，"
        "再补 2 个非 Polymarket 来源，发给 5 个目标用户看他们是否愿意继续接收更新。"
    )
    validation_plan = [
        first_step,
        f"连续 24-72 小时记录盘口概率、成交量和流动性，判断变化是持续趋势还是单笔噪声。",
        f"核对{official_sources}，尤其确认是否有官方表述、监管动作或真实行业影响。",
        f"把影响拆成 3 类具体动作：谁需要关注、要查什么数据、如果概率继续上升可以做什么。",
        "用小样本客户访谈验证是否有人愿意为这类中文监控页、预警简报或行业影响清单付费。",
    ]
    no_go = [
        "只有 Polymarket 单一盘口，没有第二来源或官方信息补强。",
        "概率、成交量和流动性没有持续变化，只是短期噪声。",
        "无法把事件映射到具体客户动作，只能停留在猎奇新闻或下注讨论。",
        "目标用户看完中文事件卡后不愿意留下邮箱、转发、咨询或订阅。",
    ]
    action_plan = _action_plan_from_steps(validation_plan)
    return {
        "opportunity": opportunity_text,
        "info_gap": info_gap,
        "what_to_sell": what_to_sell,
        "who_pays": who_pays,
        "why_now": (
            f"现在值得看，是因为这条盘口已经有可观察的市场指标，并且验证窗口只有 {int(window_hours or 72)} 小时。"
            "越早把英文规则、官方触发条件和行业影响翻成中文行动清单，越可能在新闻扩散前拿到注意力。"
        ),
        "first_step": first_step,
        "validation_plan": validation_plan,
        "no_go_signals": no_go,
        "budget": budget,
        "estimated_return": estimated_return,
        "roi": roi,
        "breakeven": breakeven,
        "max_loss": max_loss,
        "decision_label": "先做证据补强和客户验证",
        "execution_stage": _nonempty_text((gate or {}).get("opportunity_stage"), "needs_validation"),
        "execution_gate_passed": bool((gate or {}).get("execution_gate_passed", False)),
        "blockers": _list_from_value((gate or {}).get("execution_blockers")),
        "reasons": _list_from_value((gate or {}).get("execution_reasons")),
        "risk_level": risk_level,
        "success_metric": "24-72 小时内至少拿到 5 个目标用户反馈，其中 1 个愿意继续接收更新、试用监控页或询问价格。",
        "fail_metric": "没有第二来源、盘口指标不连续、客户只觉得猎奇但没有决策动作。",
        "action_plan": action_plan,
    }


def _opportunity_theme(source: str, playbook: str, playbook_name: str = "") -> str:
    text = f"{source} {playbook} {playbook_name}".lower()
    if "cisa" in text or "cyber" in text:
        return "网络安全服务机会"
    if "gdacs" in text or "usgs" in text or "disaster" in text or "earthquake" in text:
        return "供应链风险机会"
    if "polymarket" in text or "prediction" in text:
        return "事件预警机会"
    if "coingecko" in text or "crypto" in text:
        return "加密叙事机会"
    if "gdelt" in text or "bbc" in text or "al jazeera" in text or "global_situation" in text:
        return "国际局势机会"
    if "sec edgar: form d" in text or "funding" in text:
        return "融资线索机会"
    if "sec edgar: 13f" in text or "institution" in text:
        return "机构持仓机会"
    if "sec edgar: s-1" in text or "ipo" in text:
        return "IPO 管线机会"
    if "36kr" in text:
        return "创投动向机会"
    if "amazon" in text or "shopify" in text or "ecommerce" in text:
        return "电商选品机会"
    if "app store" in text or "google play" in text or "app_trend" in text:
        return "应用拆解机会"
    if "google trends" in text or "search" in text:
        return "搜索需求机会"
    if "product hunt" in text or "product_launch" in text:
        return "新品拆解机会"
    if "reddit" in text or "community" in text:
        return "社区痛点机会"
    if "github" in text or "open_source" in text:
        return "开源产品化机会"
    if "arxiv" in text or "research" in text:
        return "技术转化机会"
    if "跨境爆品" in text:
        return "跨境选品机会"
    if "内容工作流" in text:
        return "内容工具机会"
    return "商业验证机会"


def _opportunity_action(source: str, playbook: str, playbook_name: str = "") -> str:
    text = f"{source} {playbook} {playbook_name}".lower()
    if "cisa" in text or "cyber" in text:
        return "做修复服务/替代方案"
    if "gdacs" in text or "usgs" in text or "disaster" in text or "earthquake" in text:
        return "做供应链风险预警"
    if "polymarket" in text or "prediction" in text:
        return "做事件监控/投研清单"
    if "coingecko" in text or "crypto" in text:
        return "做叙事监控/内容工具"
    if "bbc" in text or "al jazeera" in text or "gdelt" in text or "global_situation" in text:
        return "做行业影响清单"
    if "sec edgar: 13f" in text or "institution" in text:
        return "跟踪机构共识"
    if "sec edgar: s-1" in text or "ipo" in text:
        return "拆产业链/竞品"
    if "sec edgar: form d" in text or "funding" in text or "36kr" in text:
        return "找赛道和销售线索"
    if "amazon" in text:
        return "验证价格带/差评痛点"
    if "shopify" in text or "ecommerce" in text:
        return "验证供给和独立站卖点"
    if "app store" in text or "google play" in text or "app_trend" in text:
        return "拆功能缺口/垂直替代"
    if "google trends" in text or "search" in text:
        return "做落地页测需求"
    if "product hunt" in text or "product_launch" in text:
        return "拆竞品/做窄版替代"
    if "reddit" in text or "community" in text:
        return "访谈痛点/做 MVP"
    if "github" in text or "open_source" in text:
        return "封装托管版/行业版"
    if "arxiv" in text or "research" in text:
        return "做 Demo/行业验证"
    if "跨境爆品" in text:
        return "测素材/供应链/投放"
    if "内容工作流" in text:
        return "做模板/自动化工具"
    return "小成本验证"


def _opportunity_object_label(source: str, value: str | None) -> str:
    text = _display_evidence_title(source, value)
    replacements = (
        r"^(开源项目|新品发布|应用榜单|搜索趋势|论文方向|Amazon 商品|科技新闻|社区讨论|融资动向|机构持仓|IPO 管线)[：:]\s*",
        r"^(Product Launch|App Ranking|Search Trend)[：:]\s*",
    )
    for pattern in replacements:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    text = text.replace(" - ", " ").replace(" | ", " ")
    return _compact_title(text, 54)


def _opportunity_title_payload(
    opportunity: Opportunity,
    signal: Signal | None,
    clean: CleanItem | None = None,
    raw: RawItem | None = None,
) -> dict[str, Any]:
    metrics = clean.metrics if clean and clean.metrics else {}
    source = clean.source if clean else (signal.sources or ["未知来源"])[0] if signal else "未知来源"
    evidence_title = (
        metrics.get("title_zh")
        or (clean.title if clean else None)
        or (signal.title if signal else None)
        or metrics.get("title_original")
        or (raw.title if raw else None)
        or opportunity.playbook_name
    )
    original_title = metrics.get("title_original") or (raw.title if raw else None) or evidence_title
    display_title = _display_evidence_title(source, str(evidence_title or original_title or ""))
    theme = _opportunity_theme(source, opportunity.playbook, opportunity.playbook_name)
    target = _localized_object_label(source, display_title)
    action = _opportunity_action(source, opportunity.playbook, opportunity.playbook_name)
    title = f"{theme}｜{target}｜{action}"
    return {
        "title": title[:240],
        "business_title": title[:240],
        "evidence_title": display_title,
        "title_original": original_title,
        "source": source,
    }


def _field_value(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _nonempty_text(value: Any, fallback: str = "") -> str:
    text = " ".join(str(value or "").split())
    return text or fallback


def _action_plan_from_steps(steps: list[str]) -> list[dict[str, str]]:
    if not steps:
        steps = [
            "把机会写成一句客户能懂的话",
            "找 5 个目标客户做小样本验证",
            "做落地页、Demo、报告样张或服务包说明",
            "根据反馈决定继续、观察或放弃",
        ]
    return [
        {
            "label": step,
            "success_metric": (
                "能清楚说出卖什么、卖给谁、为什么付钱"
                if index == 0
                else "拿到真实点击、回复、收藏、询价、试用或付费意向"
            ),
        }
        for index, step in enumerate(steps)
    ]


def _action_summary_payload(
    opportunity: Any,
    *,
    signal: Signal | None = None,
    merchant_analysis: dict | None = None,
    gate: dict[str, Any] | None = None,
    source: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    merchant = merchant_analysis or {}
    playbook = _nonempty_text(_field_value(opportunity, "playbook"))
    source_name = _nonempty_text(source, "公开数据源")
    playbook_name = _localized_playbook_name(playbook, _field_value(opportunity, "playbook_name"), source_name)
    title_text = _display_evidence_title(source_name, _nonempty_text(title, playbook_name))
    lens = _playbook_lens(playbook, source_name)
    strategies = _list_from_value(_field_value(opportunity, "strategies"))
    validation_plan = _list_from_value(merchant.get("validation_plan")) or lens.get("validation") or strategies
    validation_plan = [str(item) for item in validation_plan if str(item).strip()]
    first_step = validation_plan[0] if validation_plan else (strategies[0] if strategies else "找 5 个目标客户做小样本验证")
    no_go = _list_from_value(merchant.get("no_go_signals")) or lens.get("no_go") or _list_from_value(_field_value(opportunity, "risk_factors"))
    if not no_go and _field_value(opportunity, "bear_case"):
        no_go = [_nonempty_text(_field_value(opportunity, "bear_case"))]
    no_go = [str(item) for item in no_go if str(item).strip()] or ["没有明确客户", "只有热度没有付费或采购意图"]
    blockers = _list_from_value((gate or {}).get("execution_blockers"))
    reasons = _list_from_value((gate or {}).get("execution_reasons"))
    stage = _nonempty_text((gate or {}).get("opportunity_stage"), "needs_validation")
    score = _field_value(opportunity, "score", 0)
    validation_score = _field_value(opportunity, "validation_score", 0)
    risk_level = _nonempty_text(_field_value(opportunity, "risk_level"), "medium")
    if stage == "executable":
        decision_label = "可以开始执行"
    elif stage == "needs_validation":
        decision_label = "先补验证再执行"
    else:
        decision_label = "先观察，不重投入"

    opportunity_text = (
        merchant.get("opportunity_summary")
        or f"这是一个「{playbook_name}」机会：把「{title_text}」转成客户能购买、订阅或用于决策的产品/服务。"
    )
    info_gap = (
        merchant.get("why_opportunity")
        or lens.get("opportunity_logic")
        or f"利用「{source_name}」提前暴露的需求、供给、价格或认知变化，在大众市场反应前做小成本验证。"
    )
    what_to_sell = merchant.get("what_to_sell") or (lens.get("monetization") or [playbook_name])[0]
    who_pays = merchant.get("who_pays") or "、".join((lens.get("customers") or ["目标行业用户"])[:3])
    why_now_items = _list_from_value(merchant.get("why_now"))
    why_now = why_now_items[0] if why_now_items else f"机会分 {score}，验证分 {validation_score}，窗口 {int(_field_value(opportunity, 'window_hours', 24) or 24)} 小时。"
    budget = _nonempty_text(_field_value(opportunity, "estimated_investment"), "小额预算")
    estimated_return = _nonempty_text(_field_value(opportunity, "estimated_return"), "待小样本验证")
    roi = _nonempty_text(_field_value(opportunity, "roi_ratio"), "待验证")
    breakeven = _nonempty_text(_field_value(opportunity, "breakeven"), "待验证")
    max_loss = _nonempty_text(_field_value(opportunity, "max_loss"), "先控制在可承受小额试错内")
    success_metric = "24-72 小时内拿到真实点击、回复、收藏、询价、试用或付费意向"

    if "polymarket" in source_name.lower() or "prediction" in playbook.lower():
        return _specific_prediction_action_summary(
            title_text=title_text,
            source_name=source_name,
            score=score,
            validation_score=validation_score,
            window_hours=_field_value(opportunity, "window_hours", 72),
            budget=budget,
            estimated_return=estimated_return,
            roi=roi,
            breakeven=breakeven,
            max_loss=max_loss,
            gate=gate,
            risk_level=risk_level,
        )

    topic_text = _core_topic_from_title(title_text)
    opportunity_text = (
        f"{opportunity_text} 原始线索来自「{_localized_source_name(source_name)}」，主题是「{topic_text}」。"
        f"这不是把热度标题直接当项目，而是把它拆成“谁有痛点、能卖什么、为什么现在验证、失败时怎么退出”。"
        f"当前可卖方向是：{what_to_sell}；目标客户是：{who_pays}。"
        f"第一步不要重投入，先用 {int(_field_value(opportunity, 'window_hours', 24) or 24)} 小时验证是否有人愿意点击、咨询、试用或付费。"
    )
    info_gap = (
        f"{info_gap} 具体利用方式是：先把来源里的英文、指标或原始讨论翻成客户能懂的中文问题，"
        f"再对照预算、ROI、风险和执行门槛判断能不能做成小产品、服务包或线索清单。"
        f"如果只能停留在“这个东西很热”，但说不出客户动作和付费理由，就不应该执行。"
    )
    what_to_sell = (
        f"{what_to_sell}。交付物要具体到客户能拿走使用：一页中文说明、一个最小 Demo、一个监控表、"
        "一份可联系名单、一个部署包或一个服务报价，而不是只给热度截图。"
    )
    who_pays = (
        f"{who_pays}。优先找已经有预算或时间压力的人，比如需要降低试错成本、缩短调研时间、"
        "找到替代方案、采购线索或可执行内容选题的团队。"
    )
    first_step = (
        f"{first_step}。执行时要把「{topic_text}」写成一页中文验证卡，包含客户问题、可卖方案、"
        "目标人群、价格假设、成功标准和放弃条件，然后发给 5 个真实目标用户。"
    )

    return {
        "opportunity": opportunity_text,
        "info_gap": info_gap,
        "what_to_sell": what_to_sell,
        "who_pays": who_pays,
        "why_now": why_now,
        "first_step": first_step,
        "validation_plan": validation_plan or strategies or [first_step],
        "no_go_signals": no_go,
        "budget": budget,
        "estimated_return": estimated_return,
        "roi": roi,
        "breakeven": breakeven,
        "max_loss": max_loss,
        "decision_label": decision_label,
        "execution_stage": stage,
        "execution_gate_passed": bool((gate or {}).get("execution_gate_passed", False)),
        "blockers": blockers,
        "reasons": reasons,
        "risk_level": risk_level,
        "success_metric": success_metric,
        "fail_metric": "曝光后无互动、目标客户不认痛点、毛利/交付/合规风险无法接受",
        "action_plan": _action_plan_from_steps(validation_plan or strategies or [first_step]),
    }


def _opportunity_detail_verdict(
    opportunity: Opportunity,
    signal: Signal | None,
    source_statuses: dict[str, SourceStatus],
    clean: CleanItem | None = None,
    raw: RawItem | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    gate = _opportunity_gate(opportunity, signal, source_statuses, now)
    title_payload = _opportunity_title_payload(opportunity, signal, clean, raw)
    metrics = clean.metrics if clean and clean.metrics else {}
    dimensions = opportunity.dimensions or {}
    source = title_payload.get("source") or (clean.source if clean else "") or "未知来源"
    display_title = title_payload.get("evidence_title") or title_payload.get("business_title") or opportunity.playbook_name
    source_list = dimensions.get("sources") or dimensions.get("evidence_sources") or metrics.get("evidence_sources") or ([source] if source else [])
    if isinstance(source_list, str):
        source_list = [source_list]
    source_list = [str(item) for item in source_list if item]
    evidence_count = max(len(source_list), int(dimensions.get("evidence_count") or metrics.get("evidence_count") or 1))
    rank = metrics.get("rank")
    volume = metrics.get("volume")
    liquidity = metrics.get("liquidity")
    metric_text = "、".join(
        item
        for item in [
            f"排名 {rank}" if rank not in (None, "") else "",
            f"成交量 {volume}" if volume not in (None, "") else "",
            f"流动性 {liquidity}" if liquidity not in (None, "") else "",
        ]
        if item
    ) or "缺少关键量化指标"
    prediction_text = f"{source} {_nonempty_text(opportunity.playbook)} {_nonempty_text(opportunity.playbook_name)}".lower()
    is_prediction_market = "polymarket" in prediction_text or "prediction" in prediction_text
    is_product_launch = "product hunt" in source.lower() or "product_launch" in prediction_text
    has_probability = any(
        key in metrics and metrics.get(key) not in (None, "")
        for key in ("probability", "yes_probability", "yes_price", "odds", "current_probability")
    )
    raw_payload = raw.payload if raw and raw.payload else {}
    content_text = _nonempty_text(
        metrics.get("content_zh"),
        _nonempty_text(metrics.get("content_original"), _nonempty_text(clean.summary if clean else "", raw.content if raw else "")),
    )
    content_original_text = _nonempty_text(metrics.get("content_original"), raw.content if raw else "")
    original_title = _nonempty_text(metrics.get("title_original"), raw.title if raw else "")

    if is_prediction_market and evidence_count < 2 and not has_probability:
        return {
            "analysis_version": "opportunity_verdict_v1",
            "label": "仅观察",
            "headline": "不是可直接执行机会，先当观察信号",
            "summary": "这条线索目前只是 Polymarket 单一来源盘口。缺当前 Yes 概率、连续变化和第二来源，不能直接包装成产品或开始执行。",
            "why": [
                f"证据是单一来源：{source}，还没有第二来源确认。",
                "缺当前 Yes 概率和 24 小时变化，无法判断是不是持续信号。",
                f"已有平台指标只有：{metric_text}，只能说明有人交易，不等于有客户需求。",
            ],
            "next_steps": [
                "补当前 Yes 概率、24 小时变化、成交量和流动性截图。",
                "查世卫组织、各国疾控或可信媒体，补至少 1 个第二来源。",
                "拿一页事实卡问 3 个目标客户：这个监控对你有没有决策价值。",
            ],
            "missing_evidence": [
                "当前 Yes 概率",
                "24 小时概率变化",
                "第二来源",
                "3 个目标客户反馈",
            ],
            "do_not_do": "不要写成已成立的商业机会，不要给价格，不要做医学判断，也不要把盘口当下注建议。",
            "evidence_facts": [
                {"label": "原始信号", "value": str(display_title)},
                {"label": "来源", "value": f"{source}（单一来源）"},
                {"label": "平台指标", "value": metric_text},
                {"label": "执行状态", "value": "证据不足，不能直接执行"},
            ],
        }

    if is_product_launch:
        product_name = _localized_object_label(source, original_title or str(display_title))
        lower_content = f"{content_text} {content_original_text}".lower()
        source_phrase = content_original_text or content_text
        is_agent_testing = "agent" in lower_content and ("gap" in lower_content or "gaps" in lower_content)
        if is_agent_testing:
            what_it_is = (
                f"Fabraix 是 Product Hunt 上的新产品线索。原始卖点是“{source_phrase}”，意思是在用户发现问题前，先找出 AI Agent 的缺口。"
                "它说明的不是“又一个 AI 工具很热”，而是 AI 客服、销售助手、内部流程助手上线前可能缺少测试和验收。"
            )
            why_it_matters = (
                "如果企业把 AI Agent 放到真实用户面前，失败场景往往由用户先撞出来。"
                "这里可验证的痛点是：团队是否愿意在上线前购买一套测试清单、评测服务或轻量工具，提前发现回答错误、流程断点和边界条件。"
            )
            opportunity_angle = (
                "可验证方向不是复制 Fabraix，而是做更窄的中文场景：AI 客服/销售 Agent 上线前测试清单、失败案例库、评测模板或人工评测服务。"
                "第一批只找已经在做 AI Agent 的 SaaS 团队、外包交付团队和企业内部自动化负责人。"
            )
            current_limit = (
                "现在还不能说机会成立，因为只有 Product Hunt 一条发布信息。缺少官网功能细节、定价、评论、投票、真实用户案例和竞品对比。"
            )
            next_steps = [
                "打开 Product Hunt 和官网，补产品功能、定价、评论、投票和截图。",
                "列 5 个正在做 AI 客服/销售/内部助手的团队，问他们上线前怎么测试 Agent。",
                "做一页 AI Agent 上线前测试清单，验证有没有人愿意试用或付费评测。",
            ]
            missing = ["官网功能细节", "定价", "Product Hunt 评论/投票", "3 个目标客户反馈"]
            key_question = "关键问题：做 AI Agent 的团队，是否愿意为上线前测试清单或人工评测服务付费？"
        else:
            what_it_is = (
                f"{product_name} 是 Product Hunt 上的新产品线索。当前只知道它发布了，以及一句产品描述：{content_text or '暂无描述'}。"
            )
            why_it_matters = "新品发布只能说明有人在做这个方向，不能直接说明客户愿意付费。它的价值在于拆出目标人群、核心卖点和评论里的未满足需求。"
            opportunity_angle = f"可验证方向是围绕「{product_name}」做竞品拆解，找一个更窄的人群或中文/行业场景做小样本验证。"
            current_limit = "当前缺官网功能、定价、评论、投票、竞品对比和目标客户反馈。"
            next_steps = [
                "打开原始链接，补功能、定价、评论、投票和截图。",
                "拆 3 个目标人群和 3 个使用场景。",
                "找 3 个目标客户确认这个痛点是否真实。",
            ]
            missing = ["官网功能细节", "定价", "评论/投票", "3 个目标客户反馈"]
            key_question = f"关键问题：{product_name} 暴露的痛点，是否在某个更窄人群里足够强？"
        return {
            "analysis_version": "opportunity_verdict_v1",
            "label": "需验证",
            "headline": f"{product_name} 是新品线索，先补详情再判断能不能做",
            "summary": what_it_is,
            "detail_story": {
                "what_it_is": what_it_is,
                "why_it_matters": why_it_matters,
                "opportunity_angle": opportunity_angle,
                "current_limit": current_limit,
            },
            "key_question": key_question,
            "why": [
                f"原始信号来自 Product Hunt：{content_text or str(display_title)}",
                "这是单一新品发布来源，不能直接证明需求成立。",
                current_limit,
            ],
            "next_steps": next_steps,
            "missing_evidence": missing,
            "do_not_do": "不要把 Product Hunt 发布当成已成立机会，不要直接复制产品，也不要在缺评论、定价和客户反馈时开始重投入。",
            "evidence_facts": [
                {"label": "原始信号", "value": str(display_title)},
                {"label": "一句话卖点", "value": content_text or "--"},
                {"label": "来源", "value": f"{source}（单一来源）"},
                {"label": "当前结论", "value": "需验证：先补产品详情和客户反馈"},
            ],
        }

    blockers = _list_from_value(gate.get("execution_blockers"))
    reasons = _list_from_value(gate.get("execution_reasons"))
    stage = _nonempty_text(gate.get("opportunity_stage"), "needs_validation")
    if stage == "executable":
        label = "可执行"
        headline = "可以小步执行，但仍要按证据推进"
        summary = "这条机会已有基本证据和下一步动作，可以进入小成本执行，不适合跳过验证重投入。"
    elif stage == "needs_validation":
        label = "需验证"
        headline = "先补验证，不要直接执行"
        summary = "这条机会有一定信号，但关键证据还不够。先验证客户、来源和成本，再决定是否执行。"
    else:
        label = "仅观察"
        headline = "证据不够，先观察"
        summary = "这条线索目前只能作为观察项。缺少足够来源、客户动作或可执行条件。"
    return {
        "analysis_version": "opportunity_verdict_v1",
        "label": label,
        "headline": headline,
        "summary": summary,
        "why": (blockers or reasons or ["证据、客户和执行路径仍需补齐"])[:4],
        "next_steps": _list_from_value(opportunity.strategies)[:3] or ["补证据", "问目标客户", "按反馈决定继续或放弃"],
        "missing_evidence": (blockers or ["目标客户反馈", "第二来源", "成本和回报验证"])[:4],
        "do_not_do": "不要把热度当结论，不要在证据不足时开始重投入。",
        "evidence_facts": [
            {"label": "原始信号", "value": str(display_title)},
            {"label": "来源", "value": "、".join(source_list[:3]) or source},
            {"label": "平台指标", "value": metric_text},
            {"label": "执行状态", "value": label},
        ],
    }


def _opportunity_payload(
    opportunity: Opportunity,
    signal: Signal | None,
    source_statuses: dict[str, SourceStatus],
    clean: CleanItem | None = None,
    raw: RawItem | None = None,
    now: datetime | None = None,
    merchant_analysis: dict | None = None,
) -> dict:
    payload = _serialize(opportunity)
    gate = _opportunity_gate(opportunity, signal, source_statuses, now)
    payload.update(gate)
    payload.update(_opportunity_evidence_time_payload(opportunity, signal, clean, raw, now))
    payload.update(_opportunity_title_payload(opportunity, signal, clean, raw))
    payload["playbook_name"] = _localized_playbook_name(opportunity.playbook, opportunity.playbook_name, payload.get("source"))
    payload["action_summary"] = _action_summary_payload(
        opportunity,
        signal=signal,
        merchant_analysis=merchant_analysis,
        gate=gate,
        source=payload.get("source"),
        title=payload.get("business_title") or payload.get("title"),
    )
    payload["detail_verdict"] = _opportunity_detail_verdict(
        opportunity,
        signal,
        source_statuses,
        clean,
        raw,
        now,
    )
    return payload


def _opportunity_list_payload(
    opportunity: Opportunity,
    analysis_title: str | None,
    analysis_evidence_title: str | None,
    analysis_source: str | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    payload = _serialize(opportunity)
    payload.update(_opportunity_gate(opportunity, None, {}, now))
    payload.update(_opportunity_evidence_time_payload(opportunity, None, None, None, now))

    dimensions = opportunity.dimensions or {}
    sources = dimensions.get("evidence_sources") or dimensions.get("sources") or []
    if isinstance(sources, str):
        sources = [sources]
    source = analysis_source or (sources[0] if sources else "")
    fallback_title = _opportunity_title_payload(opportunity, None).get("title") or opportunity.playbook_name
    title = analysis_title or fallback_title
    evidence_title = analysis_evidence_title or title

    payload.update(
        {
            "title": title,
            "business_title": title,
            "evidence_title": evidence_title,
            "title_original": evidence_title,
            "source": source,
        }
    )
    return payload


def _opportunity_list_payload_from_row(row, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.utcnow()
    dimensions = row.dimensions or {}
    sources = dimensions.get("evidence_sources") or dimensions.get("sources") or []
    if isinstance(sources, str):
        sources = [sources]
    sources = [str(source) for source in sources if source]
    source = row.analysis_source or (sources[0] if sources else "")
    evidence_count = max(len(sources), int(dimensions.get("evidence_count", 1) or 1))

    evidence_at = row.created_at
    content_recency, content_age_hours = _content_recency(evidence_at, now)
    evidence_age_hours = _hours_since(row.created_at, now) if row.created_at else None
    if not sources:
        evidence_freshness = "unknown"
    elif evidence_age_hours is None:
        evidence_freshness = "unknown"
    elif evidence_age_hours > EXPIRED_SOURCE_HOURS:
        evidence_freshness = "expired"
    elif evidence_age_hours > FRESH_SOURCE_HOURS:
        evidence_freshness = "stale"
    else:
        evidence_freshness = "fresh"

    blockers: list[str] = []
    if evidence_freshness != "fresh":
        blockers.append("核心证据源未在 24 小时内刷新")
    if evidence_count < 2 and not _has_strong_demand_source(sources):
        blockers.append("证据不足：需要至少 2 个来源或 1 个强需求/交易来源")
    if not (row.strategies and len(row.strategies) > 0):
        blockers.append("缺少明确的第一步验证动作")
    if not row.estimated_investment or row.estimated_investment in {"N/A", "--"}:
        blockers.append("缺少预算范围")
    if row.risk_level == "high":
        blockers.append("风险等级过高，需先降级为观察")

    reasons: list[str] = []
    if evidence_freshness == "fresh":
        reasons.append("核心证据源 24 小时内已刷新")
    if evidence_count >= 2:
        reasons.append(f"{evidence_count} 个证据来源可交叉验证")
    elif _has_strong_demand_source(sources):
        reasons.append("包含强需求/交易类来源")
    if row.strategies:
        reasons.append("已有可执行的最小验证步骤")
    if row.estimated_investment:
        reasons.append("已有预算区间")

    if not blockers and row.validation_score >= 70:
        stage_value = "executable"
    elif evidence_freshness != "expired" and len(blockers) <= 2:
        stage_value = "needs_validation"
    else:
        stage_value = "watch"

    raw_title = row.analysis_title or row.playbook_name or row.playbook or row.id
    evidence_title = _display_evidence_title(source, row.analysis_evidence_title or raw_title)
    title = (
        f"{_opportunity_theme(source, row.playbook, row.playbook_name)}｜"
        f"{_localized_object_label(source, evidence_title)}｜"
        f"{_opportunity_action(source, row.playbook, row.playbook_name)}"
    )
    gate = {
        "opportunity_stage": stage_value,
        "execution_gate_passed": stage_value == "executable",
        "execution_blockers": blockers,
        "execution_reasons": reasons,
        "evidence_freshness": evidence_freshness,
        "evidence_last_checked": row.created_at,
        "evidence_age_hours": evidence_age_hours,
        "evidence_sources": sources,
        "evidence_count_effective": evidence_count,
    }
    action_summary = _action_summary_payload(
        row,
        merchant_analysis=_field_value(row, "analysis_payload", {}) or {},
        gate=gate,
        source=source,
        title=title,
    )
    return {
        "id": row.id,
        "signal_id": row.signal_id,
        "score": row.score,
        "level": row.level,
        "playbook": row.playbook,
        "playbook_name": _localized_playbook_name(row.playbook, row.playbook_name, source),
        "window_hours": row.window_hours,
        "strategies": row.strategies or action_summary.get("validation_plan") or [],
        "crowding_score": row.crowding_score,
        "risk_level": row.risk_level,
        "risk_factors": _field_value(row, "risk_factors", []) or [],
        "bear_case": _field_value(row, "bear_case"),
        "validation_score": row.validation_score,
        "difficulty": row.difficulty,
        "estimated_investment": row.estimated_investment or action_summary.get("budget"),
        "estimated_return": _field_value(row, "estimated_return") or action_summary.get("estimated_return"),
        "roi_ratio": _field_value(row, "roi_ratio") or action_summary.get("roi"),
        "breakeven": _field_value(row, "breakeven") or action_summary.get("breakeven"),
        "max_loss": _field_value(row, "max_loss") or action_summary.get("max_loss"),
        "execution_status": row.execution_status,
        "current_step": row.current_step,
        "status": row.status,
        "created_at": row.created_at,
        "title": title,
        "business_title": title,
        "evidence_title": evidence_title,
        "title_original": evidence_title,
        "source": source,
        "data_type": "live" if row.id.startswith("op-live-") else "demo",
        "evidence_published_at": evidence_at,
        "content_age_hours": content_age_hours,
        "content_recency": content_recency,
        "action_summary": action_summary,
        **gate,
    }


def _response_success(data):
    return SuccessResponse(data=data).dict()


def _hash_id(prefix: str, value: str, length: int = 14) -> str:
    digest = hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:length]
    return f"{prefix}-{digest}"


async def _find_clean_for_signal(db, signal_id: str, signal: Signal | None = None) -> CleanItem | None:
    if signal is not None and signal.title:
        direct = (
            await db.execute(
                select(CleanItem)
                .where(CleanItem.title == signal.title)
                .order_by(CleanItem.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if direct is not None:
            return direct
    rows = (
        await db.execute(select(CleanItem).order_by(CleanItem.created_at.desc()).limit(180))
    ).scalars().all()
    for row in rows:
        if _hash_id("live", row.raw_item_id, 20) == signal_id:
            return row
    if signal is not None:
        normalized_signal = (signal.title or "").strip().lower()
        for row in rows:
            if normalized_signal and normalized_signal == (row.title or "").strip().lower():
                return row
    return None


def _hot_reasons(source: str, metrics: dict | None, signal: Signal | None, opportunity: Opportunity) -> list[str]:
    metrics = metrics or {}
    reasons: list[str] = []
    if metrics.get("stars"):
        reasons.append(f"GitHub Stars：{metrics.get('stars')}，说明开发者关注度较高")
    if metrics.get("forks"):
        reasons.append(f"Forks：{metrics.get('forks')}，说明有复用和二次开发迹象")
    if metrics.get("points"):
        reasons.append(f"Hacker News 热度：{metrics.get('points')} points")
    if metrics.get("comments"):
        reasons.append(f"讨论量：{metrics.get('comments')} 条评论，适合判断痛点强弱")
    if metrics.get("score"):
        reasons.append(f"社区评分：{metrics.get('score')}，代表平台内互动热度")
    if metrics.get("traffic"):
        reasons.append(f"搜索流量：{metrics.get('traffic')}，说明有主动搜索需求")
    if metrics.get("rank"):
        reasons.append(f"榜单排名：第 {metrics.get('rank')} 位，说明平台近期推力较强")
    if metrics.get("review_count"):
        reasons.append(f"评论数：{metrics.get('review_count')}，可用于拆解真实需求和差评痛点")
    if metrics.get("variants"):
        reasons.append(f"商品变体：{metrics.get('variants')} 个，说明供给侧可拆分测试")
    if metrics.get("min_price"):
        reasons.append(f"最低价格：{metrics.get('min_price')}，可估算测试成本和价格带")
    evidence_count = int(metrics.get("evidence_count", 1) or 1)
    if evidence_count > 1:
        reasons.append(f"{evidence_count} 个来源形成交叉验证，可信度高于单一平台信号")
    if signal is not None:
        reasons.append(f"系统信号分：{signal.score}，等级 {signal.level}，窗口 {signal.window}")
    reasons.append(f"机会评分：{opportunity.score}，验证分：{opportunity.validation_score}")
    return reasons[:8]


def _metric_percent(dimensions: dict | None, key: str, fallback: float = 0.5) -> int:
    value = (dimensions or {}).get(key, fallback)
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = fallback
    if number <= 1:
        number *= 100
    return max(0, min(100, int(round(number))))


def _clip_text(value: Any, limit: int = 900) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: max(40, limit - 3)].rstrip()}..."


def _first_payload_value(*payloads: dict | None, keys: list[str]) -> Any:
    for payload in payloads:
        if not payload:
            continue
        for key in keys:
            value = payload.get(key)
            if value not in (None, "", [], {}):
                return value
    return None


def _source_record_type(source: str, topic: str = "") -> str:
    text = f"{source} {topic}".lower()
    if "github" in text:
        return "GitHub 开源仓库"
    if "reddit" in text:
        return "社区帖子"
    if "product hunt" in text:
        return "新品发布"
    if "app store" in text or "google play" in text:
        return "应用榜单/应用详情"
    if "amazon" in text or "shopify" in text:
        return "商品/店铺记录"
    if "google trends" in text:
        return "搜索趋势记录"
    if "polymarket" in text:
        return "预测市场盘口"
    if "coingecko" in text:
        return "加密资产热榜"
    if "cisa" in text:
        return "网络安全公告"
    if "gdacs" in text or "usgs" in text:
        return "灾害/地理事件记录"
    if "sec edgar" in text or "13f" in text or "form d" in text or "s-1" in text:
        return "监管披露文件"
    if "36kr" in text or "bbc" in text or "al jazeera" in text or "techcrunch" in text:
        return "新闻/快讯文章"
    return "原始平台记录"


def _business_model_label(playbook: str, source: str) -> str:
    text = f"{playbook} {source}".lower()
    if "github" in text or "open_source" in text:
        return "托管 SaaS / 部署集成 / 行业模板"
    if "polymarket" in text or "prediction" in text:
        return "事件监控订阅 / 投研简报 / 风险预警"
    if "global_situation" in text or "bbc" in text or "al jazeera" in text:
        return "行业情报 / 供应链影响清单 / 专题报告"
    if "cisa" in text or "cyber" in text:
        return "修复服务包 / 替代方案 / 安全监控"
    if "amazon" in text or "shopify" in text or "ecommerce" in text:
        return "选品报告 / 小批量测试 / 供应链撮合"
    if "app store" in text or "google play" in text or "app_trend" in text:
        return "垂直替代应用 / 插件模板 / 竞品拆解"
    if "google trends" in text or "search" in text:
        return "关键词落地页 / 线索获客 / 内容转化"
    if "reddit" in text or "community" in text:
        return "MVP 工具 / 服务包 / 咨询线索"
    if "funding" in text or "institution" in text or "ipo" in text or "36kr" in text:
        return "销售线索 / 赛道研究 / 上下游名单"
    return "信息服务 / 工具订阅 / 线索获客 / 小型服务包"


def _source_record_payload(
    *,
    opportunity: Opportunity,
    signal: Signal | None,
    source: str,
    title_zh: str,
    title_original: str,
    content_zh: str,
    content_original: str,
    clean_metrics: dict,
    raw_payload: dict,
    clean: CleanItem | None,
    raw: RawItem | None,
) -> dict[str, Any]:
    topic = clean.topic if clean else signal.type if signal else ""
    record_type = _source_record_type(source, topic)
    display_title = _display_evidence_title(source, title_zh or title_original)
    original_title = title_original or title_zh
    raw_content = content_zh or content_original or clean_metrics.get("description") or raw_payload.get("description") or ""
    content = _localized_prediction_market_excerpt(title_zh or title_original or display_title, raw_content)
    original_content = content_original or content_zh or raw_payload.get("description") or ""
    author = _first_payload_value(raw_payload, clean_metrics, keys=["author", "user", "username", "owner", "publisher", "organization"])
    platform_id = _first_payload_value(raw_payload, clean_metrics, keys=["id", "slug", "market_id", "symbol", "ticker", "repository", "repo"])
    published_at = clean.published_at if clean else raw.published_at if raw else None
    fetched_at = raw.fetched_at if raw else None
    metric_keys = [
        "stars",
        "forks",
        "open_issues",
        "points",
        "comments",
        "rank",
        "traffic",
        "review_count",
        "rating",
        "price",
        "min_price",
        "volume",
        "liquidity",
        "probability",
        "yes_price",
        "market_cap_rank",
        "score",
    ]
    key_metrics = {
        key: _first_payload_value(clean_metrics, raw_payload, keys=[key])
        for key in metric_keys
        if _first_payload_value(clean_metrics, raw_payload, keys=[key]) not in (None, "", [], {})
    }
    topics = _first_payload_value(raw_payload, clean_metrics, keys=["topics", "tags", "categories", "keywords"])
    language = _first_payload_value(clean_metrics, raw_payload, keys=["language"])
    if topics:
        key_metrics["topics"] = topics
    if language:
        key_metrics["language"] = language

    signal_fact = f"系统采集到一条来自「{source}」的{record_type}，主体是「{display_title or original_title}」。"
    if content:
        signal_fact += f" 内容要点：{_clip_text(content, 180)}"
    return {
        "record_type": record_type,
        "source": source,
        "url": clean.url if clean else raw.url if raw else None,
        "platform_id": platform_id,
        "author": author,
        "published_at": published_at,
        "fetched_at": fetched_at,
        "title": display_title,
        "title_original": original_title,
        "content_excerpt": _clip_text(content, 1000),
        "content_original_excerpt": _clip_text(original_content, 1000),
        "key_metrics": key_metrics,
        "signal_fact": signal_fact,
        "business_model": _business_model_label(opportunity.playbook, source),
        "system_interpretation": f"系统把这条{record_type}映射到「{_localized_playbook_name(opportunity.playbook, opportunity.playbook_name, source)}」，不是把原文直接当项目，而是把原文中的需求、风险、资金流或注意力变化转成可验证假设。",
    }


def _business_frame(playbook: str, source: str, title: str, lens: dict[str, Any]) -> dict[str, str]:
    text = f"{playbook} {source} {lens.get('plain_type', '')}".lower()
    target = _compact_title(_display_evidence_title(source, title), 72) or "这条信号"
    customers = "、".join(lens.get("customers", [])[:2]) or "目标客户"
    if "crypto" in text or "coingecko" in text:
        offer = f"围绕「{target}」做叙事监控、研究简报或风险提醒"
        pay_reason = "用户不是为涨跌本身付费，而是为更早发现叙事、资金注意力和风险变化付费。"
        first_test = "先做一个专题页或微信群简报，连续 3 天记录价格、搜索、社媒和新闻变化，看是否有人收藏、转发或愿意订阅。"
        not_this = "不是让你直接买入这个币，也不是做喊单。"
    elif "prediction" in text or "polymarket" in text:
        offer = f"围绕「{target}」做中文事件监控页：跟踪盘口概率、成交量、流动性、官方结算条件和行业影响动作"
        pay_reason = "投研、采购、跨境和内容团队不是为英文盘口本身付费，而是为更早看懂概率变化、官方触发条件和可执行影响链路付费。"
        first_test = f"先做一页中文事件卡，写清楚「{target}」的规则、当前概率、成交量、流动性、官方来源和可能影响的人群，再发给 5 个目标用户看是否愿意继续跟踪。"
        not_this = "不是让你去下注，而是把市场概率转成经营决策信息。"
    elif "global_situation" in text or "bbc" in text or "al jazeera" in text or "gdelt" in text:
        offer = f"把「{target}」转成受影响行业、地区、商品和供应链动作清单"
        pay_reason = "跨境卖家、采购和投研人员需要知道新闻会不会影响价格、渠道、交付或监管。"
        first_test = "先列出 3 个受影响行业和 10 个可能受影响公司/商品，做成短报告发给目标客户测试回复率。"
        not_this = "不是复述国际新闻，而是找新闻背后的价格、供应、渠道或政策变化。"
    elif "disruption" in text or "gdacs" in text or "usgs" in text:
        offer = f"围绕「{target}」做物流、供应、保险、本地服务的风险预警"
        pay_reason = "受影响地区的商家和采购团队需要替代供应、交付预案和风险提醒。"
        first_test = "先定位受影响城市、港口或供应链节点，再联系 5 个相关商家确认是否需要替代方案或信息提醒。"
        not_this = "不是灾难营销，只做合法、合规、帮助型的风险信息和替代方案。"
    elif "cyber" in text or "cisa" in text:
        offer = f"把「{target}」包装成修复服务包、替代方案清单或漏洞监控提醒"
        pay_reason = "使用受影响产品的企业需要降低停机、合规和安全事故风险。"
        first_test = "先确认受影响厂商和客户行业，写一页修复清单，定向触达 5-10 个 IT/安全负责人。"
        not_this = "不是泛泛讲安全新闻，而是围绕具体厂商、产品和修复动作。"
    elif "funding" in text or "institution" in text or "ipo" in text or "36kr" in text:
        offer = f"围绕「{target}」做赛道研究、销售线索、上下游供应商清单或竞品替代方案"
        pay_reason = "资本动作通常意味着预算、招聘、采购或产业链资源正在流入，B2B 服务商和投研人员会关注。"
        first_test = "先确认主体、投资方、产品和扩张动作，整理 10 个可跟进公司或客户名单。"
        not_this = "不是只看这家公司股票，而是拆它背后的赛道、客户和供应链机会。"
    elif "open_source" in text or "github" in text:
        offer = f"把「{target}」封装成托管版、部署服务、行业模板或中文化交付"
        pay_reason = "开发者关注说明能力有需求，非技术团队或企业客户会为省部署、省维护、省集成付费。"
        first_test = "先复现核心功能，找 issue 里的高频痛点，做一个最小 demo 或部署包测试咨询。"
        not_this = "不是照搬开源项目，而是把难用的技术能力变成可购买的服务。"
    elif "app_trend" in text or "app store" in text or "google play" in text:
        offer = f"拆解「{target}」的功能、评价和获客点，做垂直替代、插件或本地化版本"
        pay_reason = "榜单应用证明用户正在下载或使用，机会在未满足的人群、差评痛点和垂直场景。"
        first_test = "先看评论和功能缺口，做一张竞品拆解表，再用落地页或原型测试 20 个目标用户。"
        not_this = "不是复制整个应用，而是找它没服务好的细分人群。"
    elif "ecommerce" in text or "amazon" in text or "shopify" in text or "跨境" in text:
        offer = f"围绕「{target}」做选品、价格带、差评痛点、素材和供应链验证"
        pay_reason = "商品信号说明某个需求或供给正在出现，商家愿意为更快找到可卖点和测试路径付费。"
        first_test = "先查价格带、差评、同款供应和广告素材，用小预算测点击、收藏或询盘。"
        not_this = "不是看到商品就囤货，而是先验证需求、毛利和供应稳定性。"
    elif "search" in text or "google trends" in text:
        offer = f"把「{target}」做成关键词页、内容专题、工具入口或线索捕获页"
        pay_reason = "主动搜索代表用户已经在表达需求，机会在承接搜索意图并转成咨询、订阅或交易。"
        first_test = "先做一个落地页或内容页，投少量流量或发到相关渠道，看点击、停留和咨询。"
        not_this = "不是追热词写泛内容，而是承接一个明确搜索意图。"
    elif "community" in text or "reddit" in text:
        offer = f"把「{target}」里的抱怨、求助或讨论转成 MVP、服务包或内容获客"
        pay_reason = "社区讨论里如果有人反复表达痛点，说明可能存在尚未被产品满足的需求。"
        first_test = "先提炼 3 个痛点，私信或评论访谈 5 个用户，再做一个最小方案测试。"
        not_this = "不是把帖子当新闻，而是验证帖子背后的真实痛点和付费意愿。"
    elif "research" in text or "arxiv" in text:
        offer = f"把「{target}」转成行业 demo、技术咨询、数据集或自动化工具"
        pay_reason = "论文说明新能力正在出现，企业会为能落地到业务场景的演示和集成付费。"
        first_test = "先做一个可演示 demo，选 1 个垂直行业场景，找 3 个潜在客户验证是否有预算。"
        not_this = "不是收藏论文，而是验证这项技术能不能解决真实业务问题。"
    else:
        offer = f"把「{target}」转成一个可验证的小产品、服务包或线索清单"
        pay_reason = "只要它能对应到明确人群、明确痛点和明确动作，就可能从信息差变成商业机会。"
        first_test = "先找 5 个目标用户确认问题是否存在，再用落地页、样品或咨询清单测试付费意向。"
        not_this = "不是把热度当结论，而是把热度当待验证的商业假设。"

    return {
        "opportunity_summary": f"这是一个{offer}的机会，主要服务于 {customers}。",
        "what_to_sell": offer,
        "who_pays": customers,
        "why_they_pay": pay_reason,
        "first_test": first_test,
        "not_the_opportunity": not_this,
        "decision_question": "接下来最该回答的问题：有没有明确客户愿意为这个信息、工具、服务或替代方案付费？",
    }


def _playbook_lens(playbook: str, source: str) -> dict[str, Any]:
    text = f"{playbook} {source}".lower()
    if "crypto" in text or "coingecko" in text:
        return {
            "plain_type": "加密市场叙事信号",
            "opportunity_logic": "热门资产本身不等于可买入标的，但它会暴露资金、社区和搜索注意力正在聚集的主题。真正的商业机会通常在工具、内容、社群、数据监控、风控和 B2B 服务侧。",
            "customers": ["加密投资者", "研究员和内容团队", "交易社群", "风控/监控工具用户"],
            "monetization": ["主题研究报告", "监控面板订阅", "社群线索", "风控工具或 API"],
            "validation": ["拆出资产背后的叙事关键词", "检查搜索、社媒、开发者活动是否同步升温", "做一页专题/监控页测试收藏和订阅", "避免直接重仓交易，先验证信息服务需求"],
            "no_go": ["只有单日价格波动，没有搜索或社区跟进", "流动性很差或容易被操纵", "用户只关心短线喊单，不愿意为工具/内容付费"],
        }
    if "prediction" in text or "polymarket" in text:
        return {
            "plain_type": "预测市场领先信号",
            "opportunity_logic": "预测市场把分散信息压缩成概率和交易量。机会不一定是下注，而是利用概率变化提前准备供应链、内容、采购、投研或风控动作。",
            "customers": ["投资研究者", "跨境商家", "供应链团队", "新闻/内容团队"],
            "monetization": ["事件监控简报", "行业预警服务", "交易/采购决策支持", "垂直内容订阅"],
            "validation": ["看概率是否连续变化，而不是单笔噪声", "找官方新闻或市场数据交叉验证", "列出会受影响的国家、行业、商品和公司", "用小样本客户访谈验证这个预警是否有决策价值"],
            "no_go": ["成交量很低", "事件无法映射到商业动作", "没有第二来源确认"],
        }
    if "global_situation" in text or "bbc" in text or "al jazeera" in text or "gdelt" in text:
        return {
            "plain_type": "国际局势/宏观事件信号",
            "opportunity_logic": "国际新闻本身不是项目，项目来自它引发的价格、供应、渠道、监管、情绪或需求变化。要把事件映射到行业、地区、商品、服务和客户预算。",
            "customers": ["跨境卖家", "外贸/采购团队", "投研人员", "行业内容团队"],
            "monetization": ["行业情报简报", "采购替代清单", "风险预警服务", "专题内容和线索获客"],
            "validation": ["判断受影响地区和行业", "查是否会影响价格、交付、监管或消费心理", "找 2 个市场数据或官方来源确认", "做一份小型清单/报告给目标客户测试回复率"],
            "no_go": ["只是大新闻但没有商业链路", "影响太泛，无法落到具体客户", "没有时效优势"],
        }
    if "disruption" in text or "gdacs" in text or "usgs" in text:
        return {
            "plain_type": "灾害/供应链扰动信号",
            "opportunity_logic": "灾害信号的价值在于提前识别物流、工厂、保险、旅游、维修、替代供应等短期需求或风险。必须只做合法、合规、帮助型服务。",
            "customers": ["物流与采购团队", "保险/风控团队", "本地服务商", "跨境卖家"],
            "monetization": ["供应链风险提醒", "替代供应商清单", "本地服务线索", "风险地图/监控订阅"],
            "validation": ["定位受影响城市、港口、工厂或旅游区", "查物流和本地新闻确认影响范围", "列出可能出现缺口的商品或服务", "联系 5 个相关商家验证是否需要信息或替代方案"],
            "no_go": ["没有实际商业影响", "只能靠灾难营销", "信息滞后或无法验证"],
        }
    if "cyber" in text or "cisa" in text:
        return {
            "plain_type": "网络安全/供应商风险信号",
            "opportunity_logic": "安全公告意味着某些软件、供应商或客户群体短期会产生修复、替代、审计、培训和采购需求。机会在服务包装、工具监控、内容获客和替代方案。",
            "customers": ["中小企业 IT 负责人", "安全服务商", "采购/合规团队", "使用受影响产品的公司"],
            "monetization": ["修复服务包", "漏洞监控订阅", "替代供应商清单", "安全内容获客"],
            "validation": ["识别受影响厂商和产品", "确认漏洞严重性和利用成熟度", "列出目标客户行业", "发 5-10 条定向触达测试是否有人需要修复/咨询"],
            "no_go": ["公告影响面很小", "没有明确受影响客户", "需要高资质交付但自己没有能力"],
        }
    if "funding" in text or "institution" in text or "ipo" in text or "36kr" in text:
        return {
            "plain_type": "投资/融资动向信号",
            "opportunity_logic": "资本动作代表某个赛道正在获得预算、资源或退出预期。机会不只是投这家公司，也包括找供应商机会、替代方案、内容选题、招聘和产业链服务。",
            "customers": ["投资研究者", "创业者", "B2B 服务商", "产业链供应商"],
            "monetization": ["赛道研究", "销售线索", "竞品替代方案", "产业链名单/报告"],
            "validation": ["确认融资主体、金额、轮次和投资方", "看公司招聘、产品和客户是否扩张", "找上下游服务缺口", "沉淀 10 个可跟进公司或客户名单"],
            "no_go": ["只有融资新闻，没有产品或客户证据", "赛道过热且拥挤", "无法接触到可服务客户"],
        }
    if "open_source" in text or "github" in text:
        return {
            "plain_type": "开源项目产品化信号",
            "opportunity_logic": "开源热度说明开发者已经在关注或复用某个能力。商业机会在于把技术能力包装成托管服务、模板、行业版本、中文化交付或非技术用户可用的产品。",
            "customers": ["开发团队", "中小企业", "非技术运营人员", "垂直行业团队"],
            "monetization": ["托管版 SaaS", "部署/集成服务", "模板和插件", "行业版封装"],
            "validation": ["复现核心功能", "看 issue/讨论区里的痛点", "找 3 个同类商业产品对比定价", "做一个最小 demo 测试试用和咨询"],
            "no_go": ["只有星标没有真实使用", "维护成本太高", "已有巨头产品覆盖且差异化不足"],
        }
    if "app_trend" in text or "app store" in text or "google play" in text:
        return {
            "plain_type": "应用榜单/产品拆解信号",
            "opportunity_logic": "应用上榜说明用户正在下载、尝试或讨论某类功能。商业机会通常在差评痛点、垂直场景、本地化替代、插件化能力和获客素材侧。",
            "customers": ["垂直行业用户", "移动应用团队", "独立开发者", "增长团队"],
            "monetization": ["垂直替代应用", "插件/模板", "本地化版本", "竞品拆解报告"],
            "validation": ["看评论和差评痛点", "拆核心功能和获客文案", "找一个细分人群做原型", "用落地页或小样本访谈测试需求"],
            "no_go": ["只是平台推荐没有用户痛点", "完整复制成本太高", "没有细分场景差异化"],
        }
    if "ecommerce" in text or "amazon" in text or "shopify" in text or "跨境" in text:
        return {
            "plain_type": "电商/选品供需信号",
            "opportunity_logic": "商品、独立站或短视频电商信号说明某个需求、价格带或素材方向正在出现。机会在差评痛点、供给缺口、组合包装、内容素材和小批量测试。",
            "customers": ["跨境卖家", "供应链团队", "投放团队", "选品服务商"],
            "monetization": ["选品报告", "小批量商品测试", "素材/投放服务", "供应链撮合"],
            "validation": ["验证价格带和毛利", "看差评和问答痛点", "找同款供应稳定性", "用小预算测试点击、收藏或询盘"],
            "no_go": ["毛利太低", "供应不稳定", "只靠单个平台短期热度", "侵权或合规风险高"],
        }
    if "search" in text or "google trends" in text:
        return {
            "plain_type": "搜索需求信号",
            "opportunity_logic": "搜索上升说明用户主动表达需求。机会在承接搜索意图，做内容页、工具入口、咨询线索、联盟转化或垂直产品验证。",
            "customers": ["有明确问题的搜索用户", "内容/SEO 团队", "线索获客团队", "垂直服务商"],
            "monetization": ["关键词落地页", "咨询线索", "工具订阅", "内容转化"],
            "validation": ["拆关键词意图", "做一个承接页", "测试点击和咨询", "补竞品和搜索结果分析"],
            "no_go": ["热词很泛没有交易意图", "搜索量短期噪声", "无法承接用户下一步动作"],
        }
    if "community" in text or "reddit" in text:
        return {
            "plain_type": "社区痛点信号",
            "opportunity_logic": "社区里的抱怨、求助和讨论比新闻更接近真实需求。机会在把反复出现的痛点做成 MVP、服务包、内容入口或咨询线索。",
            "customers": ["发帖求助的人群", "垂直社区用户", "创业者", "运营/增长团队"],
            "monetization": ["MVP 工具", "服务包", "付费社群/内容", "咨询线索"],
            "validation": ["提炼高频痛点", "访谈 5 个用户", "做最小方案", "看是否愿意留下邮箱或付费试用"],
            "no_go": ["只是闲聊没有痛点", "用户没有预算", "痛点无法产品化或服务化"],
        }
    if "research" in text or "arxiv" in text:
        return {
            "plain_type": "技术转化信号",
            "opportunity_logic": "论文或技术热度说明新能力出现，但商业价值来自把能力落到行业任务、数据、流程和可演示结果上。",
            "customers": ["行业技术团队", "AI 产品团队", "咨询/集成商", "研究型企业"],
            "monetization": ["行业 demo", "技术咨询", "数据/模型服务", "自动化工具"],
            "validation": ["复现最小 demo", "选一个行业场景", "找客户确认预算", "比较现有方案成本"],
            "no_go": ["只能停留在论文", "推理或部署成本太高", "没有明确业务场景"],
        }
    return {
        "plain_type": "商业信号",
        "opportunity_logic": "系统把公开数据源中的热度、时效、供需、竞争和执行难度转成一个可验证假设。它不是最终项目结论，而是值得用小成本继续验证的商业线索。",
        "customers": ["目标行业用户", "内容/投研团队", "中小商家", "垂直服务商"],
        "monetization": ["信息差服务", "工具订阅", "线索获客", "小型服务包"],
        "validation": ["确认真实受众是谁", "找到至少 2 个额外证据源", "做落地页、内容页或小样本触达", "用点击、收藏、咨询或付费意向决定是否继续"],
        "no_go": ["没有明确客户", "不能转成可执行动作", "只有热度没有付费或采购意图"],
    }


def _merchant_analysis_payload(
    *,
    opportunity: Opportunity,
    signal: Signal | None,
    source: str,
    title: str,
    summary: str,
    metrics: dict | None,
) -> dict[str, Any]:
    dimensions = opportunity.dimensions or {}
    lens = _playbook_lens(opportunity.playbook, source)
    demand = _metric_percent(dimensions, "demand", 0.55)
    momentum = _metric_percent(dimensions, "momentum", 0.55)
    execution = _metric_percent(dimensions, "execution", 0.55)
    competition = _metric_percent(dimensions, "competition_adjusted", 0.5)
    evidence_count = int(dimensions.get("evidence_count") or (metrics or {}).get("evidence_count") or 1)
    source_list = dimensions.get("sources") or (metrics or {}).get("evidence_sources") or ([source] if source else [])
    summary_text = summary.strip() if summary else title
    if len(summary_text) > 220:
        summary_text = f"{summary_text[:217].rstrip()}..."
    frame = _business_frame(opportunity.playbook, source, title, lens)
    localized_playbook = _localized_playbook_name(opportunity.playbook, opportunity.playbook_name, source)
    why = [
        f"需求分 {demand}/100、动量分 {momentum}/100，说明这条线索不是纯静态新闻，而是有近期关注或需求变化。",
        f"执行分 {execution}/100、竞争缓冲 {competition}/100，适合先做轻量验证，而不是一上来重投入。",
        f"当前有 {evidence_count} 个证据源：{'、'.join(source_list[:4]) if source_list else source}。",
    ]
    prediction_text = f"{source} {_nonempty_text(opportunity.playbook)}".lower()
    is_prediction_market = "polymarket" in prediction_text or "prediction" in prediction_text
    if is_prediction_market:
        action_summary = _action_summary_payload(
            opportunity,
            signal=signal,
            source=source,
            title=title,
        )
        localized_title = _localized_prediction_market_title(_core_topic_from_title(title)) or _core_topic_from_title(title)
        metric_map = metrics or {}
        volume_text = f"{int(metric_map.get('volume')):,}" if str(metric_map.get("volume", "")).isdigit() else "待从盘口页补当前成交量"
        liquidity_text = f"{int(metric_map.get('liquidity')):,}" if str(metric_map.get("liquidity", "")).isdigit() else "待从盘口页补当前流动性"
        rank_text = f"第 {metric_map.get('rank')} 位" if metric_map.get("rank") not in (None, "") else "待补榜单排名"
        source_names = "、".join(source_list[:4]) if source_list else source
        sample_page = (
            "一页中文事件监控页样张：顶部放当前 Yes 概率、24 小时概率变化、成交量、流动性和榜单排名；"
            "中部放盘口结算规则、世卫组织/各国疾控/可信媒体的核对状态；"
            "底部放 3 张影响表：医疗防护用品、旅行保险/出行、跨境采购和供应链。"
        )
        first_message = (
            "触达话术：我在做一个小样张，不是下注建议，也不是医学判断。它跟踪 Polymarket 上“2026 年汉坦病毒是否会被世卫组织称为大流行”的盘口，"
            f"现在已记录榜单{rank_text}、成交量 {volume_text}、流动性 {liquidity_text}，并把结算规则、官方触发条件和可能影响行业整理成中文监控页。"
            "你们做投研/采购/内容选题时，会不会需要这种每周更新的事件预警？我可以先发免费样张，想请你告诉我哪些指标有用、哪些没用。"
        )
        agent_config = {
            "name": "MerchantOpportunityAgent",
            "role": "把单条预测市场信号拆成可售卖交付物、第一批客户、测试价、触达话术和放弃阈值，不负责医学判断或下注建议。",
            "inputs": [
                f"来源：{source}",
                f"盘口主题：{localized_title}",
                f"平台指标：榜单{rank_text}、成交量 {volume_text}、流动性 {liquidity_text}",
                f"证据状态：{evidence_count} 个来源（{source_names}）",
                f"机会分 {opportunity.score}、验证分 {opportunity.validation_score}、窗口 {opportunity.window_hours} 小时",
            ],
            "output_contract": [
                "先卖什么",
                "第一批卖给谁",
                "客户拿到什么交付物",
                "测试价和成交方式",
                "第一条触达话术",
                "72 小时验证动作",
                "明确放弃阈值",
            ],
            "guardrails": [
                "不输出医学建议",
                "不制造恐慌",
                "不把预测市场当投资建议",
                "没有第二来源前只做样张验证，不做长期订阅承诺",
            ],
        }
        execution_brief = {
            "sell": f"先卖“{localized_title}”中文事件监控页样张，不卖宏大平台。样张只回答四件事：盘口怎么结算、概率/成交量/流动性有没有变化、官方来源有没有同向证据、哪些行业要提前看。",
            "buyer": "第一批不要找泛投资者，先找事件驱动投研、跨境采购/卖家负责人、旅行保险或医疗防护相关业务负责人、公共卫生/国际新闻选题编辑。",
            "deliverable": sample_page,
            "price_test": "测试价：第一版免费换反馈；愿意继续看的客户收 19-49 元试读或 199-499 元/月主题监控；定制行业影响清单报价 999-3000 元/份。",
            "first_channel": "先从微信群、知识星球、雪球/公众号评论区、跨境卖家社群、投研朋友和行业编辑私信里找 10 个目标人，不做公开投放。",
            "first_message": first_message,
            "data_to_track": [
                "Polymarket 当前 Yes 概率和 24 小时变化",
                f"成交量 {volume_text}、流动性 {liquidity_text}、榜单{rank_text}",
                "世卫组织 Disease Outbreak News、官方声明、报告和发布会是否出现“大流行”表述",
                "各国疾控机构、可信媒体和行业数据是否有第二来源补强",
                "医疗防护用品、旅行保险、跨境物流/采购、内容选题是否出现可执行动作",
            ],
            "success_threshold": "72 小时内触达 10 个目标人，至少 3 个回复，至少 1 个要求继续更新、询价、转发给同事或愿意看下一版。",
            "stop_threshold": "72 小时内没有第二来源、盘口概率/成交量/流动性没有连续变化，或 10 个目标人没有任何有效回复，就停止产品化，只保留观察。",
        }
        customer_scenarios = [
            {
                "segment": "事件驱动投研人员",
                "pain": "他们不缺新闻，缺的是比新闻更早的概率变化、结算条件和影响链路。",
                "use_case": "用样张决定要不要写事件跟踪、提醒客户、加入宏观风险周报。",
                "where_to_find": "雪球、知识星球、投研微信群、券商/私募研究员朋友和宏观事件公众号评论区。",
            },
            {
                "segment": "跨境采购或卖家负责人",
                "pain": "他们关心的是事件是否影响防护用品、出行用品、物流、保险和采购备货，而不是盘口本身。",
                "use_case": "用影响表决定哪些品类先查库存、价格、供应商和广告素材。",
                "where_to_find": "跨境卖家社群、1688/亚马逊选品群、外贸采购群和供应链服务商客户群。",
            },
            {
                "segment": "旅行保险/医疗防护相关业务负责人",
                "pain": "他们需要提前知道公共卫生事件是否可能进入客户咨询和内容教育场景。",
                "use_case": "用监控页准备 FAQ、风控提示、内容选题和客户提醒，不做医学诊断。",
                "where_to_find": "保险代理社群、旅行服务商、医疗防护用品商家和相关行业运营负责人。",
            },
            {
                "segment": "公共卫生或国际新闻内容团队",
                "pain": "他们需要快速把英文盘口和官方规则转成可信中文选题，避免只写猎奇标题。",
                "use_case": "用官方来源核对表和行业影响清单写专题、短视频脚本或付费社群更新。",
                "where_to_find": "公众号作者、视频号/小红书科普账号、国际新闻编辑和行业研究内容团队。",
            },
        ]
        offer_packages = [
            {
                "name": "免费样张换反馈",
                "price": "0 元，目标是拿 10 个真实反馈",
                "deliverable": sample_page,
                "buy_trigger": "对方愿意留下邮箱/微信、问下一版什么时候更新，或转给同事。",
            },
            {
                "name": "主题监控小订阅",
                "price": "19-49 元试读，199-499 元/月",
                "deliverable": "每周 2-3 次更新：盘口指标、官方来源核对、行业影响表、下一步关注点。",
                "buy_trigger": "客户需要持续跟踪同一事件，但不想自己每天查英文来源和盘口。",
            },
            {
                "name": "定制行业影响清单",
                "price": "999-3000 元/份",
                "deliverable": "按客户行业拆 10-20 条影响项：风险、机会、需要查的数据、供应商/内容动作。",
                "buy_trigger": "客户明确说自己属于医疗防护、旅行保险、跨境采购、投研或内容团队，需要内部汇报材料。",
            },
        ]
        next_actions = [
            {
                "step": "第 1 小时：补齐盘口快照",
                "output": f"记录当前 Yes 概率、24 小时变化、成交量 {volume_text}、流动性 {liquidity_text}、榜单{rank_text}和结算规则截图。",
                "done_when": "监控页顶部能让客户 30 秒看懂这个盘口现在值不值得跟踪。",
            },
            {
                "step": "第 2-4 小时：补第二来源",
                "output": "检查世卫组织、各国疾控机构和可信媒体，只记录是否有官方表述和事件进展，不做医学判断。",
                "done_when": "页面里有“已确认/未确认/待观察”的来源核对表，而不是只有 Polymarket 一条。",
            },
            {
                "step": "第 4-8 小时：做 3 张行业影响表",
                "output": "分别写医疗防护用品、旅行保险/出行、跨境采购和供应链：可能影响、要查数据、客户动作。",
                "done_when": "每张表至少 5 行，客户能据此决定下一步查什么或问谁。",
            },
            {
                "step": "第 8-24 小时：发 10 个定向触达",
                "output": "用触达话术私信/微信发给 10 个目标人，附免费样张，不公开制造恐慌。",
                "done_when": "拿到回复、收藏、转发、询价或明确反对意见，并记录在验证表里。",
            },
            {
                "step": "第 24-72 小时：决定继续还是放弃",
                "output": "根据第二来源、盘口连续变化和客户反馈决定：做试读订阅、做定制清单，或停止。",
                "done_when": execution_brief["success_threshold"],
            },
        ]
        why_now = [
            f"平台已经给出可量化盘口：榜单{rank_text}、成交量 {volume_text}、流动性 {liquidity_text}。这说明它至少有交易关注，不是单纯新闻标题。",
            "这类机会的第一笔钱不来自长期系统，而来自 72 小时内做出可看的监控样张并找目标客户验证。",
            f"当前有 {evidence_count} 个证据源：{'、'.join(source_list[:4]) if source_list else source}；如果没有第二来源补强，只能先验证，不能重投入。",
        ]
        validation_steps = [item["step"] + "：" + item["output"] for item in next_actions]
        no_go = [
            execution_brief["stop_threshold"],
            "客户只说“挺有意思”，但不愿意留下联系方式、不问下一版、不转发、不询价。",
            "内容只能讲公共卫生事件本身，拆不出投研、采购、保险、供应链或内容团队的具体动作。",
            "为了吸引注意力必须制造恐慌或暗示医学结论时，立即放弃。",
        ]
        return {
            "analysis_version": "merchant_analysis_v7",
            "plain_type": "商人行动卡",
            "agent_config": agent_config,
            "execution_brief": execution_brief,
            "customer_scenarios": customer_scenarios,
            "offer_packages": offer_packages,
            "next_actions": next_actions,
            "opportunity_summary": f"可执行机会不是“汉坦病毒大流行”本身，而是先做一页「{localized_title}」中文事件监控页样张，用它去验证投研、跨境采购、保险/医疗防护和内容团队是否愿意持续接收或付费。",
            "what_to_sell": execution_brief["sell"],
            "who_pays": execution_brief["buyer"],
            "why_they_pay": (
                "客户不是为“知道一个盘口”付钱，而是为省掉每天查英文盘口、官方来源和行业影响的时间付钱。"
                "如果样张能直接告诉他们要查哪些数据、问哪些供应商、写什么选题或提醒哪些客户，就能卖试读订阅或定制影响清单。"
            ),
            "first_test": next_actions[0]["step"] + "：" + next_actions[0]["output"],
            "not_the_opportunity": "不是下注建议，也不是传播恐慌；它卖的是把预测市场概率翻译成经营、投研、采购和内容决策的中文信息服务。",
            "decision_question": "接下来只问一个问题：把免费样张发给 10 个目标人后，有没有 3 个回复、1 个愿意继续看或询价？没有就别产品化。",
            "what_it_is": (
                f"这条机会要干的事很具体：用 Polymarket 盘口做一页中文事件监控页样张，主题是「{localized_title}」。"
                f"样张不是医学判断，也不是下注建议，而是给投研、跨境采购、保险/医疗防护和内容团队看的决策材料。"
                f"它必须展示当前盘口概率、成交量 {volume_text}、流动性 {liquidity_text}、榜单{rank_text}、结算规则、世卫组织等官方触发条件、第二来源核对和 3 张行业影响表。"
                "拿这页样张去定向触达 10 个目标人，验证他们是否愿意持续接收更新、试读、询价或转发。"
            ),
            "source_context": _localized_prediction_market_excerpt(title, summary_text),
            "why_opportunity": (
                "信息差不在“预测汉坦病毒会不会大流行”，而在大多数人只看到英文盘口时，你先把它翻译成客户能用的监控页。"
                "客户真正要的是：盘口有没有连续变化、官方来源有没有同向证据、哪些行业需要动作、如果不成立什么时候停止。"
                f"现在已有成交量 {volume_text} 和流动性 {liquidity_text}，足够做样张验证；但证据源只有 {evidence_count} 个，所以只能先卖样张和试读，不适合承诺长期预警产品。"
            ),
            "why_now": why_now,
            "who_needs_it": [f"{item['segment']}：{item['use_case']}" for item in customer_scenarios],
            "business_angles": [f"{item['name']}（{item['price']}）：{item['deliverable']}" for item in offer_packages],
            "validation_plan": validation_steps,
            "no_go_signals": no_go,
            "merchant_take": (
                f"我的判断：可以干，但只能按“72 小时样张验证”干，不能按“大项目”干。"
                f"第一步交付物就是这页中文事件监控样张，第一批客户就是投研、跨境采购、保险/医疗防护和内容团队。"
                f"测试价从免费样张换反馈开始，再试 19-49 元试读、199-499 元/月主题监控或 999-3000 元定制清单。"
                f"如果 10 个定向触达里没有 3 个回复、没有 1 个愿意继续看或询价，或者 72 小时内没有第二来源和盘口连续变化，就停止。"
            ),
            "score_explanation": {
                "demand": demand,
                "momentum": momentum,
                "execution": execution,
                "competition_buffer": competition,
                "risk_level": opportunity.risk_level,
                "crowding_score": opportunity.crowding_score,
            },
        }
    return {
        "analysis_version": "merchant_analysis_v7",
        "plain_type": lens["plain_type"],
        **frame,
        "what_it_is": f"这条机会来自「{source}」的{lens['plain_type']}。原始信号是：{title}。可以做的不是复述这条信号，而是把它包装成客户能购买、能订阅或能用来决策的产品/服务。",
        "source_context": _localized_prediction_market_excerpt(title, summary_text),
        "why_opportunity": lens["opportunity_logic"],
        "why_now": why,
        "who_needs_it": lens["customers"],
        "business_angles": lens["monetization"],
        "validation_plan": lens["validation"],
        "no_go_signals": lens["no_go"],
        "merchant_take": f"我的判断：这条不是最终项目结论，而是「{localized_playbook}」方向的可验证商业假设。先用 {opportunity.window_hours} 小时验证是否有人愿意点击、咨询、订阅、采购或转介绍。分数 {opportunity.score}，验证分 {opportunity.validation_score}，不适合跳过验证直接重仓。",
        "score_explanation": {
            "demand": demand,
            "momentum": momentum,
            "execution": execution,
            "competition_buffer": competition,
            "risk_level": opportunity.risk_level,
            "crowding_score": opportunity.crowding_score,
        },
    }


def _build_merchant_analysis(
    opportunity: Opportunity,
    signal: Signal | None,
    clean: CleanItem | None,
    raw: RawItem | None,
) -> dict[str, Any]:
    metrics = clean.metrics if clean and clean.metrics else {}
    raw_payload = raw.payload if raw and raw.payload else {}
    source = clean.source if clean else (signal.sources or ["未知来源"])[0] if signal else "未知来源"
    title_zh = metrics.get("title_zh") or (clean.title if clean else signal.title if signal else "")
    title_original = metrics.get("title_original") or raw_payload.get("title_original") or (raw.title if raw else "")
    content_zh = metrics.get("content_zh") or (clean.summary if clean else "")
    content_original = metrics.get("content_original") or raw_payload.get("content_original") or (raw.content if raw else "")
    return _merchant_analysis_payload(
        opportunity=opportunity,
        signal=signal,
        source=source,
        title=_display_evidence_title(source, title_zh or title_original),
        summary=content_zh or content_original,
        metrics=metrics,
    )


async def _get_or_create_opportunity_analysis(
    db,
    opportunity: Opportunity,
    signal: Signal | None,
    clean: CleanItem | None,
    raw: RawItem | None,
) -> OpportunityAnalysis:
    existing = await db.get(OpportunityAnalysis, opportunity.id)
    title_payload = _opportunity_title_payload(opportunity, signal, clean, raw)
    if (
        existing is not None
        and existing.analysis
        and existing.analysis.get("analysis_version") == "merchant_analysis_v7"
    ):
        return existing

    existing_deep_analysis = (existing.analysis or {}).get("deep_analysis") if existing is not None else None
    analysis = _build_merchant_analysis(opportunity, signal, clean, raw)
    if existing_deep_analysis:
        analysis["deep_analysis"] = existing_deep_analysis
    now = datetime.utcnow()
    if existing is None:
        existing = OpportunityAnalysis(
            opportunity_id=opportunity.id,
            source=(title_payload.get("source") or "")[:80],
            title=(title_payload.get("business_title") or title_payload.get("title") or "")[:240],
            evidence_title=(title_payload.get("evidence_title") or "")[:300],
            analysis=analysis,
            generated_by="MerchantAnalysisAgent",
            created_at=now,
            updated_at=now,
        )
        db.add(existing)
    else:
        existing.source = (title_payload.get("source") or existing.source or "")[:80]
        existing.title = (title_payload.get("business_title") or title_payload.get("title") or existing.title or "")[:240]
        existing.evidence_title = (title_payload.get("evidence_title") or existing.evidence_title or "")[:300]
        existing.analysis = analysis
        existing.generated_by = "MerchantAnalysisAgent"
        existing.updated_at = now
    await db.flush()
    return existing


def _evidence_payload(
    *,
    opportunity: Opportunity,
    signal: Signal | None,
    clean: CleanItem | None,
    raw: RawItem | None,
    merchant_analysis: dict | None = None,
) -> dict:
    clean_metrics = clean.metrics if clean and clean.metrics else {}
    raw_payload = raw.payload if raw and raw.payload else {}
    source = clean.source if clean else (signal.sources or ["未知来源"])[0] if signal else "未知来源"
    source_list = clean_metrics.get("evidence_sources") or (signal.sources if signal else None) or [source]
    title_zh = clean_metrics.get("title_zh") or (clean.title if clean else signal.title if signal else "")
    title_original = clean_metrics.get("title_original") or raw_payload.get("title_original") or (raw.title if raw else "")
    content_zh = clean_metrics.get("content_zh") or (clean.summary if clean else "")
    content_original = clean_metrics.get("content_original") or raw_payload.get("content_original") or (raw.content if raw else "")
    display_title = _display_evidence_title(source, title_zh or title_original)
    source_record = _source_record_payload(
        opportunity=opportunity,
        signal=signal,
        source=source,
        title_zh=title_zh,
        title_original=title_original,
        content_zh=content_zh,
        content_original=content_original,
        clean_metrics=clean_metrics,
        raw_payload=raw_payload,
        clean=clean,
        raw=raw,
    )

    pipeline_steps = [
        {
            "agent": "SourceConnector",
            "action": f"从 {source} 采集原始记录",
            "output": display_title or title_original or title_zh,
            "status": "done" if raw or clean else "inferred",
        },
        {
            "agent": "QualityFilter",
            "action": "过滤低价值、重复、薄讨论和噪声内容",
            "output": "通过过滤，进入清洗队列",
            "status": "done",
        },
        {
            "agent": clean_metrics.get("translation_agent") or "ChineseLocalizationAgent",
            "action": "保留原文，并生成中文标题/摘要",
            "output": f"{clean_metrics.get('translation_provider', 'local_glossary_free')} / {clean_metrics.get('language', 'unknown')} -> zh",
            "status": "done" if clean_metrics.get("translated_to") == "zh" else "pending",
        },
        {
            "agent": "DedupCluster",
            "action": "按规范化标题和链接做去重聚合",
            "output": f"证据数：{clean_metrics.get('evidence_count', 1)}，来源：{'、'.join(source_list)}",
            "status": "done",
        },
        {
            "agent": "OpportunityScoringAgent",
            "action": "按需求、动量、供给、竞争、执行、风险六维评分",
            "output": f"机会分 {opportunity.score} / 等级 {opportunity.level}",
            "status": "done",
        },
        {
            "agent": "PlaybookAgent",
            "action": "生成商人视角打法、投入、回报和执行步骤",
            "output": _localized_playbook_name(opportunity.playbook, opportunity.playbook_name, source),
            "status": "done",
        },
    ]

    return {
        "source": source,
        "sources": source_list,
        "url": clean.url if clean else raw.url if raw else None,
        "published_at": clean.published_at if clean else raw.published_at if raw else None,
        "fetched_at": raw.fetched_at if raw else None,
        "title_zh": title_zh,
        "title_original": title_original,
        "content_zh": content_zh,
        "content_original": content_original,
        "source_record": source_record,
        "specific_content": {
            "record_type": source_record["record_type"],
            "title": source_record["title"],
            "content": source_record["content_excerpt"],
            "original_content": source_record["content_original_excerpt"],
            "url": source_record["url"],
            "metrics": source_record["key_metrics"],
        },
        "topic": clean.topic if clean else signal.type if signal else "",
        "circle": clean.circle if clean else signal.circle if signal else "",
        "region": clean.region if clean else signal.region if signal else "",
        "metrics": clean_metrics,
        "raw_payload": raw_payload,
        "hot_reasons": _hot_reasons(source, clean_metrics, signal, opportunity),
        "merchant_analysis": merchant_analysis
        or _merchant_analysis_payload(
            opportunity=opportunity,
            signal=signal,
            source=source,
            title=display_title,
            summary=content_zh or content_original,
            metrics=clean_metrics,
        ),
        "pipeline_steps": pipeline_steps,
        "analysis_summary": {
            "platform_signal": f"{source} 抓到的内容被判定为 {clean.topic if clean else signal.type if signal else '商业信号'}",
            "source_fact": source_record["signal_fact"],
            "business_model": source_record["business_model"],
            "system_interpretation": source_record["system_interpretation"],
            "business_interpretation": f"系统把它转成「{_localized_playbook_name(opportunity.playbook, opportunity.playbook_name, source)}」机会，适合用 {opportunity.window_hours} 小时窗口做小成本验证",
            "why_now": f"热度分 {signal.score if signal else opportunity.score}，拥挤度 {opportunity.crowding_score}/100，风险等级 {opportunity.risk_level}",
        },
    }


def _list_from_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _deep_offer_map(merchant_analysis: dict, source_record: dict, opportunity: Opportunity) -> list[dict[str, str]]:
    business_angles = _list_from_value(merchant_analysis.get("business_angles"))
    what_to_sell = merchant_analysis.get("what_to_sell") or source_record.get("business_model") or opportunity.playbook_name
    offers = [what_to_sell, *business_angles]
    unique_offers: list[str] = []
    for offer in offers:
        if offer and offer not in unique_offers:
            unique_offers.append(str(offer))
    if not unique_offers:
        unique_offers = ["信息差服务", "工具订阅", "线索获客"]

    return [
        {
            "offer": offer,
            "format": "落地页/样品/服务说明" if index == 0 else "轻量版本或单次交付",
            "buyer_value": "帮客户更快判断、降低风险、节省部署或找到可行动线索",
            "price_test": "先测试 0-999 元咨询/报告/部署包，确认有人愿意付款或留下采购意向",
            "proof_needed": "至少拿到 2 个正向反馈、1 个明确试用/询价或 1 个愿意付费的客户",
        }
        for index, offer in enumerate(unique_offers[:4])
    ]


def _deep_customer_segments(merchant_analysis: dict, source_record: dict) -> list[dict[str, str]]:
    customers = _list_from_value(merchant_analysis.get("who_needs_it"))
    if not customers and merchant_analysis.get("who_pays"):
        customers = [item.strip() for item in str(merchant_analysis.get("who_pays")).split("、") if item.strip()]
    if not customers:
        customers = ["目标行业用户", "中小企业", "内容/投研团队"]
    record_type = source_record.get("record_type") or "原始记录"
    return [
        {
            "segment": customer,
            "pain": f"他们需要把「{record_type}」背后的变化转成可执行判断，而不是只看信息流。",
            "buying_trigger": "出现预算、风险、效率、获客或供应链压力时最可能付费。",
            "how_to_reach": "先用定向私信、行业群、LinkedIn/邮件或垂直社区找 5-10 个样本用户。",
        }
        for customer in customers[:4]
    ]


def _deep_validation_plan(opportunity: Opportunity, merchant_analysis: dict, source_record: dict) -> list[dict[str, str]]:
    validation = _list_from_value(merchant_analysis.get("validation_plan"))
    first_test = merchant_analysis.get("first_test") or (validation[0] if validation else "做一页说明并找 5 个目标客户验证")
    title = source_record.get("title") or merchant_analysis.get("opportunity_summary") or opportunity.playbook_name
    return [
        {
            "phase": "第 0-1 天",
            "action": f"把机会写成一句客户能懂的话：{_clip_text(title, 90)}。",
            "output": "一页机会说明、目标客户清单、原始证据链接",
            "success_metric": "能清楚说出卖什么、卖给谁、为什么付钱",
        },
        {
            "phase": "第 1-2 天",
            "action": first_test,
            "output": "落地页、Demo、报告样张或服务包说明",
            "success_metric": "至少 5 个目标客户看到，2 个以上愿意继续聊",
        },
        {
            "phase": "第 2-3 天",
            "action": "做一次小范围触达，收集点击、回复、收藏、询价或试用意向。",
            "output": "客户反馈表、价格接受度、反对意见",
            "success_metric": "出现 1 个明确付费/试用/采购意向，或 3 个同类痛点反馈",
        },
        {
            "phase": "第 4-7 天",
            "action": "根据反馈决定继续做 MVP、转成内容/线索产品，或放弃。",
            "output": "继续/观察/放弃结论和下一轮预算",
            "success_metric": "能用真实反馈解释为什么继续投入或停止",
        },
    ]


def _deep_risk_review(opportunity: Opportunity, merchant_analysis: dict, source_record: dict) -> list[dict[str, str]]:
    risks = _list_from_value(opportunity.risk_factors) + _list_from_value(merchant_analysis.get("no_go_signals"))
    if not risks:
        risks = ["证据源较少，可能只是短期噪声", "目标客户和付费意愿还没有验证"]
    return [
        {
            "risk": risk,
            "why_it_matters": "如果这个风险成立，机会可能只是一条信息而不是可赚钱项目。",
            "mitigation": "用第二来源、客户访谈和小额付费测试确认，再决定是否扩大投入。",
        }
        for risk in risks[:5]
    ]


def _deep_data_gaps(evidence: dict, opportunity: Opportunity) -> list[str]:
    gaps: list[str] = []
    source_record = evidence.get("source_record") or {}
    if not source_record.get("content_excerpt"):
        gaps.append("原始内容摘要不足，需要打开链接补全文或更多上下文。")
    if int(opportunity.dimensions.get("evidence_count", 1) if opportunity.dimensions else 1) < 2:
        gaps.append("目前证据源偏少，建议找至少 1 个独立来源交叉验证。")
    if not source_record.get("key_metrics"):
        gaps.append("缺少可量化平台指标，需要补充热度、评论、交易量、榜单或搜索数据。")
    if opportunity.risk_level == "high":
        gaps.append("风险等级偏高，必须先明确合规、平台依赖和最大亏损。")
    if not gaps:
        gaps.append("下一步主要缺客户反馈：是否有人愿意试用、询价、订阅或转介绍。")
    return gaps


def _deep_decision(opportunity: Opportunity, evidence: dict) -> dict[str, str]:
    evidence_count = int(opportunity.dimensions.get("evidence_count", 1) if opportunity.dimensions else 1)
    if opportunity.level == "S" or opportunity.score >= 88:
        recommendation = "优先深入验证"
        confidence = "中高"
    elif opportunity.score >= 75:
        recommendation = "小成本验证"
        confidence = "中"
    else:
        recommendation = "继续观察"
        confidence = "低到中"
    if opportunity.risk_level == "high":
        recommendation = "先降风险再验证"
        confidence = "中"
    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "reason": f"机会分 {opportunity.score}、等级 {opportunity.level}、证据源 {evidence_count} 个、风险 {opportunity.risk_level}。",
        "next_action": "先做 5-10 个目标客户访谈或落地页测试，不要直接重投入。",
    }


def _build_deep_opportunity_analysis(
    *,
    opportunity: Opportunity,
    signal: Signal | None,
    evidence: dict,
    merchant_analysis: dict,
) -> dict[str, Any]:
    source_record = evidence.get("source_record") or {}
    metrics = source_record.get("key_metrics") or evidence.get("metrics") or {}
    scorecard = {
        "demand": _metric_percent(opportunity.dimensions, "demand", 0.55),
        "momentum": _metric_percent(opportunity.dimensions, "momentum", 0.55),
        "execution": _metric_percent(opportunity.dimensions, "execution", 0.55),
        "competition_buffer": _metric_percent(opportunity.dimensions, "competition_adjusted", 0.5),
        "risk_buffer": _metric_percent(opportunity.dimensions, "risk_adjusted", 0.5),
    }
    title = source_record.get("title") or evidence.get("title_zh") or opportunity.playbook_name
    return {
        "analysis_version": "deep_opportunity_v1",
        "generated_by": "DeepOpportunityAnalyst",
        "generated_at": datetime.utcnow().isoformat(),
        "headline": merchant_analysis.get("opportunity_summary") or f"围绕「{title}」做可验证商业机会。",
        "opportunity_definition": {
            "what_it_is": merchant_analysis.get("what_it_is") or source_record.get("system_interpretation") or "",
            "what_to_sell": merchant_analysis.get("what_to_sell") or source_record.get("business_model") or opportunity.playbook_name,
            "who_pays": merchant_analysis.get("who_pays") or "目标客户待验证",
            "why_they_pay": merchant_analysis.get("why_they_pay") or merchant_analysis.get("why_opportunity") or "",
            "not_the_opportunity": merchant_analysis.get("not_the_opportunity") or "不是直接复制原始内容，也不是跳过验证直接投入。",
        },
        "source_digest": {
            "record_type": source_record.get("record_type"),
            "source": source_record.get("source"),
            "title": title,
            "content_excerpt": source_record.get("content_excerpt") or evidence.get("content_zh") or evidence.get("content_original"),
            "url": source_record.get("url") or evidence.get("url"),
            "key_metrics": metrics,
            "signal_fact": source_record.get("signal_fact") or evidence.get("analysis_summary", {}).get("source_fact"),
        },
        "scorecard": scorecard,
        "why_now": _list_from_value(merchant_analysis.get("why_now"))
        + [
            f"系统信号分 {signal.score if signal else opportunity.score}，机会等级 {opportunity.level}。",
            f"当前打法是「{opportunity.playbook_name}」，验证窗口 {opportunity.window_hours} 小时。",
        ],
        "customer_segments": _deep_customer_segments(merchant_analysis, source_record),
        "offer_map": _deep_offer_map(merchant_analysis, source_record, opportunity),
        "validation_plan": _deep_validation_plan(opportunity, merchant_analysis, source_record),
        "go_to_market": [
            "先找最容易触达的 10 个潜在客户，不做大范围投放。",
            "用原始证据和一句话卖点做冷启动，不讲平台评分，讲客户能得到什么。",
            "把回复分成：强需求、弱兴趣、无需求、反对意见四类。",
            "若 72 小时内没有任何明确意向，降级为观察或换人群。",
        ],
        "risk_review": _deep_risk_review(opportunity, merchant_analysis, source_record),
        "data_gaps": _deep_data_gaps(evidence, opportunity),
        "decision": _deep_decision(opportunity, evidence),
    }


def _glm_deep_analysis_messages(fallback: dict[str, Any]) -> list[dict[str, str]]:
    compact_context = {
        "headline": fallback.get("headline"),
        "opportunity_definition": fallback.get("opportunity_definition"),
        "source_digest": fallback.get("source_digest"),
        "scorecard": fallback.get("scorecard"),
        "why_now": fallback.get("why_now"),
        "customer_segments": fallback.get("customer_segments"),
        "offer_map": fallback.get("offer_map"),
        "validation_plan": fallback.get("validation_plan"),
        "risk_review": fallback.get("risk_review"),
        "data_gaps": fallback.get("data_gaps"),
        "decision": fallback.get("decision"),
    }
    schema_hint = {
        "headline": "一句话说明这是什么机会",
        "opportunity_definition": {
            "what_it_is": "这个机会是什么",
            "what_to_sell": "具体卖什么产品/服务",
            "who_pays": "谁会付钱",
            "why_they_pay": "为什么愿意付钱",
            "not_the_opportunity": "这不是什么，避免误解",
        },
        "customer_segments": [
            {"segment": "客户群体", "pain": "痛点", "buying_trigger": "购买触发点", "how_to_reach": "如何触达"}
        ],
        "offer_map": [
            {"offer": "可卖方案", "format": "交付形态", "buyer_value": "客户价值", "price_test": "价格测试", "proof_needed": "需要证据"}
        ],
        "validation_plan": [
            {"phase": "阶段", "action": "动作", "output": "产出", "success_metric": "成功标准"}
        ],
        "go_to_market": ["获客动作"],
        "risk_review": [
            {"risk": "风险", "why_it_matters": "为什么重要", "mitigation": "缓解办法"}
        ],
        "data_gaps": ["还缺什么数据"],
        "decision": {
            "recommendation": "优先深入验证/小成本验证/继续观察/先降风险再验证",
            "confidence": "高/中高/中/低",
            "reason": "判断理由",
            "next_action": "下一步动作",
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "你是一个严谨的商业机会分析师，面向中国创业者和商人。"
                "你必须基于给定原始信号和评分，不编造外部事实。"
                "输出只能是 JSON 对象，不要 Markdown，不要解释。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请对这条机会做深入分析，要求具体、可执行、能回答“这是什么机会、做什么、卖给谁、怎么验证”。\n"
                "请保持以下 JSON 结构，字段名不要变；可以重写字段内容，使其更像资深商业顾问报告。\n"
                f"JSON结构示例：{json.dumps(schema_hint, ensure_ascii=False)}\n"
                f"机会上下文：{json.dumps(compact_context, ensure_ascii=False, default=str)}"
            ),
        },
    ]


def _merge_glm_deep_analysis(fallback: dict[str, Any], glm_payload: dict[str, Any]) -> dict[str, Any]:
    merged = dict(fallback)
    for key in (
        "headline",
        "opportunity_definition",
        "source_digest",
        "why_now",
        "customer_segments",
        "offer_map",
        "validation_plan",
        "go_to_market",
        "risk_review",
        "data_gaps",
        "decision",
    ):
        value = glm_payload.get(key)
        if value not in (None, "", [], {}):
            merged[key] = value
    merged["analysis_version"] = "deep_opportunity_glm_v1"
    merged["generated_by"] = "GLMDeepOpportunityAnalyst"
    merged["llm_provider"] = "glm"
    merged["model"] = settings.glm_model
    merged["generated_at"] = datetime.utcnow().isoformat()
    return merged


async def _maybe_generate_glm_deep_analysis(fallback: dict[str, Any]) -> dict[str, Any]:
    if not glm_is_configured():
        fallback["llm_provider"] = "local_fallback"
        return fallback
    try:
        glm_payload = await glm_json_completion(
            messages=_glm_deep_analysis_messages(fallback),
            temperature=0.35,
            max_tokens=3500,
        )
        return _merge_glm_deep_analysis(fallback, glm_payload)
    except (GLMError, json.JSONDecodeError) as exc:
        fallback["llm_provider"] = "local_fallback"
        fallback["llm_error"] = str(exc)[:500]
        return fallback


def _opportunity_risk_payload(opportunity: Opportunity) -> dict:
    return {
        "opportunity_id": opportunity.id,
        "crowding_score": opportunity.crowding_score,
        "risk_level": opportunity.risk_level,
        "risk_factors": opportunity.risk_factors or [],
        "bear_case": opportunity.bear_case,
    }


def _opportunity_validation_payload(opportunity: Opportunity) -> dict:
    return {
        "opportunity_id": opportunity.id,
        "validation_score": opportunity.validation_score,
        "validation": {
            "bull_case": opportunity.estimated_return,
            "bear_case": opportunity.bear_case,
            "difficulty": opportunity.difficulty,
        },
    }


def _opportunity_roi_payload(opportunity: Opportunity, capital: Optional[float] = None) -> dict:
    adjustment = 1.0
    if capital is not None and capital > 0:
        adjustment = max(0.5, min(2.0, capital / 10000.0))
    return {
        "opportunity_id": opportunity.id,
        "estimated_investment": opportunity.estimated_investment,
        "estimated_return": opportunity.estimated_return,
        "roi_ratio": opportunity.roi_ratio,
        "breakeven": opportunity.breakeven,
        "max_loss": opportunity.max_loss,
        "capital_factor": round(adjustment, 2),
    }


def _opportunity_oci_payload(opportunity: Opportunity) -> dict:
    dimensions = opportunity.dimensions or {}
    score = sum(
        [
            float(dimensions.get("momentum", 0) * 35),
            float(dimensions.get("crowding", 1) * 10),
            float((1 - dimensions.get("risk", 0)) * 30),
            float((1 - dimensions.get("pricing", 0.5)) * 15),
            float(dimensions.get("execution", 0.7) * 10),
        ]
    )
    return {
        "opportunity_id": opportunity.id,
        "oci_score": opportunity.score,
        "oci_breakdown": {
            "momentum": dimensions.get("momentum", 0),
            "crowding": dimensions.get("crowding", 0),
            "risk": dimensions.get("risk", 0),
            "pricing": dimensions.get("pricing", 0),
            "execution": dimensions.get("execution", 0),
        },
        "composite_score": round(score, 2),
        "recommendation": "优先执行" if score >= 60 else "观察",
    }


def _source_names(signal: Signal | None, clean: CleanItem | None = None) -> list[str]:
    if clean is not None:
        metrics = clean.metrics or {}
        sources = metrics.get("evidence_sources") or [clean.source]
        return [str(source) for source in sources if source]
    if signal is not None and signal.sources:
        return [str(source) for source in signal.sources if source]
    return ["未知来源"]


def _metric_reasons(metrics: dict | None, signal: Signal | None, opportunity: Opportunity | None = None) -> list[str]:
    metrics = metrics or {}
    reasons: list[str] = []
    reason_map = [
        ("stars", "GitHub Stars"),
        ("forks", "Forks"),
        ("comments", "讨论量"),
        ("score", "社区评分"),
        ("points", "Hacker News 热度"),
        ("traffic", "搜索流量"),
        ("rank", "榜单排名"),
        ("review_count", "评论数"),
    ]
    for key, label in reason_map:
        value = metrics.get(key)
        if value:
            reasons.append(f"{label} {value}")
    evidence_count = int(metrics.get("evidence_count", 1) or 1)
    if evidence_count > 1:
        reasons.append(f"{evidence_count} 个来源交叉验证")
    if signal is not None:
        reasons.append(f"信号分 {signal.score} / {signal.level}")
    if opportunity is not None:
        reasons.append(f"机会分 {opportunity.score}，验证分 {opportunity.validation_score}")
    return reasons[:4] or ["早期信号，适合小成本验证"]


async def _opportunity_brief_item(db, opportunity: Opportunity, rank: int) -> dict[str, Any]:
    signal = await db.get(Signal, opportunity.signal_id)
    dimensions = opportunity.dimensions or {}
    clean = await db.get(CleanItem, dimensions.get("clean_item_id")) if dimensions.get("clean_item_id") else None
    if clean is None:
        clean = await _find_clean_for_signal(db, opportunity.signal_id, signal)
    metrics = clean.metrics if clean and clean.metrics else {}
    sources = _source_names(signal, clean)
    decision = "优先执行" if opportunity.score >= 80 and opportunity.risk_level != "high" else "观察验证"
    if opportunity.risk_level == "high" or opportunity.crowding_score >= 75:
        decision = "只观察"
    title = _opportunity_title_payload(opportunity, signal, clean).get("title") or opportunity.playbook_name
    validation_where = clean.url if clean and clean.url else (sources[0] if sources else "对应来源平台")
    gate = _opportunity_gate(opportunity, signal, {})
    action_summary = _action_summary_payload(
        opportunity,
        signal=signal,
        gate=gate,
        source=sources[0] if sources else None,
        title=title,
    )
    return {
        "rank": rank,
        "id": opportunity.id,
        "signal_id": opportunity.signal_id,
        "title": title,
        "source": sources[0],
        "sources": sources,
        "playbook": opportunity.playbook,
        "playbook_name": opportunity.playbook_name,
        "score": opportunity.score,
        "level": opportunity.level,
        "risk_level": opportunity.risk_level,
        "crowding_score": opportunity.crowding_score,
        "validation_score": opportunity.validation_score,
        "window_hours": opportunity.window_hours,
        "estimated_investment": opportunity.estimated_investment,
        "estimated_return": opportunity.estimated_return,
        "roi_ratio": opportunity.roi_ratio,
        "decision": decision,
        "suggested_action": f"{opportunity.window_hours} 小时内做最小验证：{action_summary['first_step']}",
        "action_summary": action_summary,
        "validation_where": validation_where,
        "hot_reasons": _metric_reasons(metrics, signal, opportunity),
    }


def _source_bucket(source: SourceStatus) -> str:
    if source.status in {"needs_config", "third_party", "restricted"} or source.freshness == "not_configured":
        return "needs_config"
    if source.status in {"warning", "offline"} or source.freshness in {"stale", "offline"}:
        return "failed"
    if int(source.signal_count_24h or 0) <= 0:
        return "no_new"
    return "success"


def _brief_source_item(source: SourceStatus) -> dict[str, Any]:
    return {
        "id": source.id,
        "source": source.source,
        "status": source.status,
        "freshness": source.freshness,
        "signal_count_24h": source.signal_count_24h,
        "last_checked": source.last_checked.isoformat() if source.last_checked else None,
        "notes": source.notes,
    }


def _category_name(signal: Signal) -> str:
    text = " ".join([signal.circle or "", signal.type or "", signal.title or ""]).lower()
    if any(key in text for key in ["amazon", "shopify", "ecommerce", "电商", "商品"]):
        return "电商"
    if any(key in text for key in ["sec", "fund", "ipo", "investment", "融资", "投资", "机构"]):
        return "投资"
    if any(key in text for key in ["app store", "google play", "app", "应用"]):
        return "应用"
    if any(key in text for key in ["reddit", "social", "creator", "社区", "社交"]):
        return "社交"
    if any(key in text for key in ["ai", "agent", "llm", "github", "arxiv"]):
        return "AI"
    return signal.circle or "其他"


def _signal_brief_item(signal: Signal) -> dict[str, Any]:
    sources = _source_names(signal)
    return {
        "id": signal.id,
        "title": signal.title,
        "source": sources[0],
        "sources": sources,
        "score": signal.score,
        "level": signal.level,
        "type": signal.type,
        "circle": signal.circle,
        "region": signal.region,
        "reason": f"{signal.gap} / {signal.window} / {signal.roi_label}",
    }


def _brief_todo_items(top_opportunities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not top_opportunities:
        return [
            {
                "title": "先补充今日采集",
                "opportunity_id": None,
                "where": "运行采集管线并检查数据源状态",
                "budget": "0 元",
                "success_metric": "至少产生 5 条有效信号",
                "fail_metric": "核心来源仍无新增或失败",
            }
        ]
    todos: list[dict[str, Any]] = []
    for item in top_opportunities[:3]:
        summary = item.get("action_summary") or {}
        todos.append(
            {
                "title": item["title"],
                "opportunity_id": item["id"],
                "where": summary.get("first_step") or item["validation_where"],
                "budget": summary.get("budget") or item["estimated_investment"] or "小额预算",
                "success_metric": summary.get("success_metric") or "24-48 小时内拿到真实点击、收藏、评论或付费意向",
                "fail_metric": summary.get("fail_metric") or "曝光后无互动、评论指向伪需求，或获客成本明显过高",
            }
        )
    return todos


def _brief_risks(
    *,
    top_opportunities: list[dict[str, Any]],
    source_groups: dict[str, list[dict[str, Any]]],
    signal_count: int,
) -> list[str]:
    risks: list[str] = []
    high_risk = [item for item in top_opportunities if item["risk_level"] == "high" or item["crowding_score"] >= 75]
    if high_risk:
        risks.append(f"{len(high_risk)} 个候选机会拥挤或风险偏高，只适合观察或极小预算验证。")
    if source_groups["failed"]:
        risks.append(f"{len(source_groups['failed'])} 个数据源异常，今日结论需要降低置信度。")
    if source_groups["needs_config"]:
        risks.append(f"{len(source_groups['needs_config'])} 个高价值来源未配置，TikTok / Meta Ads / Amazon 等商业侧信号仍不完整。")
    if signal_count == 0:
        risks.append("最近 24 小时没有新信号，可能是采集未运行或来源无新增。")
    if not risks:
        risks.append("没有明显系统性风险，但所有机会仍建议先做小额验证。")
    return risks


async def _build_daily_brief_payload(db, now: datetime, signal_rows: list[Signal], op_rows: list[Opportunity]) -> dict[str, Any]:
    previous_since = now - timedelta(hours=48)
    previous_until = now - timedelta(hours=24)
    previous_signal_count = await db.scalar(
        select(func.count(Signal.id)).where(Signal.created_at >= previous_since).where(Signal.created_at < previous_until)
    ) or 0
    previous_opportunity_count = await db.scalar(
        select(func.count(Opportunity.id)).where(Opportunity.created_at >= previous_since).where(Opportunity.created_at < previous_until)
    ) or 0

    top_rows = sorted(op_rows, key=lambda item: (item.score, item.validation_score), reverse=True)[:6]
    top_opportunities = [
        await _opportunity_brief_item(db, opportunity, index + 1)
        for index, opportunity in enumerate(top_rows)
    ]
    actionable = [item for item in top_opportunities if item["decision"] == "优先执行"]
    watch_only = [item for item in top_opportunities if item["decision"] == "只观察"]

    source_rows = (await db.execute(select(SourceStatus).order_by(SourceStatus.source))).scalars().all()
    source_groups = {"success": [], "failed": [], "no_new": [], "needs_config": []}
    for source in source_rows:
        source_groups[_source_bucket(source)].append(_brief_source_item(source))

    categories: dict[str, list[dict[str, Any]]] = {}
    for signal in sorted(signal_rows, key=lambda item: item.score, reverse=True):
        category = _category_name(signal)
        categories.setdefault(category, []).append(_signal_brief_item(signal))
    signal_categories = [
        {"category": category, "count": len(items), "items": items[:5]}
        for category, items in sorted(categories.items(), key=lambda pair: len(pair[1]), reverse=True)
    ]

    market_events = (
        await db.execute(
            select(InstitutionEvent)
            .where(InstitutionEvent.detected_at >= now - timedelta(hours=24))
            .order_by(InstitutionEvent.detected_at.desc())
            .limit(5)
        )
    ).scalars().all()

    signal_delta = len(signal_rows) - int(previous_signal_count)
    opportunity_delta = len(op_rows) - int(previous_opportunity_count)
    headline = "今天没有明确可执行机会"
    if actionable:
        headline = f"今天有 {len(actionable)} 个可优先验证机会，先看「{actionable[0]['title']}」"
    elif top_opportunities:
        headline = f"今天有 {len(top_opportunities)} 个候选机会，但建议先观察验证"

    conclusion_bullets = [
        f"最近 24 小时新增 {len(signal_rows)} 条信号、{len(op_rows)} 个机会。",
        f"与上一窗口相比：信号 {'+' if signal_delta >= 0 else ''}{signal_delta}，机会 {'+' if opportunity_delta >= 0 else ''}{opportunity_delta}。",
        f"数据源：{len(source_groups['success'])} 个有新增，{len(source_groups['failed'])} 个异常，{len(source_groups['needs_config'])} 个待配置。",
    ]
    if top_opportunities:
        conclusion_bullets.append(f"Top 机会平均分 {round(sum(item['score'] for item in top_opportunities) / len(top_opportunities), 1)}。")

    return {
        "generated_by": "DailyBriefAgent",
        "date_key": now.strftime("%Y-%m-%d"),
        "metrics": {
            "signal_count": len(signal_rows),
            "opportunity_count": len(op_rows),
            "actionable_count": len(actionable),
            "watch_count": len(watch_only),
            "source_success_count": len(source_groups["success"]),
            "source_failed_count": len(source_groups["failed"]),
            "source_needs_config_count": len(source_groups["needs_config"]),
            "previous_signal_count": int(previous_signal_count),
            "previous_opportunity_count": int(previous_opportunity_count),
            "signal_delta": signal_delta,
            "opportunity_delta": opportunity_delta,
        },
        "today_conclusion": {
            "headline": headline,
            "recommended_action": "执行 Top 3 小验证" if actionable else "先补采集、再筛机会" if not top_opportunities else "观察验证，不重仓",
            "bullets": conclusion_bullets,
        },
        "top_opportunities": top_opportunities,
        "source_status": source_groups,
        "signal_categories": signal_categories,
        "market_events": [_serialize(event) for event in market_events],
        "todo": _brief_todo_items(top_opportunities),
        "risks": _brief_risks(top_opportunities=top_opportunities, source_groups=source_groups, signal_count=len(signal_rows)),
        "changes": {
            "previous_window": f"{previous_since.isoformat()} ~ {previous_until.isoformat()}",
            "signal_delta": signal_delta,
            "opportunity_delta": opportunity_delta,
        },
        "process_steps": [
            "定时采集",
            "清洗/中文化/去重",
            "机会评分",
            "证据链生成",
            "DailyBriefAgent 简报生成",
            "写入 Brief 并刷新缓存",
        ],
        "signals": [s.id for s in signal_rows],
        "opportunities": [o.id for o in op_rows],
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _prediction_category(signal: Signal) -> str:
    return _category_name(signal)


def _prediction_from_group(category: str, signals: list[Signal], rank: int) -> dict[str, Any]:
    top = sorted(signals, key=lambda item: item.score, reverse=True)[0]
    avg_score = round(sum(item.score for item in signals) / max(1, len(signals)), 1)
    sources = sorted({source for signal in signals for source in (signal.sources or [])})[:5]
    confidence = min(92, max(55, int(avg_score * 0.72 + min(len(signals), 12) * 2)))
    horizon_days = 7 if avg_score >= 82 else 14
    return {
        "id": _hash_id("pred", f"{category}:{top.title}:{len(signals)}", 16),
        "rank": rank,
        "title": f"预测机会：{category} 方向的「{top.title[:42]}」可验证需求",
        "category": category,
        "source": sources[0] if sources else "多来源信号",
        "sources": sources,
        "score": min(96, int(avg_score + min(len(signals), 8))),
        "confidence": confidence,
        "risk_level": "medium" if confidence < 76 else "low",
        "horizon_days": horizon_days,
        "reason": f"{len(signals)} 条相关信号在最近窗口聚集，平均信号分 {avg_score}",
        "suggested_action": f"{horizon_days} 天内做关键词页、竞品拆解或小额投放，验证是否有持续搜索/点击/收藏。",
        "rationale": [
            f"Top 信号：{top.title}",
            f"平均信号分：{avg_score}",
            f"来源覆盖：{'、'.join(sources) if sources else '单来源'}",
        ],
        "prediction": {
            "basis_signal_ids": [signal.id for signal in sorted(signals, key=lambda item: item.score, reverse=True)[:8]],
            "category": category,
            "horizon_days": horizon_days,
            "confidence": confidence,
            "generated_by": "PredictiveOpportunityAgent",
        },
    }


def _box_item_payload(row: OpportunityBoxItem) -> dict[str, Any]:
    return _serialize(row)


def _action_item_payload(
    action: ActionItem,
    opportunity: Opportunity | None = None,
    analysis: dict | None = None,
    analysis_title: str | None = None,
) -> dict[str, Any]:
    payload = _serialize(action)
    notes = action.step_notes if isinstance(action.step_notes, dict) else {}
    stored_summary = notes.get("action_summary") if isinstance(notes.get("action_summary"), dict) else None
    if opportunity is not None:
        title = analysis_title or _opportunity_title_payload(opportunity, None).get("title") or opportunity.playbook_name
        gate = _opportunity_gate(opportunity, None, {})
        summary = stored_summary or _action_summary_payload(
            opportunity,
            merchant_analysis=analysis or {},
            gate=gate,
            title=title,
        )
    else:
        title = action.opportunity_id
        summary = stored_summary or {
            "first_step": "打开机会详情补充执行上下文",
            "validation_plan": ["打开机会详情补充执行上下文"],
            "success_metric": "能确认当前执行项对应的机会和下一步",
            "budget": "小额预算",
            "roi": "待验证",
        }
    plan = notes.get("plan") if isinstance(notes.get("plan"), list) else None
    if not plan:
        plan = _action_plan_from_steps(_list_from_value(summary.get("validation_plan")))
    labels = [str(item.get("label") or "") for item in plan if isinstance(item, dict) and item.get("label")]
    current_index = max(0, min(int(action.current_step or 0), max(0, len(labels) - 1)))
    next_index = min(current_index + 1, max(0, len(labels) - 1))
    current_step_label = labels[current_index] if labels else summary.get("first_step", "推进当前验证")
    if action.status == "completed":
        next_step_label = "提交或查看复盘"
    elif labels and action.current_step + 1 < len(labels):
        next_step_label = labels[next_index]
    else:
        next_step_label = "完成验证并提交复盘"
    success_metric = summary.get("success_metric") or "拿到真实点击、回复、收藏、询价、试用或付费意向"
    if plan and current_index < len(plan) and isinstance(plan[current_index], dict):
        success_metric = plan[current_index].get("success_metric") or success_metric

    payload.update(
        {
            "opportunity_title": title,
            "current_step_label": current_step_label,
            "next_step_label": next_step_label,
            "success_metric": success_metric,
            "action_summary": summary,
        }
    )
    return payload


@router.get("/opportunities")
async def opportunities(
    sort: Optional[str] = Query(default="evidence_at"),
    playbook: Optional[str] = Query(default=None),
    circle: Optional[str] = Query(default=None),
    level: Optional[str] = Query(default="all"),
    stage: Optional[str] = Query(default="all"),
    recency: Optional[str] = Query(default="all"),
    data_type: Optional[str] = Query(default="all"),
    limit: int = 20,
    db=Depends(get_db),
):
    try:
        async def load():
            stmt = (
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
                    Opportunity.risk_factors,
                    Opportunity.bear_case,
                    Opportunity.validation_score,
                    Opportunity.difficulty,
                    Opportunity.estimated_investment,
                    Opportunity.estimated_return,
                    Opportunity.roi_ratio,
                    Opportunity.breakeven,
                    Opportunity.max_loss,
                    Opportunity.execution_status,
                    Opportunity.current_step,
                    Opportunity.status,
                    Opportunity.created_at,
                    OpportunityAnalysis.title.label("analysis_title"),
                    OpportunityAnalysis.evidence_title.label("analysis_evidence_title"),
                    OpportunityAnalysis.source.label("analysis_source"),
                    OpportunityAnalysis.analysis.label("analysis_payload"),
                    func.count(Opportunity.id).over().label("total_count"),
                )
                .outerjoin(
                    OpportunityAnalysis,
                    OpportunityAnalysis.opportunity_id == Opportunity.id,
                )
                .where(Opportunity.status != "filtered")
            )
            if playbook:
                stmt = stmt.where(Opportunity.playbook == playbook)
            if level and level != "all":
                stmt = stmt.where(Opportunity.level == level.upper())
            if circle:
                stmt = stmt.join(Signal, Signal.id == Opportunity.signal_id, isouter=True).where(Signal.circle == circle)
            if sort == "created_at" or sort == "evidence_at":
                stmt = stmt.order_by(Opportunity.created_at.desc())
            elif sort == "level":
                level_rank = case(
                    (Opportunity.level == "S", 0),
                    (Opportunity.level == "A", 1),
                    (Opportunity.level == "B", 2),
                    (Opportunity.level == "C", 3),
                    else_=4,
                )
                stmt = stmt.order_by(level_rank.asc(), Opportunity.score.desc(), Opportunity.created_at.desc())
            elif sort == "window_hours":
                stmt = stmt.order_by(Opportunity.window_hours.asc(), Opportunity.score.desc())
            else:
                stmt = stmt.order_by(Opportunity.score.desc())
            post_filtering = any(
                value and value != "all"
                for value in (stage, recency, data_type)
            )
            requested_limit = max(1, min(limit, 200))
            candidate_limit = min(250, requested_limit * 4) if post_filtering else requested_limit
            rows = (await db.execute(stmt.limit(candidate_limit))).all()
            now = datetime.utcnow()
            all_items = [
                _opportunity_list_payload_from_row(row, now=now)
                for row in rows
            ]
            if stage and stage != "all":
                all_items = [item for item in all_items if item.get("opportunity_stage") == stage]
            if recency and recency != "all":
                all_items = [item for item in all_items if item.get("content_recency") == recency]
            if data_type and data_type != "all":
                all_items = [item for item in all_items if item.get("data_type") == data_type]
            if sort == "evidence_at":
                all_items = sorted(
                    all_items,
                    key=lambda item: (
                        item.get("evidence_published_at") or item.get("created_at") or datetime.min,
                        item.get("score") or 0,
                    ),
                    reverse=True,
                )
            total_all = int(rows[0].total_count or 0) if rows else 0
            filtered_total = len(all_items)
            if not post_filtering:
                filtered_total = total_all
            limited_items = all_items[:requested_limit]
            return {
                "items": limited_items,
                "total": filtered_total,
                "total_all": total_all,
            }

        key = f"api:opportunities:list:v8:{sort}:{playbook or 'all'}:{circle or 'all'}:{level or 'all'}:{stage or 'all'}:{recency or 'all'}:{data_type or 'all'}:{limit}"
        return _response_success(await cached(key, 300, load))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/opportunities/{opportunity_id}")
async def opportunity_detail(opportunity_id: str, db=Depends(get_db)):
    async def load():
        opportunity = await db.get(Opportunity, opportunity_id)
        if not opportunity:
            raise HTTPException(status_code=404, detail="opportunity not found")
        signal = await db.get(Signal, opportunity.signal_id)
        dimensions = opportunity.dimensions or {}
        clean = await db.get(CleanItem, dimensions.get("clean_item_id")) if dimensions.get("clean_item_id") else None
        raw = await db.get(RawItem, dimensions.get("raw_item_id")) if dimensions.get("raw_item_id") else None
        if clean is None:
            clean = await _find_clean_for_signal(db, opportunity.signal_id, signal)
        if raw is None and clean is not None:
            raw = await db.get(RawItem, clean.raw_item_id)
        source_rows = (await db.execute(select(SourceStatus))).scalars().all()
        source_statuses = {row.source: row for row in source_rows}
        analysis_row = await _get_or_create_opportunity_analysis(db, opportunity, signal, clean, raw)
        await db.commit()
        return {
            "opportunity": _opportunity_payload(
                opportunity,
                signal,
                source_statuses,
                clean,
                raw,
                merchant_analysis=analysis_row.analysis if analysis_row else None,
            ),
            "signal": _serialize(signal) if signal else None,
            "evidence": _evidence_payload(
                opportunity=opportunity,
                signal=signal,
                clean=clean,
                raw=raw,
                merchant_analysis=analysis_row.analysis if analysis_row else None,
            ),
            "analysis": _serialize(analysis_row),
            "deep_analysis": (analysis_row.analysis or {}).get("deep_analysis") if analysis_row else None,
            "risk": _opportunity_risk_payload(opportunity),
            "validation": _opportunity_validation_payload(opportunity),
            "roi": _opportunity_roi_payload(opportunity),
            "oci": _opportunity_oci_payload(opportunity),
        }

    return _response_success(await cached(f"api:opportunity:detail:v12:{opportunity_id}", 120, load))


@router.get("/opportunities/{opportunity_id}/risk")
async def opportunity_risk(opportunity_id: str, db=Depends(get_db)):
    opportunity = await db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return _response_success(_opportunity_risk_payload(opportunity))


@router.get("/opportunities/{opportunity_id}/validation")
async def opportunity_validation(opportunity_id: str, db=Depends(get_db)):
    opportunity = await db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return _response_success(_opportunity_validation_payload(opportunity))


@router.get("/opportunities/{opportunity_id}/roi")
async def opportunity_roi(opportunity_id: str, capital: Optional[float] = Query(default=None), db=Depends(get_db)):
    opportunity = await db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return _response_success(_opportunity_roi_payload(opportunity, capital))


@router.post("/opportunities/{opportunity_id}/deep-analysis")
async def opportunity_deep_analysis(opportunity_id: str, db=Depends(get_db)):
    opportunity = await db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="opportunity not found")
    signal = await db.get(Signal, opportunity.signal_id)
    dimensions = opportunity.dimensions or {}
    clean = await db.get(CleanItem, dimensions.get("clean_item_id")) if dimensions.get("clean_item_id") else None
    raw = await db.get(RawItem, dimensions.get("raw_item_id")) if dimensions.get("raw_item_id") else None
    if clean is None:
        clean = await _find_clean_for_signal(db, opportunity.signal_id, signal)
    if raw is None and clean is not None:
        raw = await db.get(RawItem, clean.raw_item_id)

    analysis_row = await _get_or_create_opportunity_analysis(db, opportunity, signal, clean, raw)
    merchant_analysis = analysis_row.analysis or {}
    evidence = _evidence_payload(
        opportunity=opportunity,
        signal=signal,
        clean=clean,
        raw=raw,
        merchant_analysis=merchant_analysis,
    )
    fallback_analysis = _build_deep_opportunity_analysis(
        opportunity=opportunity,
        signal=signal,
        evidence=evidence,
        merchant_analysis=merchant_analysis,
    )
    deep_analysis = await _maybe_generate_glm_deep_analysis(fallback_analysis)
    merged_analysis = dict(merchant_analysis)
    merged_analysis["deep_analysis"] = deep_analysis
    analysis_row.analysis = merged_analysis
    analysis_row.generated_by = deep_analysis.get("generated_by", "DeepOpportunityAnalyst")
    analysis_row.updated_at = datetime.utcnow()
    await db.commit()
    await cache_delete_pattern("api:opportunity:detail:*")
    return _response_success(
        {
            "opportunity_id": opportunity_id,
            "deep_analysis": deep_analysis,
            "message": "AI 深入分析已生成",
        }
    )


@router.post("/opportunities/{opportunity_id}/execute")
async def execute_opportunity(
    opportunity_id: str,
    payload: ActionItemPayload | None = None,
    db=Depends(get_db),
):
    opportunity = await db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="opportunity not found")
    signal = await db.get(Signal, opportunity.signal_id)
    source_rows = (await db.execute(select(SourceStatus))).scalars().all()
    gate = _opportunity_gate(opportunity, signal, {row.source: row for row in source_rows})
    if not gate["execution_gate_passed"]:
        return SuccessResponse(
            success=False,
            error="该机会暂未满足可执行门槛",
            data={
                "opportunity_id": opportunity_id,
                "opportunity_stage": gate["opportunity_stage"],
                "execution_blockers": gate["execution_blockers"],
            },
        ).dict()
    analysis_row = await db.get(OpportunityAnalysis, opportunity_id)
    title_payload = _opportunity_title_payload(opportunity, signal)
    action_summary = _action_summary_payload(
        opportunity,
        signal=signal,
        merchant_analysis=analysis_row.analysis if analysis_row else None,
        gate=gate,
        source=title_payload.get("source"),
        title=title_payload.get("business_title") or title_payload.get("title"),
    )
    action_plan = action_summary.get("action_plan") or _action_plan_from_steps(opportunity.strategies or [])
    action = ActionItem(
        id=f"ac-{uuid4().hex[:10]}",
        opportunity_id=opportunity_id,
        user_id=DEFAULT_USER,
        playbook=opportunity.playbook,
        total_steps=max(1, len(action_plan)),
        current_step=0,
        step_notes={
            "plan": action_plan,
            "action_summary": action_summary,
        },
        status="in_progress",
        signal_heat_at_start=float(opportunity.score),
        signal_heat_current=float(opportunity.score),
        heat_change_pct=0.0,
        result="pending",
    )
    db.add(action)
    opportunity.execution_status = "in_progress"
    await db.commit()
    await cache_delete_pattern("api:opportunity:detail:*")
    await cache_delete_pattern("api:opportunities:list:*")
    return _response_success(
        {
            "opportunity_id": opportunity_id,
            "action": _action_item_payload(
                action,
                opportunity=opportunity,
                analysis=analysis_row.analysis if analysis_row else None,
                analysis_title=analysis_row.title if analysis_row else None,
            ),
            "message": f"execution started for {payload.opportunity_id if payload and payload.opportunity_id else opportunity_id}",
        }
    )


@router.get("/actions")
async def actions(status: Optional[str] = Query(default=None), limit: int = 20, db=Depends(get_db)):
    try:
        stmt = select(ActionItem).where(ActionItem.user_id == DEFAULT_USER)
        if status:
            stmt = stmt.where(ActionItem.status == status)
        stmt = stmt.order_by(ActionItem.started_at.desc()).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
        items = []
        for row in rows:
            opportunity = await db.get(Opportunity, row.opportunity_id)
            analysis_row = await db.get(OpportunityAnalysis, row.opportunity_id) if opportunity is not None else None
            items.append(
                _action_item_payload(
                    row,
                    opportunity=opportunity,
                    analysis=analysis_row.analysis if analysis_row else None,
                    analysis_title=analysis_row.title if analysis_row else None,
                )
            )
        return _response_success({"items": items, "total": len(items)})
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/actions/{action_id}")
async def action_detail(action_id: str, db=Depends(get_db)):
    action = await db.get(ActionItem, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="action not found")
    opportunity = await db.get(Opportunity, action.opportunity_id)
    analysis_row = await db.get(OpportunityAnalysis, action.opportunity_id) if opportunity is not None else None
    return _response_success(
        {
            "action": _action_item_payload(
                action,
                opportunity=opportunity,
                analysis=analysis_row.analysis if analysis_row else None,
                analysis_title=analysis_row.title if analysis_row else None,
            ),
            "opportunity": _serialize(opportunity) if opportunity else None,
        }
    )


@router.put("/actions/{action_id}/progress")
async def action_progress(action_id: str, payload: ActionProgressPayload, db=Depends(get_db)):
    action = await db.get(ActionItem, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="action not found")
    notes = action.step_notes or {}
    if not isinstance(notes, dict):
        notes = {}
    notes[str(payload.current_step)] = payload.note or ""
    action.current_step = max(0, min(payload.current_step, action.total_steps))
    action.step_notes = notes
    if action.current_step >= action.total_steps:
        action.status = "completed"
        action.completed_at = datetime.utcnow()
    await db.commit()
    await cache_delete_pattern("api:opportunity:detail:*")
    return _response_success({"action_id": action_id, "status": action.status, "current_step": action.current_step})


@router.post("/actions/{action_id}/review")
async def action_review(action_id: str, payload: ActionReviewPayload, db=Depends(get_db)):
    action = await db.get(ActionItem, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="action not found")
    if payload.result:
        action.result = payload.result
    if payload.amount is not None:
        action.return_amount = payload.amount
    action.rating = payload.rating
    action.review_notes = payload.notes
    action.reviewed_at = datetime.utcnow()
    action.status = "completed"
    opportunity = await db.get(Opportunity, action.opportunity_id)
    if opportunity:
        opportunity.execution_status = "completed"
    await db.commit()
    await cache_delete_pattern("api:opportunity:detail:*")
    return _response_success(
        {
            "action_id": action_id,
            "result": payload.result,
            "rating": payload.rating,
            "review": payload.notes,
        }
    )


@router.get("/backtest/stats")
async def backtest_stats(days: int = Query(default=90), db=Depends(get_db)):
    since = datetime.utcnow() - timedelta(days=max(1, days))
    rows = (await db.execute(select(BacktestCase).where(BacktestCase.created_at >= since))).scalars().all()
    total_cases = sum(row.total_cases for row in rows)
    win_cases = sum(row.win_cases for row in rows)
    avg_hit = round(sum(row.hit_rate for row in rows) / max(1, len(rows)), 4)
    summary = {
        "days": days,
        "cases": len(rows),
        "total_cases": total_cases,
        "win_cases": win_cases,
        "overall_win_rate": round(win_cases / total_cases, 4) if total_cases else 0,
        "avg_hit_rate": avg_hit,
        "playbooks": {},
    }
    for row in rows:
        item = summary["playbooks"].setdefault(row.playbook, {"cases": 0, "win": 0, "avg_roi": []})
        item["cases"] += row.total_cases
        item["win"] += row.win_cases
        item["avg_roi"].append(row.avg_roi)
    for key, value in summary["playbooks"].items():
        value["win_rate"] = round(value["win"] / max(1, value["cases"]), 4)
    return _response_success(summary)


@router.get("/backtest/cases")
async def backtest_cases(
    playbook: Optional[str] = Query(default=None),
    result: Optional[str] = Query(default=None),
    limit: int = 20,
    db=Depends(get_db),
):
    stmt = select(BacktestCase)
    if playbook:
        stmt = stmt.where(BacktestCase.playbook == playbook)
    if result:
        stmt = stmt.where(BacktestCase.result == result)
    stmt = stmt.order_by(BacktestCase.created_at.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return _response_success({"items": [_serialize(r) for r in rows], "total": len(rows)})


@router.get("/sources/status")
async def sources_status(db=Depends(get_db)):
    async def load():
        rows = (await db.execute(select(SourceStatus).order_by(SourceStatus.source))).scalars().all()
        now = datetime.utcnow()
        return {"items": [_source_status_payload(row, now) for row in rows], "total": len(rows)}

    return _response_success(await cached("api:sources:status:v3", 60, load))


@router.get("/circles/stats")
async def circles_stats(hours: int = Query(default=24), db=Depends(get_db)):
    async def load():
        since = datetime.utcnow() - timedelta(hours=max(1, hours))
        rows = await db.execute(
            select(Signal.circle, func.count(Signal.id).label("count"), func.avg(Signal.score).label("avg_score"))
            .where(Signal.created_at >= since)
            .group_by(Signal.circle)
        )
        items = [
            {"circle": circle, "count": int(count), "avg_score": round(float(avg_score or 0), 2)}
            for circle, count, avg_score in rows
        ]
        return {"hours": hours, "items": items}

    return _response_success(await cached(f"api:circles:stats:{hours}", 90, load))


@router.get("/regions/stats")
async def regions_stats(hours: int = Query(default=24), db=Depends(get_db)):
    async def load():
        since = datetime.utcnow() - timedelta(hours=max(1, hours))
        rows = await db.execute(
            select(Signal.region, func.count(Signal.id).label("count"), func.avg(Signal.score).label("avg_score"))
            .where(Signal.created_at >= since)
            .group_by(Signal.region)
        )
        items = [
            {"region": region, "count": int(count), "avg_score": round(float(avg_score or 0), 2)}
            for region, count, avg_score in rows
        ]
        return {"hours": hours, "items": items}

    return _response_success(await cached(f"api:regions:stats:{hours}", 90, load))


@router.get("/institutions/events")
async def institutions_events(
    institution_type: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    limit: int = 20,
    db=Depends(get_db),
):
    stmt = select(InstitutionEvent).order_by(InstitutionEvent.detected_at.desc())
    if institution_type:
        stmt = stmt.where(InstitutionEvent.institution_type == institution_type)
    if event_type:
        stmt = stmt.where(InstitutionEvent.event_type == event_type)
    rows = (await db.execute(stmt.limit(limit))).scalars().all()
    return _response_success({"items": [_serialize(r) for r in rows], "total": len(rows)})


@router.get("/preferences")
async def preferences(db=Depends(get_db)):
    rows = (await db.execute(select(UserPreference).where(UserPreference.user_id == DEFAULT_USER))).scalars().all()
    return _response_success({"items": [_serialize(r) for r in rows], "total": len(rows)})


@router.put("/preferences")
async def update_preferences(payload: PreferencePayload, db=Depends(get_db)):
    existing = (await db.execute(
        select(UserPreference).where(and_(UserPreference.user_id == DEFAULT_USER, UserPreference.dimension == payload.dimension))
    )).scalar_one_or_none()
    if existing:
        existing.value = payload.value
        existing.weight = payload.weight
        existing.updated_at = datetime.utcnow()
        item = existing
    else:
        item = UserPreference(
            id=f"pref-{uuid4().hex[:10]}",
            user_id=DEFAULT_USER,
            dimension=payload.dimension,
            value=payload.value,
            weight=payload.weight,
            updated_at=datetime.utcnow(),
        )
        db.add(item)
    await db.commit()
    return _response_success(_serialize(item))


@router.get("/user/profile")
async def user_profile(db=Depends(get_db)):
    profile = await db.get(UserProfile, DEFAULT_USER)
    if not profile:
        profile = UserProfile(user_id=DEFAULT_USER, tier="starter", role="guest", circles="", regions="", capital="", risk_appetite="medium")
        db.add(profile)
        await db.commit()
    return _response_success(_serialize(profile))


@router.put("/user/profile")
async def user_profile_update(payload: UserProfilePayload, db=Depends(get_db)):
    profile = await db.get(UserProfile, DEFAULT_USER)
    if not profile:
        profile = UserProfile(
            user_id=DEFAULT_USER,
            tier=payload.tier or "starter",
            role=payload.role or "guest",
            circles=",".join(payload.circles),
            regions=",".join(payload.regions),
            capital=payload.capital or "",
            risk_appetite=payload.risk_appetite,
        )
        db.add(profile)
    else:
        if payload.tier is not None:
            profile.tier = payload.tier
        if payload.role is not None:
            profile.role = payload.role
        if payload.circles is not None:
            profile.circles = ",".join(payload.circles)
        if payload.regions is not None:
            profile.regions = ",".join(payload.regions)
        if payload.capital is not None:
            profile.capital = payload.capital
        if payload.risk_appetite is not None:
            profile.risk_appetite = payload.risk_appetite
        profile.updated_at = datetime.utcnow()
    await db.commit()
    return _response_success(_serialize(profile))


@router.post("/user/onboarding")
async def user_onboarding(payload: OnboardingPayload, db=Depends(get_db)):
    profile = await db.get(UserProfile, DEFAULT_USER)
    if not profile:
        profile = UserProfile(
            user_id=DEFAULT_USER,
            tier="starter",
            role=payload.role,
            circles=",".join(payload.circles),
            regions=payload.region,
            capital=payload.capital,
            risk_appetite=payload.risk_appetite or "medium",
        )
        db.add(profile)
    else:
        profile.role = payload.role
        profile.circles = ",".join(payload.circles)
        profile.regions = payload.region
        profile.capital = payload.capital
        profile.risk_appetite = payload.risk_appetite or profile.risk_appetite
        profile.updated_at = datetime.utcnow()
    await db.commit()
    return _response_success({"status": "ok", "user_id": DEFAULT_USER})


@router.get("/knowledge")
async def knowledge(
    category: Optional[str] = Query(default=None),
    playbook: Optional[str] = Query(default=None),
    db=Depends(get_db),
):
    stmt = select(KnowledgeArticle).order_by(KnowledgeArticle.created_at.desc())
    if category:
        stmt = stmt.where(KnowledgeArticle.category == category)
    if playbook:
        stmt = stmt.where(KnowledgeArticle.playbook == playbook)
    rows = (await db.execute(stmt)).scalars().all()
    return _response_success({"items": [_serialize(r) for r in rows], "total": len(rows)})


@router.get("/knowledge/{article_id}")
async def knowledge_detail(article_id: str, db=Depends(get_db)):
    article = await db.get(KnowledgeArticle, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="article not found")
    return _response_success(_serialize(article))


@router.post("/pipeline/run")
async def run_pipeline(payload: PipelineRunPayload, background_tasks: BackgroundTasks, db=Depends(get_db)):
    running = (
        await db.execute(
            select(PipelineRun)
            .where(PipelineRun.status == "running")
            .where(PipelineRun.started_at >= datetime.utcnow() - timedelta(minutes=15))
            .order_by(PipelineRun.started_at.desc())
            .limit(1)
        )
    ).scalars().first()
    if running:
        return _response_success(_serialize(running))

    target_sources = [source for source in dict.fromkeys(payload.sources or []) if source]
    run = PipelineRun(
        id=f"pipe-{uuid4().hex[:10]}",
        steps=payload.steps,
        status="running",
        started_at=datetime.utcnow(),
        finished_at=None,
        message=(
            f"real pipeline queued for {len(target_sources)} target sources"
            if target_sources
            else "real pipeline queued"
        ),
    )
    db.add(run)
    await db.commit()
    await cache_delete_pattern("api:pipeline:status")
    background_tasks.add_task(_execute_pipeline_run, run.id, target_sources or None)
    return _response_success(_serialize(run))


@router.get("/pipeline/status")
async def pipeline_status(db=Depends(get_db)):
    async def load():
        run = (await db.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(1))).scalars().first()
        if not run:
            return {"status": "idle"}
        return _serialize(run)

    return _response_success(await cached("api:pipeline:status", 15, load))


@router.get("/brief/latest")
async def brief_latest(db=Depends(get_db)):
    async def load():
        brief = (await db.execute(select(Brief).order_by(Brief.created_at.desc()).limit(1))).scalars().first()
        if not brief:
            return {"summary": "", "items": []}
        return _serialize(brief)

    return _response_success(await cached("api:brief:latest", 90, load))


@router.get("/brief/history")
async def brief_history(days: int = Query(default=30), db=Depends(get_db)):
    async def load():
        since = datetime.utcnow() - timedelta(days=max(1, days))
        rows = (await db.execute(select(Brief).where(Brief.created_at >= since).order_by(Brief.created_at.desc()))).scalars().all()
        return {"items": [_serialize(r) for r in rows], "total": len(rows)}

    return _response_success(await cached(f"api:brief:history:{days}", 120, load))


@router.post("/brief/generate")
async def generate_brief(db=Depends(get_db)):
    now = datetime.utcnow()
    local_now = now + timedelta(hours=8)
    date_key = local_now.strftime("%Y-%m-%d")
    signal_rows = (
        await db.execute(
            select(Signal)
            .where(Signal.created_at >= now - timedelta(hours=24))
            .order_by(Signal.score.desc(), Signal.created_at.desc())
        )
    ).scalars().all()
    op_rows = (
        await db.execute(
            select(Opportunity)
            .where(Opportunity.created_at >= now - timedelta(hours=24))
            .where(Opportunity.status != "filtered")
            .order_by(Opportunity.score.desc(), Opportunity.created_at.desc())
        )
    ).scalars().all()
    payload = await _build_daily_brief_payload(db, now, signal_rows, op_rows)
    payload["date_key"] = date_key
    payload = _json_safe(payload)
    headline = payload["today_conclusion"]["headline"]
    brief = Brief(
        id=f"brief-{uuid4().hex[:10]}",
        date_key=date_key,
        title=f"每日行动简报 - {date_key}",
        summary=headline,
        payload=payload,
        created_at=now,
    )
    db.add(brief)
    await db.commit()
    await cache_delete_pattern("api:brief:*")
    return _response_success(_serialize(brief))


@router.get("/sources/freshness")
async def sources_freshness(db=Depends(get_db)):
    return await sources_status(db)


@router.get("/sources/{source_id}/freshness")
async def source_freshness(source_id: str, db=Depends(get_db)):
    row = await db.execute(select(SourceStatus).where(or_(SourceStatus.id == source_id, SourceStatus.source == source_id)))
    source = row.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="source not found")
    return _response_success(_source_status_payload(source))


@router.get("/scenarios/presets")
async def scenario_presets(db=Depends(get_db)):
    async def load():
        rows = (await db.execute(select(ScenarioPreset).order_by(ScenarioPreset.name))).scalars().all()
        return {"items": [_serialize(r) for r in rows], "total": len(rows)}

    return _response_success(await cached("api:scenarios:presets", 300, load))


@router.post("/scenarios/analyze")
async def scenario_analyze(payload: ScenarioAnalyzePayload, db=Depends(get_db)):
    preset = None
    if payload.preset_id:
        preset = await db.get(ScenarioPreset, payload.preset_id)
    record = ScenarioHistory(
        id=f"scanh-{uuid4().hex[:10]}",
        preset_id=payload.preset_id,
        scenario=payload.scenario,
        result=f"Scenario analysis completed for {payload.scenario}",
        confidence=0.84,
    )
    if preset:
        record.result = f"Matched preset {preset.name}: {preset.description}"
    db.add(record)
    await db.commit()
    await cache_delete_pattern("api:scenarios:history:*")
    return _response_success(_serialize(record))


@router.get("/scenarios/history")
async def scenario_history(limit: int = 20, db=Depends(get_db)):
    async def load():
        rows = (await db.execute(select(ScenarioHistory).order_by(ScenarioHistory.created_at.desc()).limit(limit))).scalars().all()
        return {"items": [_serialize(r) for r in rows], "total": len(rows)}

    return _response_success(await cached(f"api:scenarios:history:{limit}", 60, load))


@router.get("/signals/{signal_id}/convergence")
async def signal_convergence(signal_id: str, db=Depends(get_db)):
    signal = await db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="signal not found")
    peers = (
        await db.execute(
            select(Signal)
            .where(
                and_(
                    Signal.id != signal_id,
                    Signal.circle == signal.circle,
                    Signal.type == signal.type,
                )
            )
            .limit(5)
        )
    ).scalars().all()
    return _response_success(
        {
            "signal_id": signal_id,
            "convergence_tag": signal.convergence or "medium",
            "related_signals": [peer.id for peer in peers],
            "source_count": len(signal.sources or []),
            "coverage": {
                "circle": signal.circle,
                "region": signal.region,
                "type": signal.type,
            },
        }
    )


@router.get("/opportunities/{opportunity_id}/oci")
async def opportunity_oci(opportunity_id: str, db=Depends(get_db)):
    opportunity = await db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return _response_success(_opportunity_oci_payload(opportunity))


@router.get("/opportunity-box")
async def opportunity_box(status: Optional[str] = Query(default=None), db=Depends(get_db)):
    async def load():
        stmt = select(OpportunityBoxItem).where(OpportunityBoxItem.user_id == DEFAULT_USER)
        if status:
            stmt = stmt.where(OpportunityBoxItem.status == status)
        stmt = stmt.order_by(OpportunityBoxItem.updated_at.desc(), OpportunityBoxItem.created_at.desc())
        rows = (await db.execute(stmt)).scalars().all()
        return {"items": [_box_item_payload(row) for row in rows], "total": len(rows)}

    return _response_success(await cached(f"api:opportunity-box:{status or 'all'}", 60, load))


@router.post("/opportunity-box")
async def save_opportunity_box(payload: OpportunityBoxPayload, db=Depends(get_db)):
    existing = None
    if payload.opportunity_id:
        existing = (
            await db.execute(
                select(OpportunityBoxItem)
                .where(OpportunityBoxItem.user_id == DEFAULT_USER)
                .where(OpportunityBoxItem.opportunity_id == payload.opportunity_id)
                .limit(1)
            )
        ).scalar_one_or_none()
    prediction_id = (payload.prediction or {}).get("prediction_id") or (payload.prediction or {}).get("id")
    if existing is None and prediction_id:
        candidates = (
            await db.execute(
                select(OpportunityBoxItem)
                .where(OpportunityBoxItem.user_id == DEFAULT_USER)
                .where(OpportunityBoxItem.source_type == "predicted")
            )
        ).scalars().all()
        for candidate in candidates:
            candidate_prediction_id = (candidate.prediction or {}).get("prediction_id") or (candidate.prediction or {}).get("id")
            if candidate_prediction_id == prediction_id:
                existing = candidate
                break

    opportunity = await db.get(Opportunity, payload.opportunity_id) if payload.opportunity_id else None
    signal = await db.get(Signal, opportunity.signal_id) if opportunity is not None else None
    clean = None
    if opportunity is not None:
        dimensions = opportunity.dimensions or {}
        clean = await db.get(CleanItem, dimensions.get("clean_item_id")) if dimensions.get("clean_item_id") else None
        if clean is None:
            clean = await _find_clean_for_signal(db, opportunity.signal_id, signal)
    title_payload = _opportunity_title_payload(opportunity, signal, clean) if opportunity is not None else {}
    title = payload.title or title_payload.get("title") or (signal.title if signal is not None else None) or (opportunity.playbook_name if opportunity is not None else "未命名机会")
    source_names = _source_names(signal) if signal is not None else []
    source = payload.source or (source_names[0] if source_names else "预测机会")
    prediction_payload = dict(payload.prediction or {})
    if opportunity is not None:
        analysis_row = await db.get(OpportunityAnalysis, opportunity.id)
        gate = _opportunity_gate(opportunity, signal, {})
        prediction_payload["action_summary"] = _action_summary_payload(
            opportunity,
            signal=signal,
            merchant_analysis=analysis_row.analysis if analysis_row else None,
            gate=gate,
            source=source,
            title=title,
        )
    now = datetime.utcnow()
    if existing is None:
        existing = OpportunityBoxItem(
            id=f"box-{uuid4().hex[:10]}",
            user_id=DEFAULT_USER,
            opportunity_id=payload.opportunity_id,
            source_type=payload.source_type,
            title=title[:240],
            source=source[:80],
            score=payload.score if payload.score is not None else (opportunity.score if opportunity is not None else 0),
            risk_level=payload.risk_level or (opportunity.risk_level if opportunity is not None else "medium"),
            status=payload.status,
            rationale=payload.rationale,
            prediction=prediction_payload or None,
            notes=payload.notes,
            created_at=now,
            updated_at=now,
        )
        db.add(existing)
    else:
        existing.source_type = payload.source_type or existing.source_type
        existing.title = title[:240]
        existing.source = source[:80]
        existing.score = payload.score if payload.score is not None else existing.score
        existing.risk_level = payload.risk_level or existing.risk_level
        existing.status = payload.status or existing.status
        existing.rationale = payload.rationale or existing.rationale
        existing.prediction = prediction_payload or existing.prediction
        existing.notes = payload.notes if payload.notes is not None else existing.notes
        existing.updated_at = now
    await db.commit()
    await cache_delete_pattern("api:opportunity-box:*")
    return _response_success(_box_item_payload(existing))


@router.delete("/opportunity-box/{item_id}")
async def delete_opportunity_box(item_id: str, db=Depends(get_db)):
    item = await db.get(OpportunityBoxItem, item_id)
    if not item or item.user_id != DEFAULT_USER:
        raise HTTPException(status_code=404, detail="box item not found")
    await db.delete(item)
    await db.commit()
    await cache_delete_pattern("api:opportunity-box:*")
    return _response_success({"deleted": item_id})


@router.get("/opportunity-box/predictions")
async def opportunity_predictions(hours: int = Query(default=72), limit: int = 8, db=Depends(get_db)):
    async def load():
        since = datetime.utcnow() - timedelta(hours=max(24, hours))
        signals = (
            await db.execute(
                select(Signal)
                .where(Signal.created_at >= since)
                .where(Signal.score >= 68)
                .order_by(Signal.score.desc(), Signal.created_at.desc())
                .limit(240)
            )
        ).scalars().all()
        grouped: dict[str, list[Signal]] = {}
        for signal in signals:
            grouped.setdefault(_prediction_category(signal), []).append(signal)
        predictions = [
            _prediction_from_group(category, items, index + 1)
            for index, (category, items) in enumerate(
                sorted(grouped.items(), key=lambda pair: (len(pair[1]), max(item.score for item in pair[1])), reverse=True)[:limit]
            )
        ]
        saved_rows = (
            await db.execute(select(OpportunityBoxItem).where(OpportunityBoxItem.user_id == DEFAULT_USER))
        ).scalars().all()
        saved_prediction_ids = {
            (row.prediction or {}).get("prediction_id") or (row.prediction or {}).get("id")
            for row in saved_rows
            if row.prediction
        }
        for prediction in predictions:
            prediction["saved"] = prediction["id"] in saved_prediction_ids
            prediction["prediction"]["id"] = prediction["id"]
            prediction["prediction"]["prediction_id"] = prediction["id"]
        return {"items": predictions, "total": len(predictions), "hours": hours}

    return _response_success(await cached(f"api:opportunity-box:predictions:{hours}:{limit}", 90, load))
