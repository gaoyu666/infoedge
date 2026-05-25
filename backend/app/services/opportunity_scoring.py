from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEMAND_SOURCES = ("Google Trends", "Reddit", "Amazon", "Google Play", "Apple App Store", "Product Hunt", "Polymarket", "CoinGecko")
SUPPLY_SOURCES = ("Shopify", "Amazon", "GitHub", "1688", "Temu", "USGS", "GDACS")
MOMENTUM_SOURCES = ("Google Trends", "Product Hunt", "HackerNews", "TechCrunch", "36Kr", "SEC EDGAR", "GDELT", "BBC", "Al Jazeera", "Polymarket", "CoinGecko", "CISA")
COMPETITION_SOURCES = ("Product Hunt", "Apple App Store", "Google Play", "Amazon", "Meta", "TikTok", "CoinGecko")
INVESTMENT_SOURCES = ("SEC EDGAR", "36Kr", "TechCrunch", "Polymarket", "CoinGecko", "GDELT")
TECHNICAL_SOURCES = ("GitHub", "arXiv", "HackerNews")


@dataclass
class OpportunityScorecard:
    score: int
    level: str
    dimensions: dict[str, Any]
    risk_level: str
    validation_score: int
    risk_factors: list[str]
    evidence: list[str]
    rationale: list[str]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _has_source(sources: list[str], prefixes: tuple[str, ...]) -> bool:
    return any(any(source.startswith(prefix) for prefix in prefixes) for source in sources)


def _level(score: int) -> str:
    return "S" if score >= 88 else "A" if score >= 76 else "B" if score >= 65 else "C"


class OpportunityScoringAgent:
    name = "OpportunityScoringAgent"

    def score(
        self,
        *,
        source: str,
        topic: str,
        circle: str,
        base_score: int,
        crowding_score: int,
        metrics: dict[str, Any] | None,
        sources: list[str] | None = None,
    ) -> OpportunityScorecard:
        source_list = list(dict.fromkeys(sources or [source]))
        metrics = metrics or {}
        evidence_count = max(len(source_list), int(metrics.get("evidence_count", 1) or 1))
        text = " ".join([source, topic, circle]).lower()

        demand = 0.38 + base_score / 250
        if _has_source(source_list, DEMAND_SOURCES):
            demand += 0.18
        if "需求" in topic or "搜索" in topic or "痛点" in topic or "商品" in topic:
            demand += 0.10

        supply = 0.35
        if _has_source(source_list, SUPPLY_SOURCES):
            supply += 0.25
        if _has_source(source_list, TECHNICAL_SOURCES):
            supply += 0.12
        if "开源" in topic or "供给" in topic:
            supply += 0.12

        momentum = 0.32 + base_score / 220
        if _has_source(source_list, MOMENTUM_SOURCES):
            momentum += 0.14
        if evidence_count > 1:
            momentum += min(0.18, (evidence_count - 1) * 0.06)

        competition = 0.30
        if _has_source(source_list, COMPETITION_SOURCES):
            competition += 0.22
        competition += min(0.18, crowding_score / 200)

        execution = 0.62
        if "研究" in topic or "ipo" in text or "机构持仓" in topic:
            execution -= 0.18
        if "开源" in topic or "独立站" in topic or "Amazon" in topic:
            execution += 0.10
        if "投资" in circle:
            execution -= 0.08

        risk = 0.22 + crowding_score / 250
        if competition > 0.62:
            risk += 0.08
        if _has_source(source_list, INVESTMENT_SOURCES):
            risk += 0.05
        if source.startswith("Amazon") or source.startswith("Reddit"):
            risk += 0.05
        if evidence_count > 1:
            risk -= min(0.10, (evidence_count - 1) * 0.03)

        demand = _clamp(demand)
        supply = _clamp(supply)
        momentum = _clamp(momentum)
        competition = _clamp(competition)
        execution = _clamp(execution)
        risk = _clamp(risk)
        competition_adjusted = 1 - competition * 0.55
        risk_adjusted = 1 - risk

        composite = (
            demand * 0.25
            + momentum * 0.20
            + supply * 0.15
            + execution * 0.20
            + competition_adjusted * 0.10
            + risk_adjusted * 0.10
        )
        score = int(round(_clamp(composite) * 100))
        score = max(50, min(96, int(score * 0.55 + base_score * 0.45)))
        if evidence_count > 1:
            score = min(96, score + min(5, (evidence_count - 1) * 2))
        if demand >= 0.82 and momentum >= 0.78:
            score = min(96, score + 3)
        validation_score = max(45, min(96, score + int((evidence_count - 1) * 3) - int(risk * 10)))
        risk_level = "high" if risk >= 0.62 else "medium" if risk >= 0.42 else "low"

        rationale = []
        if demand >= 0.70:
            rationale.append("需求侧信号较强")
        if momentum >= 0.70:
            rationale.append("短期动量较高")
        if supply >= 0.65:
            rationale.append("供给或复用路径较清晰")
        if evidence_count > 1:
            rationale.append(f"{evidence_count} 个来源形成交叉验证")
        if not rationale:
            rationale.append("单源早期信号，适合小成本验证")

        risk_factors = []
        if competition >= 0.60:
            risk_factors.append("同类产品或内容竞争可能较快升温")
        if risk_level != "low":
            risk_factors.append("公开信号可能存在短期噪声或平台依赖")
        if execution < 0.52:
            risk_factors.append("执行路径需要更多行业研究或技术验证")
        if not risk_factors:
            risk_factors.append("需要继续验证真实付费意愿")

        dimensions = {
            "demand": round(demand, 2),
            "momentum": round(momentum, 2),
            "supply": round(supply, 2),
            "competition": round(competition, 2),
            "competition_adjusted": round(competition_adjusted, 2),
            "execution": round(execution, 2),
            "risk": round(risk, 2),
            "risk_adjusted": round(risk_adjusted, 2),
            "crowding": round(crowding_score / 100, 2),
            "base_score": base_score,
            "evidence_count": evidence_count,
            "sources": source_list,
            "rationale": rationale,
            "agent": self.name,
        }
        evidence = [f"{src} 提供信号" for src in source_list[:6]]
        return OpportunityScorecard(
            score=score,
            level=_level(score),
            dimensions=dimensions,
            risk_level=risk_level,
            validation_score=validation_score,
            risk_factors=risk_factors,
            evidence=evidence,
            rationale=rationale,
        )
