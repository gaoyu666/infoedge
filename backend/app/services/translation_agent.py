from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.services.sources import SourceRecord


_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#/-]*")

PHRASE_GLOSSARY: tuple[tuple[str, str], ...] = (
    ("artificial intelligence", "人工智能"),
    ("machine learning", "机器学习"),
    ("large language model", "大语言模型"),
    ("language model", "语言模型"),
    ("open source", "开源"),
    ("developer tool", "开发者工具"),
    ("coding agent", "编程智能体"),
    ("ai agent", "AI 智能体"),
    ("workflow automation", "工作流自动化"),
    ("store owners", "店主"),
    ("marketing teams", "营销团队"),
    ("ecommerce sellers", "电商卖家"),
    ("shopify store owners", "Shopify 店主"),
    ("automation", "自动化"),
    ("ecommerce", "电商"),
    ("e-commerce", "电商"),
    ("shopify", "Shopify"),
    ("amazon", "Amazon"),
    ("google play", "Google Play"),
    ("app store", "应用商店"),
    ("product hunt", "Product Hunt"),
    ("startup", "创业公司"),
    ("funding", "融资"),
    ("venture capital", "风险投资"),
    ("marketing", "营销"),
    ("ads", "广告"),
    ("advertising", "广告"),
    ("creator", "创作者"),
    ("security", "安全"),
    ("privacy", "隐私"),
    ("pricing", "定价"),
    ("analytics", "数据分析"),
    ("dashboard", "看板"),
    ("search", "搜索"),
    ("trend", "趋势"),
    ("review", "评论"),
    ("reviews", "评论"),
    ("ranking", "榜单"),
    ("rankings", "榜单"),
    ("template", "模板"),
    ("templates", "模板"),
    ("plugin", "插件"),
    ("plugins", "插件"),
    ("api", "API"),
    ("saas", "SaaS"),
)

WORD_GLOSSARY: dict[str, str] = {
    "agent": "智能体",
    "agents": "智能体",
    "ai": "AI",
    "app": "应用",
    "apps": "应用",
    "tool": "工具",
    "tools": "工具",
    "builder": "构建器",
    "platform": "平台",
    "marketplace": "市场",
    "store": "店铺",
    "stores": "店铺",
    "seller": "卖家",
    "sellers": "卖家",
    "owner": "店主",
    "owners": "店主",
    "team": "团队",
    "teams": "团队",
    "customer": "客户",
    "customers": "客户",
    "user": "用户",
    "users": "用户",
    "growth": "增长",
    "launch": "发布",
    "product": "产品",
    "products": "产品",
    "data": "数据",
    "insight": "洞察",
    "insights": "洞察",
    "monitor": "监控",
    "tracking": "跟踪",
    "research": "研究",
    "paper": "论文",
    "papers": "论文",
    "repo": "代码仓库",
    "repository": "代码仓库",
    "github": "GitHub",
    "reddit": "Reddit",
    "hackernews": "Hacker News",
    "hn": "Hacker News",
    "arxiv": "arXiv",
    "tiktok": "TikTok",
    "video": "视频",
    "content": "内容",
    "newsletter": "简报",
    "email": "邮件",
    "finance": "金融",
    "investment": "投资",
    "ipo": "IPO",
    "fund": "基金",
    "design": "设计",
    "image": "图片",
    "audio": "音频",
    "voice": "语音",
    "chat": "聊天",
    "sales": "销售",
    "lead": "线索",
    "leads": "线索",
    "automation": "自动化",
}


@dataclass(frozen=True)
class LocalizedRecord:
    title: str
    content: str
    language: str
    translated: bool
    provider: str
    confidence: float


def _detect_language(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "unknown"
    cjk = len(_CJK_RE.findall(stripped))
    letters = len(re.findall(r"[A-Za-z]", stripped))
    if cjk >= 2 and cjk >= letters * 0.15:
        return "zh"
    if letters >= 4:
        return "en"
    return "unknown"


def _looks_like_name(token: str) -> bool:
    return token.isupper() or any(char.isdigit() for char in token) or token[:1].isupper()


def _localize_fragment(text: str) -> str:
    if not text:
        return ""
    result = " ".join(text.split())
    lowered = result.lower()
    replacements: list[tuple[int, int, str]] = []
    for phrase, zh in PHRASE_GLOSSARY:
        start = lowered.find(phrase)
        if start >= 0:
            replacements.append((start, start + len(phrase), zh))
    if replacements:
        replacements.sort(key=lambda item: item[0])
        merged: list[tuple[int, int, str]] = []
        cursor = -1
        for item in replacements:
            if item[0] >= cursor:
                merged.append(item)
                cursor = item[1]
        chunks: list[str] = []
        cursor = 0
        for start, end, zh in merged:
            chunks.append(result[cursor:start])
            chunks.append(zh)
            cursor = end
        chunks.append(result[cursor:])
        result = "".join(chunks)

    def repl(match: re.Match[str]) -> str:
        token = match.group(0)
        key = token.lower().strip("-/")
        if key in WORD_GLOSSARY:
            return WORD_GLOSSARY[key]
        if _looks_like_name(token):
            return token
        return token

    result = _WORD_RE.sub(repl, result)
    result = re.sub(r"\bfor\b", "面向", result, flags=re.IGNORECASE)
    result = re.sub(r"\band\b", "和", result, flags=re.IGNORECASE)
    result = re.sub(r"\b(a|an|the)\b", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\s+", " ", result).strip()
    result = result.replace(" 面向 ", "面向").replace(" 和 ", "和")
    result = result.replace(" - ", "：").replace(": ", "：")
    return result


class ChineseLocalizationAgent:
    name = "ChineseLocalizationAgent"

    def localize(self, record: SourceRecord) -> LocalizedRecord:
        text = f"{record.title}\n{record.content}"
        language = _detect_language(text)
        if language == "zh":
            return LocalizedRecord(
                title=record.title,
                content=record.content,
                language=language,
                translated=False,
                provider="native",
                confidence=0.98,
            )

        title = _localize_fragment(record.title)
        content = _localize_fragment(record.content)
        title = self._business_title(record.source, title)
        return LocalizedRecord(
            title=title or record.title,
            content=content or record.content,
            language=language,
            translated=language != "zh",
            provider="local_glossary_free",
            confidence=0.62 if language == "en" else 0.45,
        )

    def _business_title(self, source: str, title: str) -> str:
        if not title:
            return title
        prefix = ""
        if source.startswith("GitHub"):
            prefix = "开源项目："
        elif source.startswith("Product Hunt"):
            prefix = "新品发布："
        elif source.startswith("Google Trends"):
            prefix = "搜索趋势："
        elif source.startswith("Reddit"):
            prefix = "社区讨论："
        elif source.startswith("arXiv"):
            prefix = "论文方向："
        elif source.startswith("TechCrunch"):
            prefix = "科技新闻："
        elif source.startswith("Amazon"):
            prefix = "Amazon 商品："
        elif source.startswith("Apple App Store") or source.startswith("Google Play"):
            prefix = "应用榜单："
        if prefix and not title.startswith(prefix):
            return f"{prefix}{title}"
        return title

    def metadata(self, record: SourceRecord, localized: LocalizedRecord) -> dict[str, Any]:
        return {
            "language": localized.language,
            "translated_to": "zh",
            "translation_provider": localized.provider,
            "translation_agent": self.name,
            "translation_confidence": localized.confidence,
            "translated": localized.translated,
            "title_original": record.title,
            "content_original": record.content,
            "title_zh": localized.title,
            "content_zh": localized.content,
        }
