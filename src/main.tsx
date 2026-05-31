import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Archive,
  ArrowLeft,
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  Check,
  CircleDollarSign,
  Database,
  Download,
  ExternalLink,
  Filter,
  Flame,
  Gauge,
  ListChecks,
  MessageSquareText,
  LineChart,
  Plus,
  Radar,
  RefreshCw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Target,
  TrendingUp,
  Zap
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar as RadarShape,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import "./styles.css";

const API_CANDIDATE_BASES = (() => {
  const env = (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL?.replace(/\/+$/, "");
  const hostname = window.location.hostname;
  const isLocal = hostname === "localhost" || hostname === "127.0.0.1";
  const list = [
    env,
    isLocal ? "http://127.0.0.1:8000" : null,
    isLocal ? "http://127.0.0.1:8002" : null,
    isLocal ? "http://localhost:8000" : null,
    isLocal ? "http://localhost:8002" : null
  ];
  return [...new Set(list.filter((item): item is string => Boolean(item)))];
})();

let ACTIVE_API_BASE: string | null = null;

type ApiEnvelope<T> = {
  success?: boolean;
  data: T;
  error?: string;
};

type ListResponse<T> = {
  items: T[];
  total: number;
  total_all?: number;
};

type Signal = {
  id: string;
  level: string;
  score: number;
  title: string;
  type: string;
  gap: string;
  window: string;
  circle: string;
  region: string;
  crowding: string;
  risk: string;
  difficulty: string;
  sources: string[];
  time: string;
  roi: string;
  convergence?: string | null;
  created_at?: string;
};

type OpportunityDimensions = {
  demand?: number;
  momentum?: number;
  supply?: number;
  competition?: number;
  competition_adjusted?: number;
  execution?: number;
  risk?: number;
  risk_adjusted?: number;
  crowding?: number;
  base_score?: number;
  evidence_count?: number;
  sources?: string[];
  rationale?: string[];
  agent?: string;
  merged_by?: string;
  [key: string]: unknown;
};

type ActionPlanStep = {
  index?: number;
  label?: string;
  deliverable?: string;
  success_metric?: string;
};

type ActionSummary = {
  opportunity?: string;
  info_gap?: string;
  what_to_sell?: string;
  who_pays?: string;
  why_now?: string;
  first_step?: string;
  validation_plan?: string[];
  no_go_signals?: string[];
  budget?: string;
  estimated_return?: string;
  roi?: string;
  breakeven?: string;
  max_loss?: string;
  decision_label?: string;
  execution_stage?: string;
  execution_gate_passed?: boolean;
  blockers?: string[];
  reasons?: string[];
  risk_level?: string;
  success_metric?: string;
  fail_metric?: string;
  action_plan?: ActionPlanStep[];
};

type DetailVerdict = {
  analysis_version?: string;
  label?: "可执行" | "需验证" | "仅观察" | "应放弃" | string;
  headline?: string;
  summary?: string;
  detail_story?: {
    what_it_is?: string;
    why_it_matters?: string;
    opportunity_angle?: string;
    current_limit?: string;
  };
  key_question?: string;
  why?: string[];
  next_steps?: string[];
  missing_evidence?: string[];
  do_not_do?: string;
  evidence_facts?: Array<{ label?: string; value?: string }>;
};

type Opportunity = {
  id: string;
  signal_id: string;
  title?: string;
  business_title?: string;
  evidence_title?: string;
  title_original?: string;
  source?: string;
  score: number;
  level: string;
  dimensions: OpportunityDimensions | null;
  playbook: string;
  playbook_name: string;
  window_hours: number;
  strategies: string[] | null;
  crowding_score: number;
  risk_level: string;
  risk_factors?: string[] | null;
  bear_case?: string | null;
  validation_score: number;
  difficulty: string;
  estimated_investment: string;
  estimated_return: string;
  roi_ratio: string;
  breakeven: string;
  max_loss: string;
  execution_status: string;
  current_step?: number | null;
  actual_result?: string | null;
  user_feedback?: string | null;
  status: string;
  created_at: string;
  opportunity_stage?: "executable" | "needs_validation" | "watch" | string;
  execution_gate_passed?: boolean;
  execution_blockers?: string[];
  execution_reasons?: string[];
  evidence_freshness?: "fresh" | "stale" | "expired" | "unknown" | "not_configured" | string;
  evidence_last_checked?: string | null;
  evidence_age_hours?: number | null;
  evidence_sources?: string[];
  evidence_count_effective?: number;
  data_type?: "live" | "demo" | string;
  evidence_published_at?: string | null;
  content_age_hours?: number | null;
  content_recency?: "fresh" | "recent" | "stale" | "expired" | "unknown" | string;
  action_summary?: ActionSummary | null;
  detail_verdict?: DetailVerdict | null;
};

type ActionItem = {
  id: string;
  opportunity_id: string;
  opportunity_title?: string;
  playbook: string;
  action_summary?: ActionSummary | null;
  current_step_label?: string;
  next_step_label?: string;
  success_metric?: string;
  total_steps: number;
  current_step: number;
  status: string;
  signal_heat_at_start: number;
  signal_heat_current: number;
  heat_change_pct: number;
  result: string;
  invested_amount?: number;
  return_amount?: number;
  rating?: number | null;
  review_notes?: string | null;
  started_at?: string;
  completed_at?: string;
};

type Brief = {
  id: string;
  date_key: string;
  title: string;
  summary: string;
  payload?: BriefPayload;
  created_at: string;
};

type BriefOpportunity = {
  rank: number;
  id: string;
  signal_id?: string;
  title: string;
  source: string;
  sources?: string[];
  playbook_name: string;
  score: number;
  level: string;
  risk_level: string;
  crowding_score: number;
  validation_score: number;
  window_hours: number;
  estimated_investment: string;
  estimated_return?: string;
  roi_ratio?: string;
  decision: string;
  suggested_action: string;
  validation_where?: string;
  hot_reasons?: string[];
  action_summary?: ActionSummary | null;
};

type BriefSource = {
  id: string;
  source: string;
  status: string;
  freshness: string;
  signal_count_24h?: number;
  last_checked?: string;
  notes?: string;
};

type BriefSignalCategory = {
  category: string;
  count: number;
  items: Array<{
    id: string;
    title: string;
    source: string;
    sources?: string[];
    score: number;
    level: string;
    reason?: string;
  }>;
};

type BriefTodo = {
  title: string;
  opportunity_id?: string | null;
  where: string;
  budget: string;
  success_metric: string;
  fail_metric: string;
};

type BriefPayload = {
  generated_by?: string;
  metrics?: Record<string, number>;
  today_conclusion?: {
    headline?: string;
    recommended_action?: string;
    bullets?: string[];
  };
  top_opportunities?: BriefOpportunity[];
  source_status?: {
    success?: BriefSource[];
    failed?: BriefSource[];
    no_new?: BriefSource[];
    needs_config?: BriefSource[];
  };
  signal_categories?: BriefSignalCategory[];
  market_events?: Array<Record<string, unknown>>;
  todo?: BriefTodo[];
  risks?: string[];
  changes?: Record<string, unknown>;
  process_steps?: string[];
  signals?: string[];
  opportunities?: string[];
};

type SourceItem = {
  id: string;
  source: string;
  status: "normal" | "warning" | "offline" | string;
  freshness: "fresh" | "aging" | "stale" | "offline" | string;
  config_status?: string;
  collection_status?: string;
  freshness_status?: string;
  yield_status?: string;
  operational_state?: string;
  is_ready?: boolean;
  last_checked?: string;
  signal_count_24h?: number;
  notes?: string;
  category?: string;
  source_type?: string;
  age_hours?: number | null;
  freshness_reason?: string | null;
  is_static?: boolean;
};

type ScenarioPreset = {
  id: string;
  name: string;
  scenario: string;
  description: string;
};

type ScenarioHistory = {
  id: string;
  preset_id: string | null;
  scenario: string;
  result: string;
  confidence: number;
  created_at: string;
};

type OpportunityExtra = {
  risk_factors?: string[];
  bear_case?: string;
  crowding_score?: number;
  risk_level?: string;
  validation_score?: number;
  validation?: {
    bull_case?: string;
    bear_case?: string;
    difficulty?: string;
  };
  capital_factor?: number;
  estimated_investment?: string;
  estimated_return?: string;
  roi_ratio?: string;
  breakeven?: string;
  max_loss?: string;
  oci_score?: number;
  oci_breakdown?: Record<string, number>;
  composite_score?: number;
  recommendation?: string;
};

type EvidenceStep = {
  agent: string;
  action: string;
  output: string;
  status: string;
};

type SourceRecord = {
  record_type?: string;
  source?: string;
  url?: string | null;
  platform_id?: string | number | null;
  author?: string | number | null;
  published_at?: string | null;
  fetched_at?: string | null;
  title?: string;
  title_original?: string;
  content_excerpt?: string;
  content_original_excerpt?: string;
  key_metrics?: Record<string, unknown>;
  signal_fact?: string;
  business_model?: string;
  system_interpretation?: string;
};

type DeepAnalysisItem = {
  [key: string]: unknown;
};

type DeepOpportunityAnalysis = {
  analysis_version?: string;
  generated_by?: string;
  generated_at?: string;
  headline?: string;
  opportunity_definition?: {
    what_it_is?: string;
    what_to_sell?: string;
    who_pays?: string;
    why_they_pay?: string;
    not_the_opportunity?: string;
  };
  source_digest?: {
    record_type?: string;
    source?: string;
    title?: string;
    content_excerpt?: string;
    url?: string | null;
    key_metrics?: Record<string, unknown>;
    signal_fact?: string;
  };
  scorecard?: Record<string, number>;
  why_now?: string[];
  customer_segments?: DeepAnalysisItem[];
  offer_map?: DeepAnalysisItem[];
  validation_plan?: DeepAnalysisItem[];
  go_to_market?: string[];
  risk_review?: DeepAnalysisItem[];
  data_gaps?: string[];
  decision?: {
    recommendation?: string;
    confidence?: string;
    reason?: string;
    next_action?: string;
  };
};

type OpportunityEvidence = {
  source: string;
  sources: string[];
  url?: string | null;
  published_at?: string | null;
  fetched_at?: string | null;
  title_zh?: string;
  title_original?: string;
  content_zh?: string;
  content_original?: string;
  source_record?: SourceRecord;
  specific_content?: {
    record_type?: string;
    title?: string;
    content?: string;
    original_content?: string;
    url?: string | null;
    metrics?: Record<string, unknown>;
  };
  topic?: string;
  circle?: string;
  region?: string;
  metrics?: Record<string, unknown>;
  hot_reasons?: string[];
  pipeline_steps?: EvidenceStep[];
  analysis_summary?: {
    platform_signal?: string;
    source_fact?: string;
    business_model?: string;
    system_interpretation?: string;
    business_interpretation?: string;
    why_now?: string;
  };
  merchant_analysis?: {
    analysis_version?: string;
    plain_type?: string;
    agent_config?: {
      name?: string;
      role?: string;
      inputs?: string[];
      output_contract?: string[];
      guardrails?: string[];
    };
    execution_brief?: {
      sell?: string;
      buyer?: string;
      deliverable?: string;
      price_test?: string;
      first_channel?: string;
      first_message?: string;
      data_to_track?: string[];
      success_threshold?: string;
      stop_threshold?: string;
    };
    customer_scenarios?: Array<{
      segment?: string;
      pain?: string;
      use_case?: string;
      where_to_find?: string;
    }>;
    offer_packages?: Array<{
      name?: string;
      price?: string;
      deliverable?: string;
      buy_trigger?: string;
    }>;
    next_actions?: Array<{
      step?: string;
      output?: string;
      done_when?: string;
    }>;
    opportunity_summary?: string;
    what_to_sell?: string;
    who_pays?: string;
    why_they_pay?: string;
    first_test?: string;
    not_the_opportunity?: string;
    decision_question?: string;
    what_it_is?: string;
    source_context?: string;
    why_opportunity?: string;
    why_now?: string[];
    who_needs_it?: string[];
    business_angles?: string[];
    validation_plan?: string[];
    no_go_signals?: string[];
    merchant_take?: string;
    score_explanation?: Record<string, unknown>;
  };
};

type OpportunityDetail = {
  opportunity: Opportunity;
  signal: Signal | null;
  evidence?: OpportunityEvidence | null;
  analysis?: {
    analysis?: {
      deep_analysis?: DeepOpportunityAnalysis;
      [key: string]: unknown;
    } | null;
    [key: string]: unknown;
  } | null;
  deep_analysis?: DeepOpportunityAnalysis | null;
  risk?: OpportunityExtra | null;
  validation?: OpportunityExtra | null;
  roi?: OpportunityExtra | null;
  oci?: OpportunityExtra | null;
};

type DashboardStats = {
  win_rate: number;
  signals_24h: number;
  high_level_signals: number;
  active_sources: number;
  source_health: string;
  data_volume: number;
};

type CircleStat = {
  circle: string;
  count: number;
  avg_score: number;
};

type RegionStat = {
  region: string;
  count: number;
  avg_score: number;
};

type SourceDetail = SourceItem & {
  // Keep explicit for endpoint detail shape compatibility
  signal_count_24h?: number;
};

const SOURCE_CATALOG: SourceItem[] = [
  { id: "catalog-github", source: "GitHub", category: "技术趋势", source_type: "public_api", status: "pending", freshness: "unknown", notes: "开源项目、开发者趋势和可产品化技术供给。" },
  { id: "catalog-github-agents", source: "GitHub: Agents", category: "AI/Agent", source_type: "public_api", status: "pending", freshness: "unknown", notes: "Agent、自动化和 AI 工具方向的开源项目。" },
  { id: "catalog-github-creator", source: "GitHub: Creator Tools", category: "创作者工具", source_type: "public_api", status: "pending", freshness: "unknown", notes: "内容生产、设计、视频和创作者工具。" },
  { id: "catalog-github-ecommerce", source: "GitHub: Ecommerce", category: "电商技术", source_type: "public_api", status: "pending", freshness: "unknown", notes: "电商、Shopify、营销自动化相关开源项目。" },
  { id: "catalog-reddit", source: "Reddit", category: "社区需求", source_type: "public_json", status: "pending", freshness: "unknown", notes: "社区讨论中的痛点、抱怨和早期需求。" },
  { id: "catalog-reddit-entrepreneur", source: "Reddit: r/Entrepreneur", category: "创业社区", source_type: "public_json", status: "pending", freshness: "unknown", notes: "创业者需求、商业模式讨论和增长问题。" },
  { id: "catalog-reddit-saas", source: "Reddit: r/SaaS", category: "SaaS", source_type: "public_json", status: "pending", freshness: "unknown", notes: "SaaS 产品、获客、定价和留存问题。" },
  { id: "catalog-reddit-sideproject", source: "Reddit: r/SideProject", category: "独立产品", source_type: "public_json", status: "pending", freshness: "unknown", notes: "独立开发、MVP 和小产品验证。" },
  { id: "catalog-reddit-ecommerce", source: "Reddit: r/ecommerce", category: "电商社区", source_type: "public_json", status: "pending", freshness: "unknown", notes: "电商运营、选品、履约和转化痛点。" },
  { id: "catalog-reddit-shopify", source: "Reddit: r/shopify", category: "Shopify", source_type: "public_json", status: "pending", freshness: "unknown", notes: "Shopify 店铺运营和应用需求。" },
  { id: "catalog-hn", source: "HackerNews", category: "技术社区", source_type: "public_api", status: "pending", freshness: "unknown", notes: "开发者和创业者讨论中的早期技术信号。" },
  { id: "catalog-hn-startup", source: "HackerNews: Startup", category: "创业技术", source_type: "public_api", status: "pending", freshness: "unknown", notes: "创业、自动化、电商和工具类讨论。" },
  { id: "catalog-arxiv", source: "arXiv", category: "研究论文", source_type: "public_atom", status: "pending", freshness: "unknown", notes: "AI/技术论文到应用机会。" },
  { id: "catalog-google-trends-us", source: "Google Trends: US", category: "搜索需求", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "美国上升搜索词和短期需求变化。" },
  { id: "catalog-product-hunt-feed", source: "Product Hunt: Feed", category: "新品发布", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "新品、投票和早期产品定位。" },
  { id: "catalog-product-hunt-api", source: "Product Hunt API", category: "新品深度数据", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "官方 GraphQL API 需要 token，用于补评论、投票和分类趋势。" },
  { id: "catalog-techcrunch-ai", source: "TechCrunch: AI", category: "科技新闻", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "AI 公司、融资和产品发布信号。" },
  { id: "catalog-techcrunch-startups", source: "TechCrunch: Startups", category: "创业新闻", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "创业公司、新品和融资动态。" },
  { id: "catalog-techradar-techcrunch", source: "TechRadar: TechCrunch", category: "科技媒体", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "Global-Tech-Rader 的 TechCrunch 通用科技 feed。" },
  { id: "catalog-techradar-mit-tr", source: "TechRadar: MIT Technology Review", category: "科技媒体", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "MIT Technology Review 科技趋势和产业分析。" },
  { id: "catalog-techradar-the-verge", source: "TechRadar: The Verge", category: "科技媒体", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "消费科技、平台和硬件生态动态。" },
  { id: "catalog-techradar-wired", source: "TechRadar: Wired", category: "科技媒体", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "Wired 科技、商业和社会影响报道。" },
  { id: "catalog-techradar-openai-blog", source: "TechRadar: OpenAI Blog", category: "AI/Agent", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "OpenAI 官方博客和产品/研究发布。" },
  { id: "catalog-techradar-deepmind", source: "TechRadar: Google DeepMind", category: "AI/Agent", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "Google DeepMind 研究和产品动态。" },
  { id: "catalog-techradar-google-ai", source: "TechRadar: Google AI Blog", category: "AI/Agent", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "Google AI 官方技术和产品动态。" },
  { id: "catalog-techradar-arxiv-ai", source: "TechRadar: arXiv CS AI RSS", category: "研究论文", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "arXiv CS.AI RSS，用于补充论文趋势。" },
  { id: "catalog-techradar-mit-ai", source: "TechRadar: MIT News AI", category: "AI/Agent", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "MIT News 人工智能专题。" },
  { id: "catalog-techradar-github-blog", source: "TechRadar: GitHub Blog", category: "开发者生态", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "GitHub 官方产品、开源和开发者生态动态。" },
  { id: "catalog-techradar-hn-rss", source: "TechRadar: Hacker News RSS", category: "技术社区", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "Hacker News RSS 热门讨论补充源。" },
  { id: "catalog-techradar-qbitai", source: "TechRadar: QbitAI", category: "中文科技", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "量子位中文 AI/科技新闻。" },
  { id: "catalog-techradar-jiqizhixin", source: "TechRadar: Jiqizhixin", category: "中文科技", source_type: "public_rss", status: "needs_config", freshness: "not_configured", notes: "当前公开 URL 返回 HTML 数据服务页，需配置有效 RSS/relay 后采集。" },
  { id: "catalog-techradar-solidot", source: "TechRadar: Solidot", category: "中文科技", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "Solidot 开源、科技和互联网新闻。" },
  { id: "catalog-techradar-oschina", source: "TechRadar: OSChina", category: "中文科技", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "OSChina 开源和开发者生态新闻。" },
  { id: "catalog-techradar-ifanr", source: "TechRadar: ifanr", category: "消费科技", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "爱范儿消费科技与产品趋势。" },
  { id: "catalog-techradar-sspai", source: "TechRadar: SSPAI", category: "效率工具", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "少数派效率工具、数字生活和产品趋势。" },
  { id: "catalog-techradar-huxiu", source: "TechRadar: Huxiu", category: "中文商业", source_type: "public_rss", status: "needs_config", freshness: "not_configured", notes: "当前公开 RSS 在服务器环境超时，需代理或 relay 后采集。" },
  { id: "catalog-techradar-ithome", source: "TechRadar: ITHome", category: "消费科技", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "IT之家科技和硬件资讯。" },
  { id: "catalog-techradar-aws", source: "TechRadar: AWS Blog", category: "云计算", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "AWS 官方云产品和基础设施动态。" },
  { id: "catalog-techradar-google-cloud", source: "TechRadar: Google Cloud", category: "云计算", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "Google Cloud 官方云产品动态。" },
  { id: "catalog-techradar-reuters-business", source: "TechRadar: Reuters Business", category: "商业新闻", source_type: "public_rss", status: "needs_config", freshness: "not_configured", notes: "Reuters 公开 RSS 当前返回 401，需授权 API 或可用 feed relay。" },
  { id: "catalog-techradar-canary", source: "TechRadar: Canary Media", category: "能源气候", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "清洁能源和气候科技趋势。" },
  { id: "catalog-techradar-electrek", source: "TechRadar: Electrek", category: "新能源车", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "EV、电池和新能源硬件动态。" },
  { id: "catalog-techradar-krebs", source: "TechRadar: KrebsOnSecurity", category: "网络安全", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "网络安全事件和风险趋势。" },
  { id: "catalog-techradar-stat", source: "TechRadar: STAT News", category: "医疗科技", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "医疗、生物科技和健康产业动态。" },
  { id: "catalog-36kr-news", source: "36Kr: News", category: "中文商业新闻", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "中文新经济、创投和产业趋势。" },
  { id: "catalog-36kr-newsflash", source: "36Kr: Newsflash", category: "中文快讯", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "中文创投、融资、IPO 和产业快讯。" },
  { id: "catalog-sec-formd", source: "SEC EDGAR: Form D", category: "融资披露", source_type: "public_atom", status: "pending", freshness: "unknown", notes: "美国私募融资和 Reg D 披露。" },
  { id: "catalog-sec-13f", source: "SEC EDGAR: 13F", category: "机构持仓", source_type: "public_atom", status: "pending", freshness: "unknown", notes: "机构持仓变化和行业资金流。" },
  { id: "catalog-sec-s1", source: "SEC EDGAR: S-1 IPO", category: "IPO 管线", source_type: "public_atom", status: "pending", freshness: "unknown", notes: "拟上市公司、招股书和产业链机会。" },
  { id: "catalog-apple-app-store", source: "Apple App Store", category: "应用榜单", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "美国应用榜单趋势。" },
  { id: "catalog-google-play-search", source: "Google Play: App Search", category: "安卓应用", source_type: "scraper_library", status: "pending", freshness: "unknown", notes: "按关键词采集 Google Play 应用趋势。" },
  { id: "catalog-google-play", source: "Google Play", category: "安卓深度数据", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "非官方抓取链路，需要监控可用性。" },
  { id: "catalog-trendradar-toutiao", source: "TrendRadar: Toutiao Hot", category: "中文热榜", source_type: "public_json", status: "needs_config", freshness: "not_configured", notes: "NewsNow 今日头条热榜；默认公共端点在服务器环境被 Cloudflare 拦截，需配置 NEWSNOW_API_BASE。" },
  { id: "catalog-trendradar-baidu", source: "TrendRadar: Baidu Hot Search", category: "中文热榜", source_type: "public_json", status: "needs_config", freshness: "not_configured", notes: "NewsNow 百度热搜；需配置可访问的 NEWSNOW_API_BASE。" },
  { id: "catalog-trendradar-wallstreetcn", source: "TrendRadar: Wallstreetcn Hot", category: "财经热榜", source_type: "public_json", status: "needs_config", freshness: "not_configured", notes: "NewsNow 华尔街见闻热门；需配置可访问的 NEWSNOW_API_BASE。" },
  { id: "catalog-trendradar-thepaper", source: "TrendRadar: The Paper", category: "中文热榜", source_type: "public_json", status: "needs_config", freshness: "not_configured", notes: "NewsNow 澎湃新闻热榜；需配置可访问的 NEWSNOW_API_BASE。" },
  { id: "catalog-trendradar-bilibili", source: "TrendRadar: Bilibili Hot Search", category: "内容热榜", source_type: "public_json", status: "needs_config", freshness: "not_configured", notes: "NewsNow Bilibili 热搜；需配置可访问的 NEWSNOW_API_BASE。" },
  { id: "catalog-trendradar-cls", source: "TrendRadar: CLS Hot", category: "财经热榜", source_type: "public_json", status: "needs_config", freshness: "not_configured", notes: "NewsNow 财联社热榜；需配置可访问的 NEWSNOW_API_BASE。" },
  { id: "catalog-trendradar-ifeng", source: "TrendRadar: Ifeng Hot", category: "中文热榜", source_type: "public_json", status: "needs_config", freshness: "not_configured", notes: "NewsNow 凤凰新闻热榜；需配置可访问的 NEWSNOW_API_BASE。" },
  { id: "catalog-trendradar-tieba", source: "TrendRadar: Tieba Hot", category: "社区热榜", source_type: "public_json", status: "needs_config", freshness: "not_configured", notes: "NewsNow 贴吧热榜；需配置可访问的 NEWSNOW_API_BASE。" },
  { id: "catalog-trendradar-weibo", source: "TrendRadar: Weibo Hot", category: "中文社媒", source_type: "public_json", status: "needs_config", freshness: "not_configured", notes: "NewsNow 微博热搜；需配置可访问的 NEWSNOW_API_BASE。" },
  { id: "catalog-trendradar-douyin", source: "TrendRadar: Douyin Hot", category: "短视频热榜", source_type: "public_json", status: "needs_config", freshness: "not_configured", notes: "NewsNow 抖音热榜；需配置可访问的 NEWSNOW_API_BASE。" },
  { id: "catalog-trendradar-zhihu", source: "TrendRadar: Zhihu Hot", category: "社区热榜", source_type: "public_json", status: "needs_config", freshness: "not_configured", notes: "NewsNow 知乎热榜；需配置可访问的 NEWSNOW_API_BASE。" },
  { id: "catalog-trendradar-yahoo-finance", source: "TrendRadar: Yahoo Finance RSS", category: "财经新闻", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "Yahoo Finance RSS 财经新闻。" },
  { id: "catalog-amazon-light", source: "Amazon: Light Search", category: "电商需求", source_type: "crawler", status: "pending", freshness: "unknown", notes: "轻量采集 Amazon 搜索结果，稳定性受反爬影响。" },
  { id: "catalog-amazon-market", source: "Amazon Market Data", category: "电商深度数据", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "建议走 Keepa/Rainforest/SerpApi 等服务。" },
  { id: "catalog-amazon-sp-api", source: "Amazon SP-API", category: "卖家数据", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "需要卖家/开发者授权。" },
  { id: "catalog-shopify-public", source: "Shopify: Public Catalog", category: "独立站供给", source_type: "public_json", status: "pending", freshness: "unknown", notes: "公开 /products.json 商品目录。" },
  { id: "catalog-shopify-admin", source: "Shopify Admin/Storefront", category: "独立站深度数据", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "需要店铺授权或目标店铺清单。" },
  { id: "catalog-tiktok", source: "TikTok Shop/Creative Center", category: "短视频电商", source_type: "official_or_vendor", status: "needs_config", freshness: "not_configured", notes: "官方接口需要申请，大规模采集更适合第三方服务。" },
  { id: "catalog-meta-ads", source: "Meta Ads Library", category: "广告投放", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "官方接口需要 Meta 开发者访问。" },
  { id: "catalog-etsy-api", source: "Etsy Open API", category: "手工设计电商", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "需要开发者 API key。" },
  { id: "catalog-apify-amazon", source: "Apify: Amazon Products", category: "第三方采集", source_type: "third_party_api", status: "needs_config", freshness: "not_configured", notes: "需要 APIFY_TOKEN。" },
  { id: "catalog-apify-tiktok", source: "Apify: TikTok Creative Center", category: "第三方采集", source_type: "third_party_api", status: "needs_config", freshness: "not_configured", notes: "需要 APIFY_TOKEN，通常还需要登录态。" },
  { id: "catalog-apify-meta", source: "Apify: Meta Ads Library", category: "第三方采集", source_type: "third_party_api", status: "needs_config", freshness: "not_configured", notes: "需要 APIFY_TOKEN。" },
  { id: "catalog-apify-etsy", source: "Apify: Etsy Products", category: "第三方采集", source_type: "third_party_api", status: "needs_config", freshness: "not_configured", notes: "需要 APIFY_TOKEN。" },
  { id: "catalog-apify-1688", source: "Apify: 1688 Products", category: "第三方采集", source_type: "third_party_api", status: "needs_config", freshness: "not_configured", notes: "需要 APIFY_TOKEN，通常还需要 1688 登录 cookie。" },
  { id: "catalog-apify-temu", source: "Apify: Temu Products", category: "第三方采集", source_type: "third_party_api", status: "needs_config", freshness: "not_configured", notes: "需要 APIFY_TOKEN。" },
  { id: "catalog-akshare", source: "AkShare", category: "股票/宏观", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "A 股、宏观、基金、期货等金融数据，来自 daily_stock_analysis 借鉴源。" },
  { id: "catalog-tushare", source: "Tushare", category: "股票/基本面", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "需要 Tushare token。" },
  { id: "catalog-pytdx", source: "Pytdx", category: "股票行情", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "通达信行情链路，适合行情补充和回测。" },
  { id: "catalog-baostock", source: "Baostock", category: "股票历史数据", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "A 股历史行情和基础财务数据。" },
  { id: "catalog-yfinance", source: "YFinance", category: "全球股票", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "Yahoo Finance 第三方库行情和公司数据。" },
  { id: "catalog-longbridge", source: "Longbridge OpenAPI", category: "券商行情", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "需要 Longbridge 开发者凭证。" },
  { id: "catalog-finnhub", source: "Finnhub", category: "全球股票", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "需要 FINNHUB_API_KEY。" },
  { id: "catalog-alpha-vantage", source: "AlphaVantage", category: "全球股票", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "需要 ALPHAVANTAGE_API_KEY。" },
  { id: "catalog-search-serpapi", source: "SerpAPI", category: "搜索/新闻", source_type: "third_party_api", status: "needs_config", freshness: "not_configured", notes: "搜索结果 API，用于新闻和趋势发现。" },
  { id: "catalog-search-tavily", source: "Tavily Search", category: "搜索/新闻", source_type: "third_party_api", status: "needs_config", freshness: "not_configured", notes: "研究型搜索 API，用于新闻发现。" },
  { id: "catalog-search-bocha", source: "Bocha Search", category: "中文搜索", source_type: "third_party_api", status: "needs_config", freshness: "not_configured", notes: "中文网页搜索 API。" },
  { id: "catalog-search-brave", source: "Brave Search", category: "搜索/新闻", source_type: "third_party_api", status: "needs_config", freshness: "not_configured", notes: "需要 BRAVE_SEARCH_API_KEY。" },
  { id: "catalog-search-searxng", source: "SearXNG", category: "自托管搜索", source_type: "self_hosted", status: "needs_config", freshness: "not_configured", notes: "配置 SEARXNG_URL 后可作为 metasearch 源。" },
  { id: "catalog-nasa-eonet", source: "NASA EONET: Natural Events", category: "自然灾害", source_type: "public_json", status: "pending", freshness: "unknown", notes: "NASA EONET 开放自然事件。" },
  { id: "catalog-noaa-alerts", source: "NOAA/NWS: Severe Weather Alerts", category: "极端天气", source_type: "public_geojson", status: "pending", freshness: "unknown", notes: "美国国家气象局实时预警 GeoJSON。" },
  { id: "catalog-noaa-swpc", source: "NOAA SWPC: Space Weather", category: "太空天气", source_type: "public_json", status: "pending", freshness: "unknown", notes: "NOAA SWPC Kp 指数等太空天气产品。" },
  { id: "catalog-celestrak-active", source: "CelesTrak: Active Satellites", category: "卫星/航天", source_type: "public_json", status: "pending", freshness: "unknown", notes: "CelesTrak 活跃卫星 GP 数据。" },
  { id: "catalog-opensky", source: "OpenSky Network", category: "航班/ADS-B", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "航班状态向量，建议配置账号以提高限额。" },
  { id: "catalog-wingbits", source: "Wingbits", category: "航班/ADS-B", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "WorldMonitor/OSINT 类航班情报源，需要授权。" },
  { id: "catalog-aisstream", source: "AISStream", category: "海事/AIS", source_type: "streaming_api", status: "needs_config", freshness: "not_configured", notes: "实时 AIS websocket，需要 AISSTREAM_API_KEY。" },
  { id: "catalog-shodan", source: "Shodan", category: "网络安全", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "互联网资产暴露搜索，需要 SHODAN_API_KEY。" },
  { id: "catalog-nasa-firms", source: "NASA FIRMS", category: "火情/卫星", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "NASA 火点和热异常，需要 FIRMS MAP_KEY。" },
  { id: "catalog-cloudflare-radar", source: "Cloudflare Radar", category: "互联网观测", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "网络流量、故障和安全趋势，需要 Cloudflare 凭证。" },
  { id: "catalog-imf-portwatch", source: "IMF PortWatch", category: "港口/供应链", source_type: "public_data", status: "third_party", freshness: "not_configured", notes: "港口和海运贸易扰动监测。" },
  { id: "catalog-openaq", source: "OpenAQ", category: "环境/空气质量", source_type: "public_api", status: "third_party", freshness: "not_configured", notes: "全球空气质量观测。" },
  { id: "catalog-abuseipdb", source: "AbuseIPDB", category: "网络安全", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "IP reputation 和 abuse reports，需要 API key。" },
  { id: "catalog-wikidata", source: "Wikidata", category: "实体增强", source_type: "public_api", status: "third_party", freshness: "not_configured", notes: "实体、组织、地点和基础设施补全。" },
  { id: "catalog-acled", source: "ACLED", category: "地缘风险", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "冲突和抗议事件数据，需要 ACLED API key。" },
  { id: "catalog-fred", source: "FRED", category: "宏观经济", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "美国和全球宏观序列，需要 FRED API key。" },
  { id: "catalog-eia", source: "EIA Open Data", category: "能源数据", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "能源库存、价格和供需数据，需要 EIA API key。" },
  { id: "catalog-un-comtrade", source: "UN Comtrade", category: "贸易/供应链", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "进出口和贸易流数据，需要 API key。" },
  { id: "catalog-bbc-world", source: "BBC: World", category: "全球新闻", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "BBC World RSS，全球新闻和地缘风险补充源。" },
  { id: "catalog-aljazeera-world", source: "Al Jazeera: World", category: "全球新闻", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "Al Jazeera World RSS，补充中东和新兴市场覆盖。" },
  { id: "catalog-cisa", source: "CISA: Cyber Advisories", category: "网络安全", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "CISA 官方安全公告和漏洞利用风险。" },
  { id: "catalog-gdacs", source: "GDACS: Disaster Alerts", category: "自然灾害", source_type: "public_rss", status: "pending", freshness: "unknown", notes: "GDACS 全球灾害预警。" },
  { id: "catalog-polymarket", source: "Polymarket: Active Markets", category: "预测市场", source_type: "public_json", status: "pending", freshness: "unknown", notes: "预测市场赔率和成交量，用于提前观察叙事变化。" },
  { id: "catalog-coingecko-trending", source: "CoinGecko: Trending", category: "加密资产", source_type: "public_json", status: "pending", freshness: "unknown", notes: "CoinGecko 热门搜索列表，用于加密叙事和流动性信号。" },
  { id: "catalog-usgs-earthquakes", source: "USGS: Earthquakes", category: "自然灾害", source_type: "public_geojson", status: "pending", freshness: "unknown", notes: "USGS 地震 GeoJSON feed。" },
  { id: "catalog-gdelt-geopolitics", source: "GDELT: Geopolitics", category: "地缘新闻", source_type: "public_json", status: "needs_config", freshness: "not_configured", notes: "GDELT Doc API 地缘风险查询，建议配置代理或 relay 后启用。" },
  { id: "catalog-gdelt-conflict", source: "GDELT: Conflict Risk", category: "冲突风险", source_type: "public_json", status: "needs_config", freshness: "not_configured", notes: "GDELT 冲突、封锁和供应链扰动查询。" },
  { id: "catalog-gdelt-energy", source: "GDELT: Energy Markets", category: "能源新闻", source_type: "public_json", status: "needs_config", freshness: "not_configured", notes: "GDELT 能源市场和价格事件查询。" },
  { id: "catalog-gdelt-ai-regulation", source: "GDELT: AI Regulation", category: "AI 监管", source_type: "public_json", status: "needs_config", freshness: "not_configured", notes: "GDELT AI 监管、芯片禁令和出口管制查询。" },
  { id: "catalog-anspire-search", source: "Anspire AI Search", category: "搜索/新闻", source_type: "third_party_api", status: "needs_config", freshness: "not_configured", notes: "daily_stock_analysis 借鉴搜索源，需要服务商凭证。" },
  { id: "catalog-minimax-search", source: "MiniMax Search", category: "搜索/新闻", source_type: "third_party_api", status: "needs_config", freshness: "not_configured", notes: "搜索/研究服务商，需要凭证。" },
  { id: "catalog-stock-sentiment", source: "Stock Sentiment API", category: "股票情绪", source_type: "third_party_api", status: "needs_config", freshness: "not_configured", notes: "市场和新闻情绪源，需要服务商凭证。" },
  { id: "catalog-tickflow", source: "TickFlow", category: "股票行情", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "market data provider，需要供应商授权。" },
  { id: "catalog-adsb-lol", source: "adsb.lol", category: "航班/ADS-B", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "社区 ADS-B 航空器 feed，需要限流和缓存。" },
  { id: "catalog-global-fishing-watch", source: "Global Fishing Watch", category: "海事/AIS", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "渔船活动和海事风险，需要 API 凭证。" },
  { id: "catalog-deepstate", source: "DeepState Map", category: "冲突风险", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "冲突地图和地缘风险观察源。" },
  { id: "catalog-amtrak", source: "Amtrak", category: "交通/铁路", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "铁路状态和交通扰动源。" },
  { id: "catalog-digitraffic", source: "DigiTraffic", category: "交通/海事", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "芬兰交通、海事和路况开放数据。" },
  { id: "catalog-satnogs", source: "SatNOGS", category: "卫星/航天", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "卫星地面站观测网络。" },
  { id: "catalog-tinygs", source: "TinyGS", category: "卫星/航天", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "社区卫星遥测网络，需要专用解析器。" },
  { id: "catalog-meshtastic", source: "Meshtastic MQTT", category: "无线电/网格", source_type: "streaming", status: "third_party", freshness: "not_configured", notes: "社区 mesh telemetry stream，需要流式接入和隐私过滤。" },
  { id: "catalog-aprs", source: "APRS-IS", category: "无线电/位置", source_type: "streaming", status: "third_party", freshness: "not_configured", notes: "业余无线电 packet reporting stream。" },
  { id: "catalog-kiwisdr", source: "KiwiSDR", category: "无线电/RF", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "公开 SDR 接收机目录。" },
  { id: "catalog-openmhz", source: "OpenMHZ", category: "无线电/音频", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "公开无线电音频监测源，需要下游转写/分类。" },
  { id: "catalog-wri-power", source: "WRI Global Power Plant Database", category: "能源基础设施", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "全球电厂基础数据，用于能源基础设施映射。" },
  { id: "catalog-nasa-gibs", source: "NASA GIBS", category: "卫星影像", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "卫星影像瓦片，用于视觉验证。" },
  { id: "catalog-esri-imagery", source: "Esri World Imagery", category: "卫星影像", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "遥感底图和影像上下文。" },
  { id: "catalog-planetary-computer", source: "Microsoft Planetary Computer", category: "地理空间", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "地理空间 catalog 和卫星资产，部分数据需要签名访问。" },
  { id: "catalog-copernicus", source: "Copernicus CDSE", category: "卫星影像", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "Sentinel/Copernicus 数据，需要账号和批处理链路。" },
  { id: "catalog-viirs", source: "VIIRS Nightlights", category: "经济活动代理", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "夜间灯光数据，可做经济活动代理指标。" },
  { id: "catalog-restcountries", source: "RestCountries", category: "实体增强", source_type: "public_api", status: "third_party", freshness: "not_configured", notes: "国家元数据和区域标准化。" },
  { id: "catalog-wikipedia", source: "Wikipedia", category: "实体增强", source_type: "public_api", status: "third_party", freshness: "not_configured", notes: "实体和文章上下文补充。" },
  { id: "catalog-nominatim", source: "Nominatim", category: "地理编码", source_type: "public_api", status: "third_party", freshness: "not_configured", notes: "OpenStreetMap geocoding，需要严格限流和 user-agent。" },
  { id: "catalog-carto", source: "CARTO", category: "地理空间", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "地图和地理空间数据平台。" },
  { id: "catalog-submarine-cable", source: "Submarine Cable Map", category: "互联网基础设施", source_type: "third_party", status: "third_party", freshness: "not_configured", notes: "海底光缆基础设施参考数据。" },
  { id: "catalog-icao-notam", source: "ICAO NOTAM", category: "航空/NOTAM", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "航空通告数据，稳定机器访问通常需要供应商凭证。" },
  { id: "catalog-faa-asws", source: "FAA ASWS", category: "航空天气", source_type: "official_api", status: "needs_config", freshness: "not_configured", notes: "航空天气/状态源，需要专用 aviation connector。" },
  { id: "catalog-1688-taobao-tmall", source: "1688/淘宝/天猫", category: "中文供给", source_type: "restricted", status: "restricted", freshness: "not_configured", notes: "反爬和授权限制强，建议接服务商或自有授权。" },
  { id: "catalog-pdd-temu", source: "拼多多/Temu", category: "价格/爆品", source_type: "restricted", status: "restricted", freshness: "not_configured", notes: "公开稳定 API 不足，建议接服务商或授权数据。" },
];

type ModelRegistryItem = {
  name: string;
  provider: string;
  endpoint: string;
  state: "active" | "inactive" | string;
  usage?: string | number | null;
  cost?: number | string | null;
  capabilities?: Record<string, unknown> | null;
  is_active?: boolean;
};

type ModelAllocationItem = {
  agent_name: string;
  model_name: string;
  recommended_model: string;
};

type ModelUsageSummaryItem = {
  skill_name: string;
  model: string;
  tokens: number;
  cost: number;
};

type ModelUsageSummary = {
  total_tokens: number;
  estimated_cost_cny: number;
  daily_avg_cost_cny: number;
  items: ModelUsageSummaryItem[];
};

type PipelineRunResult = {
  id: string;
  status: string;
  steps: string[];
  started_at?: string;
  finished_at?: string | null;
  message?: string | null;
};

type AgentConfigView = ModelAllocationItem & {
  display_name: string;
  role: string;
  system_prompt: string;
  status: string;
  cadence: string;
  budget: string;
  allowed_tools: string[];
  fail_strategy: string;
  max_daily_runs: number;
  max_daily_cost_cny: number;
  last_run?: string;
  updated_at?: string;
};

type AgentConfigPayload = Omit<AgentConfigView, "model_name" | "recommended_model" | "last_run">;

type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
};

type OpportunityBoxItem = {
  id: string;
  opportunity_id?: string | null;
  source_type: string;
  title: string;
  source: string;
  score: number;
  risk_level: string;
  status: string;
  rationale?: string[] | null;
  prediction?: Record<string, unknown> | null;
  notes?: string | null;
  created_at: string;
  updated_at?: string;
};

type PredictedOpportunity = {
  id: string;
  rank: number;
  title: string;
  category: string;
  source: string;
  sources?: string[];
  score: number;
  confidence: number;
  risk_level: string;
  horizon_days: number;
  reason: string;
  suggested_action: string;
  rationale: string[];
  prediction: Record<string, unknown>;
  saved?: boolean;
};

const navItems = [
  { label: "仪表盘", href: "/workspace/dashboard", icon: Radar },
  { label: "机会池", href: "/workspace/opportunities", icon: BarChart3 },
  { label: "机会箱", href: "/workspace/opportunity-box", icon: Archive },
  { label: "执行看板", href: "/workspace/actions", icon: ListChecks },
  { label: "每日简报", href: "/workspace/brief", icon: BookOpen },
  { label: "智能体", href: "/workspace/agents", icon: Bot },
  { label: "AI 对话", href: "/workspace/chat", icon: MessageSquareText },
  { label: "情景推演", href: "/workspace/scenarios", icon: Sparkles },
  { label: "数据源", href: "/workspace/sources", icon: Database },
  { label: "设置", href: "/workspace/settings", icon: Settings },
];

function navigate(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function usePath() {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  return path === "/" ? "/workspace/dashboard" : path;
}

function getDisplayApiBase() {
  return ACTIVE_API_BASE || API_CANDIDATE_BASES[0] || "未配置后端";
}

function resolveApiPath(path: string) {
  if (!path.startsWith("/")) {
    return `/${path}`;
  }
  return path;
}

function buildApiCandidates() {
  const bases = [...API_CANDIDATE_BASES];
  if (ACTIVE_API_BASE) {
    bases.unshift(ACTIVE_API_BASE);
  }
  return [...new Set(bases)];
}

function getErrorMessage(payload: unknown) {
  if (typeof payload === "object" && payload !== null && "error" in payload) {
    return String((payload as { error?: string }).error || "请求失败");
  }
  return "请求失败";
}

async function apiRequest<T>(path: string, init: RequestInit): Promise<T> {
  const cleanPath = resolveApiPath(path);
  const candidates = buildApiCandidates();
  if (!candidates.length) {
    throw new Error("未配置后端 API。在线 demo 展示静态界面；本地运行请启动 FastAPI 或设置 VITE_API_BASE_URL。");
  }
  let lastError = new Error("所有 API 地址暂不可用");
  for (const base of candidates) {
    const url = `${base}/api${cleanPath}`;
    try {
      const response = await fetch(url, init);
      const rawText = await response.text();
      let payload: ApiEnvelope<T> | unknown = {};
      try {
        payload = rawText ? JSON.parse(rawText) : { data: {} as T };
      } catch {
        throw new Error(`接口返回格式异常：${url}`);
      }
      if (!response.ok) {
        throw new Error(getErrorMessage(payload));
      }
      if (typeof payload === "object" && payload && "success" in payload && payload.success === false) {
        throw new Error(getErrorMessage(payload));
      }
      ACTIVE_API_BASE = base;
      return (payload as ApiEnvelope<T>).data;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error("请求失败");
      continue;
    }
  }
  throw lastError;
}

async function apiGet<T>(path: string): Promise<T> {
  return apiRequest<T>(path, {
    headers: { Accept: "application/json" }
  });
}

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json"
    },
    body: body ? JSON.stringify(body) : "{}"
  });
}

async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json"
    },
    body: body ? JSON.stringify(body) : "{}"
  });
}

async function apiDelete<T>(path: string): Promise<T> {
  return apiRequest<T>(path, {
    method: "DELETE",
    headers: { Accept: "application/json" }
  });
}

function formatDate(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function normalizeTag(input?: string | null): string {
  const text = (input || "").toLowerCase();
  const normalized = text.replace(/[\s_-]/g, "");
  if (normalized.includes("high") || normalized.includes("h")) return "high";
  if (normalized.includes("low") || normalized.includes("l")) return "low";
  return "medium";
}

function normalizeState(input?: string | null): string {
  return (input || "unknown").toLowerCase().replace(/_/g, "-").replace(/[^a-z0-9-]/g, "");
}

function asStringArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).filter(Boolean);
  }
  if (typeof value === "string" && value.trim()) {
    return [value.trim()];
  }
  return [];
}

function dimensionNumber(dimensions: OpportunityDimensions | null | undefined, key: keyof OpportunityDimensions, fallback = 0) {
  const raw = dimensions?.[key];
  const value = typeof raw === "number" ? raw : Number(raw);
  return Number.isFinite(value) ? value : fallback;
}

function dimensionPercent(dimensions: OpportunityDimensions | null | undefined, key: keyof OpportunityDimensions, fallback = 0) {
  return Math.round(Math.max(0, Math.min(1, dimensionNumber(dimensions, key, fallback))) * 100);
}

function firstValue(...values: Array<string | number | null | undefined>) {
  for (const value of values) {
    if (value !== null && value !== undefined && value !== "") {
      return String(value);
    }
  }
  return "--";
}

function displayListFromText(value?: string | null, maxItems = 4) {
  return String(value || "")
    .split(/[、，,；;\/]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, maxItems);
}

function uiLabel(value?: string | number | null) {
  const text = String(value ?? "");
  const labels: Record<string, string> = {
    All: "全部",
    AI: "AI",
    Commerce: "电商",
    Finance: "金融",
    SaaS: "SaaS",
    Social: "社交",
    S: "S 重点",
    A: "A 优先",
    B: "B 观察",
    C: "C 暂存",
    executable: "可执行",
    needs_validation: "需验证",
    watch: "仅观察",
    fresh: "新鲜",
    recent: "近 72h",
    stale: "陈旧",
    expired: "过期",
    unknown: "未知",
    not_configured: "未配置",
    all: "全部",
    in_progress: "进行中",
    completed: "已完成",
    pending: "待开始",
    not_started: "未开始",
    new: "新机会",
    live: "真实采集",
    demo: "演示数据",
    daily: "每日简报",
    predicted: "预测机会",
    manual: "手动添加",
    tracking: "跟踪中",
    low: "低",
    medium: "中",
    high: "高",
    normal: "正常",
    healthy: "正常",
    ready: "完全正常可用",
    configured: "已配置",
    not_ready: "未就绪",
    productive: "有有效产出",
    no_new: "无新增",
    refresh_due: "需要刷新",
    retry_needed: "需要重试",
    configure_needed: "需要配置",
    rate_limited: "被限流",
    blocked: "被阻断",
    degraded: "可用性下降",
    pending_sync: "未初始化状态",
    warning: "预警",
    offline: "离线",
    needs_config: "待配置",
    third_party: "第三方",
    restricted: "受限",
    aging: "变旧",
    active: "启用",
    inactive: "停用",
    paused: "暂停",
    disabled: "停用",
    idle: "空闲",
    running: "运行中",
    failed: "失败",
    profit: "盈利",
    loss: "亏损",
    collect: "采集",
    clean: "清洗",
    analyze: "分析",
    score: "评分",
    done: "已完成",
    inferred: "推断",
    stars: "Stars",
    forks: "Forks",
    points: "热度点数",
    comments: "评论数",
    traffic: "搜索流量",
    rank: "排名",
    rss_rank: "RSS 排名",
    review_count: "评论总数",
    variants: "商品变体",
    min_price: "最低价格",
    evidence_count: "证据数",
    language: "原始语言",
    translated_to: "翻译目标",
    translation_provider: "翻译方式",
    translation_agent: "翻译 Agent",
    translation_confidence: "翻译置信度",
    translated: "是否翻译",
    gap: "机会差",
    canonical_url: "规范链接",
    normalized_title: "规范标题",
    cluster_key: "聚合键",
    evidence_sources: "证据来源"
  };
  return labels[text] || text;
}

function metricDelta(value?: number) {
  const safeValue = Number(value || 0);
  if (safeValue === 0) return "持平";
  return `${safeValue > 0 ? "+" : ""}${safeValue}`;
}

function firstItems<T>(items?: T[], count = 3): T[] {
  return (items || []).slice(0, count);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function actionSummaryFromPrediction(prediction?: Record<string, unknown> | null): ActionSummary | null {
  if (!prediction) return null;
  const raw = prediction.action_summary;
  return isRecord(raw) ? raw as ActionSummary : null;
}

function fallbackActionSummary(title: string, firstStep?: string, source?: string): ActionSummary {
  return {
    opportunity: title,
    info_gap: source ? `利用 ${source} 里的新增信号先做小样本验证。` : "先把信号转成可验证的客户问题。",
    first_step: firstStep || "先找 5 个目标客户验证痛点和付费意愿",
    validation_plan: firstStep ? [firstStep] : ["先找 5 个目标客户验证痛点和付费意愿"],
    no_go_signals: ["没有明确客户愿意继续沟通", "验证后没有点击、回复、询价或试用意向"],
    budget: "小额验证",
    estimated_return: "待验证",
    roi: "待验证",
    execution_stage: "needs_validation",
    success_metric: "24-72 小时内拿到真实互动、询价或试用意向",
    fail_metric: "曝光后无互动或目标客户不认痛点"
  };
}

function mergeSourceCatalog(statusItems: SourceItem[] = []): SourceItem[] {
  const statusBySource = new Map(statusItems.map((item) => [item.source, item]));
  const merged = SOURCE_CATALOG.map((catalogItem) => {
    const statusItem = statusBySource.get(catalogItem.source);
    return {
      ...catalogItem,
      ...(statusItem || {}),
      id: statusItem?.id || catalogItem.id,
      source: catalogItem.source,
      category: catalogItem.category,
      source_type: catalogItem.source_type,
      notes: statusItem?.notes || catalogItem.notes,
      is_static: !statusItem,
    };
  });
  const catalogSources = new Set(SOURCE_CATALOG.map((item) => item.source));
  return [
    ...merged,
    ...statusItems.filter((item) => !catalogSources.has(item.source)),
  ];
}

const LIVE_PULL_SOURCE_NAMES = new Set([
  "GitHub",
  "GitHub: Agents",
  "GitHub: Ecommerce",
  "GitHub: Creator Tools",
  "Reddit",
  "Reddit: r/Entrepreneur",
  "Reddit: r/SideProject",
  "Reddit: r/SaaS",
  "Reddit: r/ecommerce",
  "Reddit: r/shopify",
  "HackerNews",
  "HackerNews: Startup",
  "arXiv",
  "Apple App Store",
  "Google Trends: US",
  "Product Hunt: Feed",
  "TechCrunch: AI",
  "TechCrunch: Startups",
  "Shopify: Public Catalog",
  "Amazon: Light Search",
  "Google Play: App Search",
  "TechRadar: TechCrunch",
  "TechRadar: MIT Technology Review",
  "TechRadar: The Verge",
  "TechRadar: Wired",
  "TechRadar: OpenAI Blog",
  "TechRadar: Google DeepMind",
  "TechRadar: Google AI Blog",
  "TechRadar: arXiv CS AI RSS",
  "TechRadar: MIT News AI",
  "TechRadar: GitHub Blog",
  "TechRadar: Hacker News RSS",
  "TechRadar: QbitAI",
  "TechRadar: Solidot",
  "TechRadar: OSChina",
  "TechRadar: ifanr",
  "TechRadar: SSPAI",
  "TechRadar: ITHome",
  "TechRadar: AWS Blog",
  "TechRadar: Google Cloud",
  "TechRadar: Canary Media",
  "TechRadar: Electrek",
  "TechRadar: KrebsOnSecurity",
  "TechRadar: STAT News",
  "TrendRadar: Yahoo Finance RSS",
  "SEC EDGAR: Form D",
  "SEC EDGAR: 13F",
  "SEC EDGAR: S-1 IPO",
  "36Kr: Newsflash",
  "36Kr: News",
  "BBC: World",
  "Al Jazeera: World",
  "CISA: Cyber Advisories",
  "GDACS: Disaster Alerts",
  "Polymarket: Active Markets",
  "CoinGecko: Trending",
  "USGS: Earthquakes",
  "NASA EONET: Natural Events",
  "NOAA/NWS: Severe Weather Alerts",
  "NOAA SWPC: Space Weather",
  "CelesTrak: Active Satellites",
]);

const REQUIRED_CONFIG_BY_SOURCE: Record<string, string> = {
  ACLED: "ACLED_API_KEY",
  FRED: "FRED_API_KEY",
  "EIA Open Data": "EIA_API_KEY",
  "UN Comtrade": "UN_COMTRADE_API_KEY",
  "Amazon SP-API": "AMAZON_SP_API_*",
  "Product Hunt API": "PRODUCT_HUNT_TOKEN",
  "Shopify Admin/Storefront": "SHOPIFY_*",
  "TikTok Shop/Creative Center": "TIKTOK_* 或服务商授权",
  "Meta Ads Library": "META_ACCESS_TOKEN",
  "Etsy Open API": "ETSY_API_KEY",
  "Apify: Amazon Products": "APIFY_TOKEN",
  "Apify: TikTok Creative Center": "APIFY_TOKEN",
  "Apify: Meta Ads Library": "APIFY_TOKEN",
  "Apify: Etsy Products": "APIFY_TOKEN",
  "Apify: 1688 Products": "APIFY_TOKEN + 登录态",
  "Apify: Temu Products": "APIFY_TOKEN",
  Tushare: "TUSHARE_TOKEN",
  "Longbridge OpenAPI": "LONGBRIDGE_*",
  TickFlow: "TICKFLOW_*",
  Finnhub: "FINNHUB_API_KEY",
  AlphaVantage: "ALPHAVANTAGE_API_KEY",
  "Anspire AI Search": "ANSPIRE_*",
  SerpAPI: "SERPAPI_API_KEY",
  "Tavily Search": "TAVILY_API_KEY",
  "Bocha Search": "BOCHA_API_KEY",
  "Brave Search": "BRAVE_SEARCH_API_KEY",
  SearXNG: "SEARXNG_URL",
  "MiniMax Search": "MINIMAX_*",
  "Stock Sentiment API": "STOCK_SENTIMENT_API_KEY",
  "OpenSky Network": "OPENSKY_*",
  Wingbits: "WINGBITS_*",
  AISStream: "AISSTREAM_API_KEY",
  "Global Fishing Watch": "GFW_API_KEY",
  Shodan: "SHODAN_API_KEY",
  "NASA FIRMS": "NASA_FIRMS_MAP_KEY",
  "Microsoft Planetary Computer": "签名访问配置",
  "Copernicus CDSE": "COPERNICUS_*",
  "Cloudflare Radar": "CLOUDFLARE_API_TOKEN",
  AbuseIPDB: "ABUSEIPDB_API_KEY",
  "ICAO NOTAM": "NOTAM/航空数据凭证",
  "FAA ASWS": "FAA/航空天气凭证",
  "GDELT: Geopolitics": "代理或 GDELT relay",
  "GDELT: Conflict Risk": "代理或 GDELT relay",
  "GDELT: Energy Markets": "代理或 GDELT relay",
  "GDELT: AI Regulation": "代理或 GDELT relay",
  "TrendRadar: Toutiao Hot": "NEWSNOW_API_BASE",
  "TrendRadar: Baidu Hot Search": "NEWSNOW_API_BASE",
  "TrendRadar: Wallstreetcn Hot": "NEWSNOW_API_BASE",
  "TrendRadar: The Paper": "NEWSNOW_API_BASE",
  "TrendRadar: Bilibili Hot Search": "NEWSNOW_API_BASE",
  "TrendRadar: CLS Hot": "NEWSNOW_API_BASE",
  "TrendRadar: Ifeng Hot": "NEWSNOW_API_BASE",
  "TrendRadar: Tieba Hot": "NEWSNOW_API_BASE",
  "TrendRadar: Weibo Hot": "NEWSNOW_API_BASE",
  "TrendRadar: Douyin Hot": "NEWSNOW_API_BASE",
  "TrendRadar: Zhihu Hot": "NEWSNOW_API_BASE",
  "TechRadar: Huxiu": "RSS 代理或 feed relay",
  "TechRadar: Jiqizhixin": "有效 RSS 或 feed relay",
  "TechRadar: Reuters Business": "Reuters API 或 feed relay",
};

type SourceCapability = "live" | "auth" | "integration" | "restricted" | "legacy" | "pending";

const SOURCE_CAPABILITY_LABELS: Record<SourceCapability, string> = {
  live: "实际拉取",
  auth: "需要授权",
  integration: "待接入",
  restricted: "受限",
  legacy: "历史源",
  pending: "待确认",
};

function isLegacySource(source: SourceItem) {
  return source.source_type === "legacy" || source.source === "微博" || source.id === "src-wechat";
}

function sourceRequiredConfig(source: SourceItem): string | null {
  return REQUIRED_CONFIG_BY_SOURCE[source.source] || null;
}

function sourceCapability(source: SourceItem): SourceCapability {
  if (isLegacySource(source)) return "legacy";
  if (LIVE_PULL_SOURCE_NAMES.has(source.source)) return "live";
  const status = normalizeState(source.config_status || source.status || "");
  if (status === "restricted" || source.source_type === "restricted") return "restricted";
  if (sourceRequiredConfig(source) || status === "needs_config") return "auth";
  if (status === "third_party" || ["third_party", "self_hosted", "streaming", "public_data"].includes(source.source_type || "")) return "integration";
  return source.is_static ? "pending" : "auth";
}

function sourceCapabilityText(source: SourceItem) {
  return SOURCE_CAPABILITY_LABELS[sourceCapability(source)];
}

function sourceConfigText(source: SourceItem) {
  const config = sourceRequiredConfig(source);
  if (config) return config;
  const capability = sourceCapability(source);
  if (capability === "live") return "无需额外授权";
  if (capability === "integration") return "需要 adapter/依赖封装";
  if (capability === "restricted") return "需授权数据或服务商";
  if (capability === "legacy") return "历史状态，不进入新采集";
  return "待确认配置";
}

type SourceCollectionState = "normal" | "issue" | "config" | "pending";
type SourceOperationalState =
  | "ready"
  | "no_new"
  | "refresh_due"
  | "expired"
  | "retry_needed"
  | "rate_limited"
  | "blocked"
  | "degraded"
  | "configure_needed"
  | "restricted"
  | "pending_sync";

function sourceCollectionState(source: SourceItem): SourceCollectionState {
  if (source.is_static) {
    const capability = sourceCapability(source);
    return capability === "live" || capability === "legacy" ? "pending" : "config";
  }
  if (source.config_status && source.config_status !== "configured") return "config";
  if (source.collection_status) {
    if (source.collection_status === "healthy" || source.collection_status === "degraded") return "normal";
    if (source.collection_status === "not_ready") return "config";
    return "issue";
  }
  if (
    source.status === "needs_config" ||
    source.status === "restricted" ||
    source.status === "third_party" ||
    source.freshness === "not_configured"
  ) {
    return "config";
  }
  if (source.status === "warning" || source.status === "offline" || source.status === "failed" || source.freshness === "offline") {
    return "issue";
  }
  return "normal";
}

function sourceDataFreshness(source: SourceItem): "fresh" | "stale" | "expired" | "unknown" | "not_configured" {
  const freshness = source.freshness_status || source.freshness;
  if (freshness === "fresh") return "fresh";
  if (freshness === "stale" || freshness === "aging" || freshness === "moderate") return "stale";
  if (freshness === "expired") return "expired";
  if (freshness === "not_configured") return "not_configured";
  return "unknown";
}

function sourceOperationalState(source: SourceItem): SourceOperationalState {
  if (source.is_static) {
    const capability = sourceCapability(source);
    if (capability === "auth") return "configure_needed";
    if (capability === "restricted") return "restricted";
    return "pending_sync";
  }
  if (source.operational_state) return normalizeState(source.operational_state) as SourceOperationalState;
  const collectionState = sourceCollectionState(source);
  const freshnessState = sourceDataFreshness(source);
  if (collectionState === "config") {
    return source.status === "restricted" ? "restricted" : "configure_needed";
  }
  if (collectionState === "issue") return "retry_needed";
  if (freshnessState === "expired") return "expired";
  if (freshnessState === "stale") return "refresh_due";
  if (freshnessState === "unknown") return "pending_sync";
  if ((source.signal_count_24h || 0) <= 0) return "no_new";
  return "ready";
}

function isNormalExpiredSource(source: SourceItem) {
  return sourceOperationalState(source) === "expired";
}

function isNormalStaleSource(source: SourceItem) {
  return sourceOperationalState(source) === "refresh_due";
}

function isRetryableSource(source: SourceItem) {
  const state = sourceOperationalState(source);
  if (sourceCapability(source) === "live") return state !== "no_new";
  return !source.is_static && ["expired", "refresh_due", "retry_needed", "rate_limited", "blocked", "degraded"].includes(state);
}

const agentCatalog: Array<AgentConfigPayload & { recommended_model: string }> = [
  {
    agent_name: "SourceCollectorAgent",
    display_name: "数据采集智能体",
    role: "采集 GitHub、Reddit、RSS、App Store 与扩展来源，产出原始信号。",
    system_prompt: "你负责发现可商业化的早期信号。优先保留来源、时间、热度指标和可验证链接，过滤低质量噪声。",
    status: "active",
    cadence: "每日 08:00 / 手动",
    budget: "低",
    allowed_tools: ["source_connectors", "rss_fetch", "github_api", "reddit_fetch"],
    fail_strategy: "retry_then_warn",
    max_daily_runs: 24,
    max_daily_cost_cny: 3,
    recommended_model: "GLM-5.1"
  },
  {
    agent_name: "ChineseLocalizationAgent",
    display_name: "中文化智能体",
    role: "保留原文并生成中文标题、摘要、关键词和元数据。",
    system_prompt: "你负责把英文或其他语言信号转成清晰中文，不夸大、不改写事实，保留原始标题和内容。",
    status: "active",
    cadence: "入库实时",
    budget: "低",
    allowed_tools: ["local_glossary", "language_detect"],
    fail_strategy: "fallback_local",
    max_daily_runs: 300,
    max_daily_cost_cny: 2,
    recommended_model: "Local glossary"
  },
  {
    agent_name: "OpportunityScoringAgent",
    display_name: "机会评分智能体",
    role: "按需求、动量、供给、竞争、执行、风险六维评分。",
    system_prompt: "你负责给商业机会打分。输出必须包含分数、风险、验证建议、反方场景，不允许只给泛泛结论。",
    status: "active",
    cadence: "清洗后",
    budget: "中",
    allowed_tools: ["scorecard", "evidence_metrics"],
    fail_strategy: "retry_then_warn",
    max_daily_runs: 120,
    max_daily_cost_cny: 8,
    recommended_model: "GLM-5.1"
  },
  {
    agent_name: "EvidenceAgent",
    display_name: "证据链智能体",
    role: "为机会详情生成证据链、来源解释和处理轨迹。",
    system_prompt: "你负责解释一条机会为什么值得看。所有结论都要能回到来源、指标或处理步骤。",
    status: "active",
    cadence: "详情预热",
    budget: "中",
    allowed_tools: ["opportunity_detail", "source_trace"],
    fail_strategy: "use_cached_evidence",
    max_daily_runs: 80,
    max_daily_cost_cny: 6,
    recommended_model: "GLM-5.1"
  },
  {
    agent_name: "DailyBriefAgent",
    display_name: "每日简报智能体",
    role: "把信号、机会、数据源、风险组织成每日行动简报。",
    system_prompt: "你给老板写行动简报。先给结论，再给 Top 机会、风险、数据源异常和今日待办。",
    status: "active",
    cadence: "每日 08:10 / 手动",
    budget: "低",
    allowed_tools: ["brief_builder", "cache_warmup"],
    fail_strategy: "retry_then_warn",
    max_daily_runs: 12,
    max_daily_cost_cny: 5,
    recommended_model: "GLM-5.1"
  },
  {
    agent_name: "RiskAgent",
    display_name: "风险智能体",
    role: "识别拥挤、平台、政策、噪声和执行风险。",
    system_prompt: "你负责唱反调。指出机会为什么可能失败，并给出降低损失的验证方式。",
    status: "active",
    cadence: "评分后",
    budget: "中",
    allowed_tools: ["risk_rules", "source_status"],
    fail_strategy: "mark_for_review",
    max_daily_runs: 80,
    max_daily_cost_cny: 6,
    recommended_model: "GLM-5.1"
  },
  {
    agent_name: "ChatAdvisorAgent",
    display_name: "经营对话智能体",
    role: "围绕日报、机会、数据源和执行记录进行经营问答。",
    system_prompt: "你是经营助手。回答必须结合当前日报、机会池和数据源，不确定时明确说明需要补采集或补证据。",
    status: "active",
    cadence: "按需",
    budget: "可控",
    allowed_tools: ["brief_latest", "opportunity_list", "source_status", "action_items"],
    fail_strategy: "answer_with_context_only",
    max_daily_runs: 200,
    max_daily_cost_cny: 10,
    recommended_model: "GLM-5.1"
  }
];

function buildAgentViews(allocations: ModelAllocationItem[], configs: AgentConfigPayload[], pipelineStatus?: PipelineRunResult | null): AgentConfigView[] {
  const allocationMap = new Map(allocations.map((item) => [item.agent_name, item]));
  const configMap = new Map(configs.map((item) => [item.agent_name, item]));
  return agentCatalog.map((agent) => {
    const allocation = allocationMap.get(agent.agent_name);
    const config = configMap.get(agent.agent_name);
    return {
      ...agent,
      ...config,
      model_name: allocation?.model_name || allocation?.recommended_model || agent.recommended_model,
      recommended_model: allocation?.recommended_model || agent.recommended_model,
      status: pipelineStatus?.status === "running" && agent.agent_name === "SourceCollectorAgent" ? "running" : config?.status || agent.status,
      last_run: pipelineStatus?.finished_at || pipelineStatus?.started_at
    };
  });
}

function buildAdvisorReply(input: string, brief: Brief | null, opportunities: Opportunity[], sources: SourceItem[]) {
  const text = input.toLowerCase();
  const payload = brief?.payload || {};
  const top = payload.top_opportunities || [];
  const first = top[0];
  const failedSources = (payload.source_status?.failed || []).map((item) => item.source);
  const needsConfig = (payload.source_status?.needs_config || []).map((item) => item.source);
  if (text.includes("数据源") || text.includes("失败") || text.includes("异常")) {
    const sourceNames = failedSources.length ? failedSources.slice(0, 5).join("、") : sources.filter((item) => item.status === "warning" || item.status === "offline").slice(0, 5).map((item) => item.source).join("、");
    return sourceNames
      ? `今天需要先看数据源：${sourceNames}。待配置来源还有 ${needsConfig.length} 个，商业侧信号完整度会受影响。`
      : "当前没有明显失败数据源，建议继续看 Top 机会和高分信号。";
  }
  if (text.includes("预算") || text.includes("低风险") || text.includes("推荐")) {
    const lowRisk = top.find((item) => item.risk_level !== "high") || first;
    if (lowRisk) {
      return `按低风险和小预算优先，我建议先验证「${lowRisk.title}」。分数 ${lowRisk.score}，风险 ${uiLabel(lowRisk.risk_level)}，预算 ${lowRisk.estimated_investment || "小额验证"}，动作是：${lowRisk.suggested_action}`;
    }
  }
  if (text.includes("为什么") || text.includes("原因")) {
    if (first) {
      return `「${first.title}」排前面，主要因为：${(first.hot_reasons || []).slice(0, 3).join("；")}。建议先做 ${first.window_hours} 小时最小验证，不要直接重仓。`;
    }
  }
  if (text.includes("待办") || text.includes("今天做什么")) {
    const todos = payload.todo || [];
    return todos.length
      ? `今天先做三件事：${todos.slice(0, 3).map((todo, index) => `${index + 1}. ${todo.title}，预算 ${todo.budget}`).join("；")}`
      : "今天先运行采集管线，然后重新生成日报。";
  }
  if (first) {
    return `今天最值得先看的机会是「${first.title}」。它的机会分是 ${first.score}，验证分 ${first.validation_score}，建议动作：${first.suggested_action}`;
  }
  if (opportunities.length) {
    const best = opportunities[0];
    return `机会池里当前最高的是「${best.playbook_name || best.playbook}」，分数 ${best.score}。建议打开详情看证据链后再决定是否执行。`;
  }
  return "当前缺少足够上下文，建议先运行采集管线并生成每日简报。";
}

const trendData = [
  { time: "00:00", signals: 11, high: 2 },
  { time: "04:00", signals: 18, high: 3 },
  { time: "08:00", signals: 23, high: 5 },
  { time: "12:00", signals: 31, high: 7 },
  { time: "16:00", signals: 28, high: 6 },
  { time: "20:00", signals: 36, high: 8 }
];

const platformData = [
  { name: "X", value: 452 },
  { name: "Reddit", value: 890 },
  { name: "HN", value: 210 },
  { name: "Bili", value: 156 },
  { name: "GitHub", value: 45 }
];

function App() {
  const path = usePath();
  const title = path.includes("/workspace/strategy")
    ? "机会详情"
    : path.includes("opportunity-box")
    ? "机会箱"
    : path.includes("opportunities")
    ? "机会池"
    : path.includes("actions")
      ? "执行看板"
        : path.includes("brief")
        ? "每日简报"
        : path.includes("agents")
          ? "智能体"
          : path.includes("chat")
            ? "AI 对话"
            : path.includes("scenarios")
              ? "情景推演"
              : path.includes("sources")
                ? "数据源"
                : path.includes("settings")
                  ? "设置"
                  : "仪表盘";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => navigate("/workspace/dashboard")}>
          <span className="brand-mark">
            <Zap size={18} />
          </span>
          <span>
            <strong>InfoEdge</strong>
            <small>商业信号情报平台</small>
          </span>
        </button>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = path.startsWith(item.href);
            return (
              <button key={item.href} className={`nav-item ${active ? "active" : ""}`} onClick={() => navigate(item.href)}>
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <div className="health-dot" />
          <span>接口：{getDisplayApiBase()}/api</span>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <p className="eyebrow">工作台 / 情报 / 监控 / 执行</p>
            <h1>{title}</h1>
          </div>
          <div className="top-actions">
            <label className="search">
              <Search size={17} />
              <input placeholder="搜索信号、机会、执行项..." />
            </label>
            <IconButton title="提醒">
              <Bell size={18} />
            </IconButton>
            <IconButton title="设置">
              <Settings size={18} />
            </IconButton>
          </div>
        </header>
        <RouteView path={path} />
      </main>
    </div>
  );
}

function RouteView({ path }: { path: string }) {
  if (path.includes("/workspace/opportunity-box")) return <OpportunityBoxPage />;
  if (path.includes("/workspace/opportunities")) return <OpportunitiesPage />;
  if (path.includes("/workspace/actions")) return <ActionsPage />;
  if (path.includes("/workspace/brief")) return <BriefPage />;
  if (path.includes("/workspace/agents")) return <AgentsPage />;
  if (path.includes("/workspace/chat")) return <ChatPage />;
  if (path.includes("/workspace/scenarios")) return <ScenariosPage />;
  if (path.includes("/workspace/sources")) return <SourcesPage />;
  if (path.includes("/workspace/settings")) return <SettingsPage />;
  const strategyMatch = path.match(/^\/workspace\/strategy\/([^/]+)/);
  if (strategyMatch) return <StrategyPage opportunityId={strategyMatch[1]} />;
  return <DashboardPage />;
}

function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<DashboardStats>({
    win_rate: 0,
    signals_24h: 0,
    high_level_signals: 0,
    active_sources: 0,
    source_health: "unknown",
    data_volume: 0
  });
  const [topCircles, setTopCircles] = useState<CircleStat[]>([]);
  const [topRegions, setTopRegions] = useState<RegionStat[]>([]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsResp, circlesResp, regionsResp] = await Promise.all([
        apiGet<DashboardStats>("/dashboard/stats"),
        apiGet<{ hours: number; items: CircleStat[] }>("/circles/stats?hours=24"),
        apiGet<{ hours: number; items: RegionStat[] }>("/regions/stats?hours=24")
      ]);
      setStats(statsResp);
      setTopCircles((circlesResp.items || []).slice(0, 3));
      setTopRegions((regionsResp.items || []).slice(0, 3));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "仪表盘加载失败";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const activeSignals = `S/A 信号：${stats.high_level_signals}/${stats.signals_24h}`;

  return (
    <div className="page-grid dashboard-grid">
      <section className="stats-row">
        <StatCard
          label="活跃信号"
          value={String(stats.signals_24h)}
          trend={activeSignals}
          icon={<Sparkles />}
        />
        <StatCard label="胜率" value={`${stats.win_rate}%`} trend="近 90 天回测" icon={<TrendingUp />} />
        <StatCard label="数据源" value={String(stats.active_sources)} trend={uiLabel(stats.source_health)} icon={<Database />} />
        <StatCard label="信号量" value={String(stats.data_volume)} trend="24 小时总量" icon={<Activity />} />
      </section>

      <section className="panel span-12">
        <div className="toolbar">
          <PanelHeader title="信号监控" action="实时数据流" icon={<Filter size={18} />} />
          <button className="secondary" data-testid="dashboard-refresh" onClick={load}>
            <RefreshCw size={16} /> {loading ? "刷新中..." : "刷新"}
          </button>
        </div>
        {error && <p style={{ color: "#fecaca" }}>{error}</p>}
        <div className="summary-grid" style={{ marginTop: "14px" }}>
          <div className="metric">
            <span>热门圈层</span>
            {topCircles.length ? (
              topCircles.map((row) => <Metric key={row.circle} label={row.circle} value={`${row.count} 条，均分 ${row.avg_score}`} />)
            ) : (
              <Metric label="热门圈层" value="暂无数据" />
            )}
          </div>
          <div className="metric">
            <span>热门区域</span>
            {topRegions.length ? (
              topRegions.map((row) => <Metric key={row.region} label={row.region} value={`${row.count} 条，均分 ${row.avg_score}`} />)
            ) : (
              <Metric label="热门区域" value="暂无数据" />
            )}
          </div>
          <SignalPulse offline={Boolean(error)} />
        </div>
      </section>

      <section className="panel span-7">
        <PanelHeader title="信号趋势" action="24 小时" icon={<LineTitle icon={false} />} />
        <TrendChart />
      </section>
      <section className="panel span-5">
        <PanelHeader title="平台分布" action="按数据源" icon={<BarChart3 size={18} />} />
        <PlatformBar />
      </section>
    </div>
  );
}

function LineTitle({ icon }: { icon: boolean }) {
  return <LineChart size={18} />;
}

function SignalPulse({ offline }: { offline: boolean }) {
  return (
    <p className="metric" style={{ marginTop: "4px" }}>
      {offline
        ? "在线 demo 当前展示静态界面；启动 FastAPI 或设置 VITE_API_BASE_URL 后会读取真实 API 数据。"
        : "核心模块已经接入后端真实接口；机会列表和机会详情都直接读取 API 数据。"}
    </p>
  );
}

function OpportunitiesPage() {
  const [rows, setRows] = useState<Opportunity[]>([]);
  const [total, setTotal] = useState(0);
  const [totalAll, setTotalAll] = useState(0);
  const [sort, setSort] = useState<"score" | "level" | "window_hours" | "created_at" | "evidence_at">("evidence_at");
  const [circle, setCircle] = useState("All");
  const [levelFilter, setLevelFilter] = useState("all");
  const [stageFilter, setStageFilter] = useState("all");
  const [recencyFilter, setRecencyFilter] = useState("all");
  const [dataTypeFilter, setDataTypeFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [executingId, setExecutingId] = useState<string | null>(null);
  const [savingBoxId, setSavingBoxId] = useState<string | null>(null);

  const circles = ["All", "AI", "Commerce", "Finance", "SaaS", "Social"];
  const levelDefinitions = [
    { level: "S", label: "重点推进", note: "高分强信号" },
    { level: "A", label: "优先验证", note: "值得排期" },
    { level: "B", label: "观察试探", note: "低成本看" },
    { level: "C", label: "暂存复盘", note: "先不投入" }
  ];
  const levels = ["all", ...levelDefinitions.map((item) => item.level)];
  const stages = ["all", "executable", "needs_validation", "watch"];
  const recencies = ["all", "fresh", "recent", "stale", "expired", "unknown"];
  const dataTypes = ["all", "live", "demo"];
  const sortOptions: Array<{ value: typeof sort; label: string }> = [
    { value: "score", label: "分数" },
    { value: "created_at", label: "最新" },
    { value: "evidence_at", label: "证据时间" },
    { value: "window_hours", label: "窗口期" },
    { value: "level", label: "等级" }
  ];

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const query = new URLSearchParams({ sort, limit: "50" });
      if (circle !== "All") query.set("circle", circle);
      if (levelFilter !== "all") query.set("level", levelFilter);
      if (stageFilter !== "all") query.set("stage", stageFilter);
      if (recencyFilter !== "all") query.set("recency", recencyFilter);
      if (dataTypeFilter !== "all") query.set("data_type", dataTypeFilter);
      const data = await apiGet<ListResponse<Opportunity>>(`/opportunities?${query.toString()}`);
      setRows(data.items || []);
      setTotal(data.total || 0);
      setTotalAll(data.total_all || data.total || 0);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "机会加载失败";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [sort, circle, levelFilter, stageFilter, recencyFilter, dataTypeFilter]);

  const opportunitySummary = useMemo(() => {
    const stageCounts = rows.reduce<Record<string, number>>((acc, item) => {
      const stage = item.opportunity_stage || "watch";
      acc[stage] = (acc[stage] || 0) + 1;
      return acc;
    }, {});
    const riskCounts = rows.reduce<Record<string, number>>((acc, item) => {
      const risk = normalizeState(item.risk_level || "medium");
      acc[risk] = (acc[risk] || 0) + 1;
      return acc;
    }, {});
    const levelCounts = rows.reduce<Record<string, number>>((acc, item) => {
      const level = item.level || "B";
      acc[level] = (acc[level] || 0) + 1;
      return acc;
    }, {});
    const freshEvidence = rows.filter((item) => item.evidence_freshness === "fresh").length;
    const freshContent = rows.filter((item) => item.content_recency === "fresh").length;
    const expiredContent = rows.filter((item) => item.content_recency === "expired").length;
    const demoCount = rows.filter((item) => item.data_type === "demo").length;
    const blocked = rows.filter((item) => item.execution_gate_passed === false).length;
    const avgScore = rows.length
      ? Math.round(rows.reduce((sum, item) => sum + Number(item.score || 0), 0) / rows.length)
      : 0;
    return {
      avgScore,
      blocked,
      demoCount,
      expiredContent,
      freshEvidence,
      freshContent,
      levelCounts,
      riskCounts,
      stageCounts,
      top: rows[0],
    };
  }, [rows]);

  const executeOpportunity = async (id: string) => {
    setExecutingId(id);
    setMessage(null);
    try {
      const payload = await apiPost<{ message?: string }>(`/opportunities/${id}/execute`, { opportunity_id: id });
      setMessage(payload.message || "已开始执行");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "执行启动失败");
    } finally {
      setExecutingId(null);
    }
  };

  const saveOpportunityToBox = async (item: Opportunity) => {
    setSavingBoxId(item.id);
    setMessage(null);
    setError(null);
    try {
      await apiPost<OpportunityBoxItem>("/opportunity-box", {
        opportunity_id: item.id,
        source_type: "manual",
        title: item.business_title || item.title || item.playbook_name || item.id,
        source: item.source || item.playbook_name || item.playbook,
        score: item.score,
        risk_level: item.risk_level,
        rationale: item.action_summary?.reasons || item.execution_reasons || [],
        prediction: { action_summary: item.action_summary },
        notes: `下一步：${item.action_summary?.first_step || "小样本验证"}`
      });
      setMessage("已存入机会箱，后续可以按候选、验证、执行、复盘继续跟踪。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "存入机会箱失败");
    } finally {
      setSavingBoxId(null);
    }
  };

  return (
    <div className="page-grid">
      <section className="panel span-12 opportunity-overview">
        <div className="toolbar">
          <PanelHeader title="机会池总览" action={`当前筛选 ${total} 条 / 全量 ${totalAll || total} 条`} icon={<Target size={18} />} />
          <button className="select-button" data-testid="opportunities-refresh" onClick={() => load()}>
            <RefreshCw size={16} /> {loading ? "刷新中..." : "刷新"}
          </button>
        </div>
        {message && <div className="story-card">{message}</div>}
        {error && <p style={{ color: "#fca5a5" }}>{error}</p>}
        <div className="opportunity-overview-grid">
          <Metric label="机会总数" value={String(total)} />
          <Metric label="当前平均分" value={String(opportunitySummary.avgScore || "--")} />
          <Metric label="可执行" value={String(opportunitySummary.stageCounts.executable || 0)} />
          <Metric label="内容新鲜" value={`${opportunitySummary.freshContent}/${rows.length}`} />
          <Metric label="需验证" value={String(opportunitySummary.stageCounts.needs_validation || 0)} />
          <Metric label="仅观察" value={String(opportunitySummary.stageCounts.watch || 0)} />
          <Metric label="内容过期" value={String(opportunitySummary.expiredContent)} />
          <Metric label="演示数据" value={String(opportunitySummary.demoCount)} />
        </div>
        <div className="opportunity-overview-bottom">
          <div className="opportunity-stage-strip">
            {["executable", "needs_validation", "watch"].map((stage) => (
              <button key={stage} className={`stage-${normalizeState(stage)}`}>
                <strong>{opportunitySummary.stageCounts[stage] || 0}</strong>
                <span>{uiLabel(stage)}</span>
              </button>
            ))}
          </div>
          <div className="opportunity-level-row">
            {levelDefinitions.map((item) => (
              <button
                key={item.level}
                className={`level-card level-card-${item.level} ${levelFilter === item.level ? "selected" : ""}`}
                onClick={() => setLevelFilter(levelFilter === item.level ? "all" : item.level)}
              >
                <span>
                  {item.label}
                  <small>{item.note}</small>
                </span>
                <strong>{item.level}</strong>
                {opportunitySummary.levelCounts[item.level] || 0}
              </button>
            ))}
          </div>
          <p className="muted-copy">
            {opportunitySummary.top
              ? `当前首条机会：${opportunitySummary.top.business_title || opportunitySummary.top.title || opportunitySummary.top.playbook_name || opportunitySummary.top.playbook}，分数 ${opportunitySummary.top.score}。`
              : "当前筛选条件下暂无机会。"}
          </p>
        </div>
      </section>

      <section className="panel span-12">
        <div className="toolbar">
          <PanelHeader title="机会列表" action="按筛选结果展示" icon={<ListChecks size={18} />} />
          <div className="toolbar-right">
            <Segmented values={circles} active={circle} setActive={setCircle} />
            <select
              className="select-button"
              value={sort}
              onChange={(event) => setSort(event.target.value as typeof sort)}
            >
              {sortOptions.map((item) => (
                <option key={item.value} value={item.value}>
                  排序：{item.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="opportunity-filter-bar">
          <Segmented values={levels} active={levelFilter} setActive={setLevelFilter} />
          <Segmented values={stages} active={stageFilter} setActive={setStageFilter} />
          <Segmented values={recencies} active={recencyFilter} setActive={setRecencyFilter} />
          <Segmented values={dataTypes} active={dataTypeFilter} setActive={setDataTypeFilter} />
        </div>
        {loading ? (
          <p style={{ padding: 12 }}>机会加载中...</p>
        ) : (
          <div className="opportunity-action-list">
            {rows.map((item) => {
              const title = item.business_title || item.title || item.playbook_name || item.playbook || item.id;
              const summary = item.action_summary || fallbackActionSummary(title, item.strategies?.[0], item.source);
              const blockers = summary.blockers?.length ? summary.blockers : item.execution_blockers || [];
              const validationPlan = summary.validation_plan?.length ? summary.validation_plan : item.strategies || [];
              return (
                <article className="opportunity-action-card" key={item.id}>
                  <div className="action-card-main">
                    <div className="action-card-head">
                      <div>
                        <LevelBadge level={item.level || "B"} score={item.score || 0} />
                        <GateBadge stage={summary.execution_stage || item.opportunity_stage} freshness={item.evidence_freshness} />
                      </div>
                      <span className={`freshness freshness-${normalizeState(item.content_recency || "unknown")}`}>
                        {uiLabel(item.content_recency || "unknown")}
                      </span>
                    </div>
                    <button className="text-link action-title" onClick={() => navigate(`/workspace/strategy/${item.id}`)}>
                      {title}
                    </button>
                    <p className="action-opportunity-line">{summary.opportunity}</p>
                    <div className="action-info-gap">
                      <span>可利用的信息差</span>
                      <p>{summary.info_gap}</p>
                    </div>
                    <div className="action-next-step">
                      <span>第一步验证</span>
                      <strong>{summary.first_step || validationPlan[0] || "先做最小验证"}</strong>
                      <small>成功标准：{summary.success_metric || "拿到真实互动或付费意向"}</small>
                    </div>
                    <div className="action-card-tags">
                      <span>卖：{summary.what_to_sell || item.playbook_name}</span>
                      <span>给：{summary.who_pays || "目标客户"}</span>
                      <span>预算：{summary.budget || item.estimated_investment}</span>
                      <span>ROI：{summary.roi || item.roi_ratio || "待验证"}</span>
                    </div>
                  </div>
                  <aside className="action-card-side">
                    <Metric label="窗口期" value={`${item.window_hours || 0}h`} />
                    <Metric label="验证分" value={String(item.validation_score || "--")} />
                    <Metric label="最大亏损" value={summary.max_loss || item.max_loss || "--"} />
                    <Metric label="回本点" value={summary.breakeven || item.breakeven || "--"} />
                    <div className="action-checklist">
                      <h3>{blockers.length ? "阻塞原因" : "执行依据"}</h3>
                      {(blockers.length ? blockers : summary.reasons || item.execution_reasons || []).slice(0, 3).map((text) => (
                        <p key={text}>{text}</p>
                      ))}
                      {!blockers.length && !summary.reasons?.length && <p>已有行动摘要，可进入详情查看证据链。</p>}
                    </div>
                    <div className="feedback compact">
                      <button className="secondary small" onClick={() => navigate(`/workspace/strategy/${item.id}`)}>
                        详情
                      </button>
                      <button
                        className="secondary small"
                        onClick={() => saveOpportunityToBox(item)}
                        disabled={savingBoxId === item.id}
                      >
                        <Archive size={14} /> {savingBoxId === item.id ? "保存中..." : "存入箱"}
                      </button>
                      <button
                        className="primary small"
                        data-testid={`opportunity-execute-${item.id}`}
                        onClick={() => executeOpportunity(item.id)}
                        disabled={executingId === item.id || item.execution_gate_passed === false}
                        title={blockers.join("；") || "开始执行"}
                      >
                        {executingId === item.id ? "启动中..." : "执行"}
                      </button>
                    </div>
                  </aside>
                </article>
              );
            })}
            {!rows.length && <p className="muted-copy">接口暂未返回机会。</p>}
          </div>
        )}
      </section>
    </div>
  );
}

function StrategyPage({ opportunityId }: { opportunityId: string }) {
  const [loading, setLoading] = useState(true);
  const [opportunity, setOpportunity] = useState<Opportunity | null>(null);
  const [signal, setSignal] = useState<Signal | null>(null);
  const [evidence, setEvidence] = useState<OpportunityEvidence | null>(null);
  const [risk, setRisk] = useState<OpportunityExtra | null>(null);
  const [validation, setValidation] = useState<OpportunityExtra | null>(null);
  const [roi, setRoi] = useState<OpportunityExtra | null>(null);
  const [oci, setOci] = useState<OpportunityExtra | null>(null);
  const [deepAnalysis, setDeepAnalysis] = useState<DeepOpportunityAnalysis | null>(null);
  const [deepLoading, setDeepLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [execMessage, setExecMessage] = useState<string | null>(null);
  const [savingBox, setSavingBox] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const detail = await apiGet<OpportunityDetail>(`/opportunities/${opportunityId}`);
      setOpportunity(detail.opportunity);
      setSignal(detail.signal);
      setEvidence(detail.evidence || null);
      setRisk(detail.risk || null);
      setValidation(detail.validation || null);
      setRoi(detail.roi || null);
      setOci(detail.oci || null);
      setDeepAnalysis(detail.deep_analysis || detail.analysis?.analysis?.deep_analysis || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "详情加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [opportunityId]);

  const launch = async () => {
    try {
      const data = await apiPost<{ message?: string }>(`/opportunities/${opportunityId}/execute`, { opportunity_id: opportunityId });
      setExecMessage(data.message || "已开始执行");
    } catch (err) {
      setError(err instanceof Error ? err.message : "执行启动失败");
    }
  };

  const saveToBox = async () => {
    if (!opportunity) return;
    setSavingBox(true);
    setExecMessage(null);
    try {
      await apiPost<OpportunityBoxItem>("/opportunity-box", {
        opportunity_id: opportunity.id,
        source_type: "manual",
        title: opportunity.business_title || opportunity.title || opportunity.playbook_name || opportunity.id,
        source: opportunity.source || opportunity.playbook_name || opportunity.playbook,
        score: opportunity.score,
        risk_level: opportunity.risk_level,
        rationale: opportunity.action_summary?.reasons || opportunity.execution_reasons || [],
        prediction: { action_summary: opportunity.action_summary },
        notes: `下一步：${opportunity.action_summary?.first_step || "小样本验证"}`
      });
      setExecMessage("已保存到机会箱。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "存入机会箱失败");
    } finally {
      setSavingBox(false);
    }
  };

  const runDeepAnalysis = async () => {
    setDeepLoading(true);
    setExecMessage(null);
    try {
      const data = await apiPost<{ deep_analysis: DeepOpportunityAnalysis; message?: string }>(
        `/opportunities/${opportunityId}/deep-analysis`,
        {}
      );
      setDeepAnalysis(data.deep_analysis);
      setExecMessage(data.message || "AI 深入分析已生成");
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 深入分析失败");
    } finally {
      setDeepLoading(false);
    }
  };

  if (loading) {
    return <p className="panel span-12">机会详情加载中...</p>;
  }
  if (error || !opportunity) {
    return <p className="panel span-12">{error || "未找到该机会。"}</p>;
  }

  const dimensions: OpportunityDimensions = opportunity.dimensions || {};
  const rationale = asStringArray(dimensions.rationale);
  const sources = asStringArray(evidence?.sources?.length ? evidence.sources : dimensions.sources);
  const riskFactors = [
    ...asStringArray(opportunity.risk_factors),
    ...asStringArray(risk?.risk_factors)
  ].filter((item, index, arr) => arr.indexOf(item) === index);
  const steps = opportunity.strategies && opportunity.strategies.length ? opportunity.strategies : [
    "收集证据，验证信号来源是否一致",
    "量化需求和转化假设",
    "准备成本模型和执行排期",
    "启动第一批测试，观察用户反馈",
    "根据 72 小时反馈继续优化"
  ];
  const evidenceCount = dimensionNumber(dimensions, "evidence_count", Math.max(1, sources.length));
  const effectiveEvidenceCount = opportunity.evidence_count_effective ?? evidenceCount;
  const hotReasons = evidence?.hot_reasons?.length ? evidence.hot_reasons : rationale;
  const pipelineSteps = evidence?.pipeline_steps || [];
  const rawMerchantAnalysis = evidence?.merchant_analysis;
  const rawMerchantAnalysisText = JSON.stringify(rawMerchantAnalysis || {});
  const merchantAnalysisLooksStale = Boolean(rawMerchantAnalysis) && (
    rawMerchantAnalysis?.analysis_version !== "merchant_analysis_v7"
    || /Prediction market leading-signal watch|Hantavirus pandemic in 2026\?/i.test(rawMerchantAnalysisText)
  );
  const merchantAnalysis = merchantAnalysisLooksStale ? undefined : rawMerchantAnalysis;
  const visibleMetrics = Object.entries(evidence?.metrics || {})
    .filter(([key, value]) => value !== null && value !== undefined && value !== "" && !key.includes("original") && !key.includes("_zh"))
    .slice(0, 10);
  const decision = opportunity.level === "S" || opportunity.score >= 90
    ? "优先下场"
    : opportunity.score >= 75
      ? "小成本验证"
      : "继续观察";
  const gateDecision = opportunity.execution_gate_passed === false
    ? uiLabel(opportunity.opportunity_stage || "watch")
    : decision;
  const currentStep = Number(opportunity.current_step || 0);
  const chartData = [
    { axis: "需求", value: dimensionPercent(dimensions, "demand", 0.55) },
    { axis: "动量", value: dimensionPercent(dimensions, "momentum", 0.55) },
    { axis: "供给", value: dimensionPercent(dimensions, "supply", 0.55) },
    { axis: "竞争", value: dimensionPercent(dimensions, "competition_adjusted", 0.5) },
    { axis: "执行", value: dimensionPercent(dimensions, "execution", 0.55) },
    { axis: "风险缓冲", value: dimensionPercent(dimensions, "risk_adjusted", 0.5) }
  ];
  const opportunityLabel = opportunity.business_title || opportunity.title || opportunity.playbook_name || opportunity.playbook;
  const evidenceLabel = evidence?.title_zh || evidence?.title_original || signal?.title || opportunity.evidence_title || opportunityLabel;
  const actionSummary = opportunity.action_summary || fallbackActionSummary(opportunityLabel, opportunity.strategies?.[0], evidence?.source || opportunity.source);
  const summaryLine = merchantAnalysis?.opportunity_summary
    || actionSummary.opportunity
    || `这是一个把「${evidenceLabel}」转成可验证产品、服务或线索清单的机会。`;
  const sourceRecord = evidence?.source_record;
  const sourceRecordTitle = sourceRecord?.title || evidence?.specific_content?.title || evidenceLabel;
  const sourceRecordContent = sourceRecord?.content_excerpt
    || evidence?.specific_content?.content
    || evidence?.content_zh
    || evidence?.content_original
    || merchantAnalysis?.source_context
    || "暂无可展示的正文摘要，建议打开原始来源继续查看。";
  const commercialCustomers = merchantAnalysis?.who_needs_it?.length
    ? merchantAnalysis.who_needs_it
    : (displayListFromText(actionSummary.who_pays).length ? displayListFromText(actionSummary.who_pays) : ["目标客户待验证"]);
  const commercialAngles = merchantAnalysis?.business_angles?.length
    ? merchantAnalysis.business_angles
    : (actionSummary.what_to_sell ? [actionSummary.what_to_sell] : ["信息服务、工具订阅或线索清单"]);
  const commercialWhyNow = merchantAnalysis?.why_now?.length
    ? merchantAnalysis.why_now
    : [actionSummary.why_now || `机会分 ${opportunity.score}，验证分 ${opportunity.validation_score}。`];
  const commercialValidation = merchantAnalysis?.validation_plan?.length
    ? merchantAnalysis.validation_plan
    : (actionSummary.validation_plan?.length ? actionSummary.validation_plan : steps.slice(0, 4));
  const commercialNoGo = merchantAnalysis?.no_go_signals?.length
    ? merchantAnalysis.no_go_signals
    : (actionSummary.no_go_signals?.length ? actionSummary.no_go_signals : riskFactors.slice(0, 3));
  const commercialSourceContext = merchantAnalysis?.source_context
    || actionSummary.opportunity
    || evidence?.content_zh
    || "暂无更多中文来源摘要，建议打开原始来源继续查看。";
  const executionBrief = merchantAnalysis?.execution_brief;
  const customerScenarios = merchantAnalysis?.customer_scenarios || [];
  const offerPackages = merchantAnalysis?.offer_packages || [];
  const merchantNextActions = merchantAnalysis?.next_actions || [];
  const agentConfig = merchantAnalysis?.agent_config;
  const sourceRecordOriginal = sourceRecord?.content_original_excerpt
    || evidence?.specific_content?.original_content
    || evidence?.content_original;
  const sourceRecordMetrics = Object.entries(sourceRecord?.key_metrics || evidence?.specific_content?.metrics || {})
    .filter(([, value]) => value !== null && value !== undefined && value !== "" && (!Array.isArray(value) || value.length > 0))
    .slice(0, 10);
  const explainerCards = [
    {
      label: "卖什么",
      value: actionSummary.what_to_sell || merchantAnalysis?.what_to_sell || merchantAnalysis?.business_angles?.join("、") || "信息服务、工具订阅、服务包或线索清单"
    },
    {
      label: "卖给谁",
      value: actionSummary.who_pays || merchantAnalysis?.who_pays || merchantAnalysis?.who_needs_it?.join("、") || "有明确痛点或决策需求的目标客户"
    },
    {
      label: "为什么付钱",
      value: merchantAnalysis?.why_they_pay || merchantAnalysis?.why_opportunity || "因为它能帮客户更快做判断、降低风险、找到供给或抓住需求。"
    },
    {
      label: "第一步怎么试",
      value: actionSummary.first_step || merchantAnalysis?.first_test || steps[0] || "先做一页说明或一个最小样品，找 5 个目标客户验证。"
    },
    {
      label: "不是什么",
      value: merchantAnalysis?.not_the_opportunity || "不是把热度当结论，也不是跳过验证直接重仓。"
    },
    {
      label: "现在要问",
      value: merchantAnalysis?.decision_question || "有没有明确客户愿意为这个信息、工具、服务或替代方案付费？"
    }
  ];
  const deepField = (item: DeepAnalysisItem, key: string) => {
    const value = item[key];
    if (Array.isArray(value)) return value.join("、");
    if (value && typeof value === "object") return JSON.stringify(value);
    return firstValue(value as string | number | null | undefined);
  };
  const verdict = opportunity.detail_verdict;

  if (verdict) {
    const verdictFacts = verdict.evidence_facts || [];
    const verdictWhy = verdict.why || [];
    const verdictNext = verdict.next_steps || [];
    const verdictMissing = verdict.missing_evidence || [];
    return (
      <div className="page-grid clear-detail-page">
        <section className="panel span-12 clear-hero">
          <button className="ghost" onClick={() => navigate("/workspace/opportunities")}>
            <ArrowLeft size={17} /> 返回机会池
          </button>
          <div>
            <span className={`verdict-pill verdict-${verdict.label || "unknown"}`}>{verdict.label || "待判断"}</span>
            <h2>{verdict.headline || opportunityLabel}</h2>
            <p>{verdict.summary || "这条机会还没有形成明确处理结论。"}</p>
          </div>
          <div className="clear-hero-actions">
            <button className="secondary" onClick={saveToBox} disabled={savingBox}>
              <Archive size={16} /> {savingBox ? "保存中..." : "存入机会箱"}
            </button>
            <button
              className="primary"
              onClick={launch}
              disabled={opportunity.execution_gate_passed === false || verdict.label !== "可执行"}
              title={verdict.do_not_do || opportunity.execution_blockers?.join("；") || "开始执行"}
            >
              开始执行
            </button>
            {execMessage && <p className="story-card">{execMessage}</p>}
          </div>
        </section>

        {verdict.detail_story ? (
          <section className="panel span-12 clear-story-panel">
            <PanelHeader title="这条线索到底是什么" action="详情" icon={<Sparkles size={18} />} />
            <div className="clear-story-grid">
              <article>
                <h3>它本身在说什么</h3>
                <p>{verdict.detail_story.what_it_is}</p>
              </article>
              <article>
                <h3>它可能说明什么痛点</h3>
                <p>{verdict.detail_story.why_it_matters}</p>
              </article>
              <article>
                <h3>可能的机会方向</h3>
                <p>{verdict.detail_story.opportunity_angle}</p>
              </article>
              <article>
                <h3>现在还不能确定什么</h3>
                <p>{verdict.detail_story.current_limit}</p>
              </article>
            </div>
            {verdict.key_question && <p className="clear-key-question">{verdict.key_question}</p>}
          </section>
        ) : null}

        <section className="panel span-12 clear-verdict-panel">
          <PanelHeader title="为什么这么处理" action="只看事实和缺口" icon={<ShieldCheck size={18} />} />
          <div className="clear-fact-grid">
            {verdictFacts.map((item, index) => (
              <article key={`${item.label}-${index}`}>
                <span>{item.label || `事实 ${index + 1}`}</span>
                <strong>{item.value || "--"}</strong>
              </article>
            ))}
          </div>
          <div className="clear-two-column">
            <article>
              <h3>依据</h3>
              {(verdictWhy.length ? verdictWhy : ["暂无足够依据。"]).map((item) => <p key={item}>{item}</p>)}
            </article>
            <article>
              <h3>缺什么</h3>
              {(verdictMissing.length ? verdictMissing : ["缺少可执行证据。"]).map((item) => <p key={item}>{item}</p>)}
            </article>
          </div>
          <div className="clear-next-steps">
            <h3>下一步只做这几件事</h3>
            {verdictNext.map((item, index) => (
              <article key={item}>
                <strong>{index + 1}</strong>
                <p>{item}</p>
              </article>
            ))}
          </div>
          {verdict.do_not_do && <p className="clear-warning">{verdict.do_not_do}</p>}
        </section>

        <section className="panel span-7 clear-source-panel">
          <PanelHeader title="原始信号" action={sourceRecord?.record_type || "证据"} icon={<Database size={18} />} />
          <h3>{sourceRecord?.title || evidenceLabel}</h3>
          <p>{sourceRecord?.content_excerpt || evidence?.content_zh || "暂无中文摘要。"}</p>
          <div className="clear-source-meta">
            <Metric label="来源" value={sourceRecord?.source || evidence?.source || sources[0] || "--"} />
            <Metric label="采集时间" value={formatDate(sourceRecord?.fetched_at || evidence?.fetched_at)} />
            <Metric label="链接" value={sourceRecord?.url || evidence?.url ? "可打开原始来源" : "--"} />
          </div>
          {sourceRecord?.url || evidence?.url ? (
            <a className="text-link" href={sourceRecord?.url || evidence?.url || "#"} target="_blank" rel="noreferrer">
              查看原始来源 <ExternalLink size={14} />
            </a>
          ) : null}
        </section>

        <section className="panel span-5 clear-audit-panel">
          <PanelHeader title="处理链路" action="审计用" icon={<Activity size={18} />} />
          <p className="muted-copy">这里只展示数据经过哪些步骤，不把它当成已成立的商业机会。</p>
          <div className="clear-audit-list">
            {(pipelineSteps.length ? pipelineSteps : [
              { agent: "SourceConnector", action: "采集原始平台数据", output: "等待更多证据", status: "done" },
              { agent: "OpportunityScoringAgent", action: "生成机会评分", output: `${opportunity.score} 分`, status: "done" }
            ]).map((step, index) => (
              <article key={`${step.agent}-${index}`}>
                <strong>{String(index + 1).padStart(2, "0")}</strong>
                <div>
                  <h3>{step.agent}</h3>
                  <p>{step.action}</p>
                  <small>{step.output}</small>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="page-grid">
      <section className="panel span-12 hero-panel opportunity-hero">
        <button className="ghost" onClick={() => navigate("/workspace/opportunities")}>
          <ArrowLeft size={17} /> 返回机会池
        </button>
        <div>
          <LevelBadge level={opportunity.level} score={opportunity.score} />
          <GateBadge stage={opportunity.opportunity_stage} freshness={opportunity.evidence_freshness} />
          <h2>{opportunityLabel}</h2>
          <p>
            {gateDecision} / {opportunity.playbook_name || opportunity.playbook} / {opportunity.window_hours} 小时窗口 / 创建于 {formatDate(opportunity.created_at)}
          </p>
          {signal && <p>信号：{signal.type} / {signal.circle} / {signal.region} / {signal.crowding}</p>}
        </div>
        <div>
          <button className="secondary" onClick={runDeepAnalysis} disabled={deepLoading}>
            {deepLoading ? "分析中..." : "AI 深入分析"}
          </button>
          <button className="secondary" onClick={saveToBox} disabled={savingBox}>
            <Archive size={16} /> {savingBox ? "保存中..." : "存入机会箱"}
          </button>
          <button
            className="primary"
            onClick={launch}
            disabled={opportunity.execution_gate_passed === false}
            title={opportunity.execution_blockers?.join("；") || "开始执行"}
          >
            开始执行
          </button>
          {execMessage && <p className="story-card">{execMessage}</p>}
        </div>
      </section>

      <section className="panel span-12 action-command-panel">
        <PanelHeader title="行动摘要" action={actionSummary.decision_label || gateDecision} icon={<Target size={18} />} />
        <div className="action-command-lead">
          <article>
            <span>这是什么机会</span>
            <h3>{actionSummary.opportunity || summaryLine}</h3>
            <p>{actionSummary.info_gap || merchantAnalysis?.why_opportunity || "先把信息差转成可以验证的客户问题。"}</p>
          </article>
          <aside>
            <Metric label="投入预算" value={actionSummary.budget || opportunity.estimated_investment} />
            <Metric label="预期回报" value={actionSummary.estimated_return || opportunity.estimated_return} />
            <Metric label="ROI" value={actionSummary.roi || opportunity.roi_ratio} />
            <Metric label="最大亏损" value={actionSummary.max_loss || opportunity.max_loss} />
          </aside>
        </div>
        <div className="action-command-grid">
          <article>
            <span>卖什么</span>
            <p>{actionSummary.what_to_sell || merchantAnalysis?.what_to_sell || "信息服务、工具订阅、服务包或线索清单"}</p>
          </article>
          <article>
            <span>卖给谁</span>
            <p>{actionSummary.who_pays || merchantAnalysis?.who_pays || "有明确痛点或决策需求的目标客户"}</p>
          </article>
          <article>
            <span>为什么现在</span>
            <p>{actionSummary.why_now || `机会分 ${opportunity.score}，验证分 ${opportunity.validation_score}。`}</p>
          </article>
          <article className="action-next">
            <span>下一步</span>
            <p>{actionSummary.first_step || steps[0]}</p>
          </article>
          <article>
            <span>成功标准</span>
            <p>{actionSummary.success_metric || "24-72 小时内拿到真实点击、回复、询价、试用或付费意向"}</p>
          </article>
          <article>
            <span>放弃条件</span>
            <p>{(actionSummary.no_go_signals || riskFactors).slice(0, 3).join("；") || "客户不认痛点或成本风险无法接受"}</p>
          </article>
        </div>
        <div className="action-plan-strip">
          {(actionSummary.action_plan?.length ? actionSummary.action_plan : steps.map<ActionPlanStep>((step, index) => ({ index: index + 1, label: step }))).slice(0, 5).map((step, index) => (
            <article key={`${step.label}-${index}`}>
              <strong>{String(step.index || index + 1).padStart(2, "0")}</strong>
              <span>{step.label}</span>
              {step.deliverable && <small>{step.deliverable}</small>}
            </article>
          ))}
        </div>
      </section>

      <section className="panel span-12 opportunity-explainer">
        <PanelHeader title="这到底是什么机会" action={merchantAnalysis?.plain_type || opportunity.playbook_name || "商业假设"} icon={<Sparkles size={18} />} />
        <div className="opportunity-explainer-lead">
          <h3>{summaryLine}</h3>
          <p>原始信号：{evidenceLabel}</p>
        </div>
        <div className="opportunity-explainer-grid">
          {explainerCards.map((item) => (
            <article key={item.label}>
              <span>{item.label}</span>
              <p>{item.value}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="panel span-12 source-record-panel">
        <PanelHeader title="具体发文内容" action={sourceRecord?.record_type || evidence?.specific_content?.record_type || "原始记录"} icon={<Database size={18} />} />
        <div className="source-record-layout">
          <article className="source-record-main">
            <span className="source-record-kicker">{sourceRecord?.source || evidence?.source || sources[0] || "未知来源"}</span>
            <h3>{sourceRecordTitle}</h3>
            {sourceRecord?.title_original && sourceRecord.title_original !== sourceRecordTitle ? (
              <p className="source-record-original-title">原始标题：{sourceRecord.title_original}</p>
            ) : null}
            <p className="source-record-body">{sourceRecordContent}</p>
            {sourceRecordOriginal && sourceRecordOriginal !== sourceRecordContent ? (
              <p className="source-record-original">原文摘要：{sourceRecordOriginal}</p>
            ) : null}
            {sourceRecord?.url || evidence?.url ? (
              <a className="text-link" href={sourceRecord?.url || evidence?.url || "#"} target="_blank" rel="noreferrer">
                打开原始链接 <ExternalLink size={14} />
              </a>
            ) : null}
          </article>
          <aside className="source-record-side">
            <Metric label="记录类型" value={sourceRecord?.record_type || evidence?.specific_content?.record_type || "--"} />
            <Metric label="平台/来源" value={sourceRecord?.source || evidence?.source || "--"} />
            <Metric label="作者/主体" value={firstValue(sourceRecord?.author, sourceRecord?.platform_id)} />
            <Metric label="发布时间" value={formatDate(sourceRecord?.published_at || evidence?.published_at)} />
            <Metric label="采集时间" value={formatDate(sourceRecord?.fetched_at || evidence?.fetched_at)} />
            <Metric label="可做模式" value={sourceRecord?.business_model || evidence?.analysis_summary?.business_model || "--"} />
          </aside>
        </div>
        <div className="source-record-interpretation">
          <article>
            <h3>这条内容本身在说什么</h3>
            <p>{sourceRecord?.signal_fact || evidence?.analysis_summary?.source_fact || evidence?.analysis_summary?.platform_signal || "系统从原始平台采集到这条记录，并把它作为机会判断的基础证据。"}</p>
          </article>
          <article>
            <h3>系统怎么把它变成机会</h3>
            <p>{sourceRecord?.system_interpretation || evidence?.analysis_summary?.system_interpretation || evidence?.analysis_summary?.business_interpretation || "系统将原始内容映射到可执行打法，再结合分数、风险和验证窗口生成机会。"}</p>
          </article>
        </div>
        {sourceRecordMetrics.length ? (
          <div className="source-record-metrics">
            {sourceRecordMetrics.map(([key, value]) => (
              <span key={key}>
                <strong>{uiLabel(key)}</strong>
                {Array.isArray(value) ? value.join("、") : String(value)}
              </span>
            ))}
          </div>
        ) : null}
      </section>

      {deepAnalysis ? (
        <section className="panel span-12 deep-analysis-panel">
          <PanelHeader title="AI 深入分析报告" action={deepAnalysis.generated_by || "DeepOpportunityAnalyst"} icon={<Sparkles size={18} />} />
          <div className="deep-analysis-head">
            <article>
              <span>分析结论</span>
              <h3>{deepAnalysis.headline || "已生成深度机会分析。"}</h3>
              <p>{deepAnalysis.decision?.reason || "系统已综合原始内容、评分、风险和验证路径生成判断。"}</p>
            </article>
            <article>
              <span>建议动作</span>
              <h3>{deepAnalysis.decision?.recommendation || "小成本验证"}</h3>
              <p>{deepAnalysis.decision?.next_action || "先做小样本客户验证，不要直接重投入。"}</p>
              <small>置信度：{deepAnalysis.decision?.confidence || "--"}</small>
            </article>
          </div>
          <div className="deep-definition-grid">
            <article>
              <span>机会定义</span>
              <p>{deepAnalysis.opportunity_definition?.what_it_is || merchantAnalysis?.what_it_is || "--"}</p>
            </article>
            <article>
              <span>产品/服务</span>
              <p>{deepAnalysis.opportunity_definition?.what_to_sell || merchantAnalysis?.what_to_sell || "--"}</p>
            </article>
            <article>
              <span>付费客户</span>
              <p>{deepAnalysis.opportunity_definition?.who_pays || merchantAnalysis?.who_pays || "--"}</p>
            </article>
            <article>
              <span>付费理由</span>
              <p>{deepAnalysis.opportunity_definition?.why_they_pay || merchantAnalysis?.why_they_pay || "--"}</p>
            </article>
          </div>
          <div className="deep-analysis-grid">
            <article>
              <h3>目标客户</h3>
              {(deepAnalysis.customer_segments || []).map((item, index) => (
                <p key={`segment-${index}`}>
                  <strong>{deepField(item, "segment")}</strong>
                  {deepField(item, "pain")} / 触达：{deepField(item, "how_to_reach")}
                </p>
              ))}
            </article>
            <article>
              <h3>可卖方案</h3>
              {(deepAnalysis.offer_map || []).map((item, index) => (
                <p key={`offer-${index}`}>
                  <strong>{deepField(item, "offer")}</strong>
                  {deepField(item, "price_test")}；证据：{deepField(item, "proof_needed")}
                </p>
              ))}
            </article>
            <article>
              <h3>为什么现在</h3>
              {(deepAnalysis.why_now || []).map((item) => <p key={item}>{item}</p>)}
            </article>
            <article>
              <h3>验证计划</h3>
              {(deepAnalysis.validation_plan || []).map((item, index) => (
                <p key={`plan-${index}`}>
                  <strong>{deepField(item, "phase")}</strong>
                  {deepField(item, "action")} / 成功标准：{deepField(item, "success_metric")}
                </p>
              ))}
            </article>
            <article>
              <h3>风险复盘</h3>
              {(deepAnalysis.risk_review || []).map((item, index) => (
                <p key={`risk-${index}`}>
                  <strong>{deepField(item, "risk")}</strong>
                  {deepField(item, "mitigation")}
                </p>
              ))}
            </article>
            <article>
              <h3>缺口与获客</h3>
              {(deepAnalysis.data_gaps || []).map((item) => <p key={item}>{item}</p>)}
              {(deepAnalysis.go_to_market || []).slice(0, 3).map((item) => <p key={item}>{item}</p>)}
            </article>
          </div>
          {deepAnalysis.scorecard ? (
            <div className="deep-score-row">
              {Object.entries(deepAnalysis.scorecard).map(([key, value]) => (
                <Metric key={key} label={uiLabel(key)} value={`${value}/100`} />
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="panel span-12 decision-strip">
        <Metric label="商业判断" value={gateDecision} />
        <Metric label="证据状态" value={`${uiLabel(opportunity.evidence_freshness || "unknown")} / ${effectiveEvidenceCount} 源`} />
        <Metric label="所需资金" value={firstValue(roi?.estimated_investment, opportunity.estimated_investment)} />
        <Metric label="30 天回报" value={firstValue(roi?.estimated_return, opportunity.estimated_return)} />
        <Metric label="投资回报率" value={firstValue(roi?.roi_ratio, opportunity.roi_ratio)} />
        <Metric label="回本点" value={firstValue(roi?.breakeven, opportunity.breakeven)} />
      </section>

      {opportunity.execution_blockers?.length ? (
        <section className="panel span-12 gate-panel">
          <PanelHeader title="执行门槛" action={uiLabel(opportunity.opportunity_stage || "watch")} icon={<ShieldCheck size={18} />} />
          <div className="gate-grid">
            {opportunity.execution_blockers.map((item) => <p className="gate-blocker" key={item}>{item}</p>)}
            {(opportunity.execution_reasons || []).map((item) => <p className="gate-reason" key={item}>{item}</p>)}
          </div>
        </section>
      ) : null}

      <section className="panel span-12 decision-strip">
        <Metric label="最大亏损" value={firstValue(roi?.max_loss, opportunity.max_loss)} />
        <Metric label="最后采集" value={formatDate(opportunity.evidence_last_checked)} />
        <Metric label="证据年龄" value={opportunity.evidence_age_hours == null ? "--" : `${opportunity.evidence_age_hours}h`} />
        <Metric label="来源数量" value={String(effectiveEvidenceCount)} />
        <Metric label="执行状态" value={uiLabel(opportunity.execution_status)} />
        <Metric label="风险等级" value={uiLabel(opportunity.risk_level)} />
      </section>

      <section className="panel span-12 evidence-hero">
        <PanelHeader title="这条机会从哪来" action={evidence?.source || sources[0] || "未知平台"} icon={<Database size={18} />} />
        <div className="evidence-source-grid">
          <div className="evidence-main">
            <h3>{evidence?.title_zh || signal?.title || opportunity.playbook_name}</h3>
            {evidence?.title_original && evidence.title_original !== evidence.title_zh && (
              <p>原始标题：{evidence.title_original}</p>
            )}
            <p>{evidence?.analysis_summary?.platform_signal || "系统从真实数据源采集到该信号，并进入清洗、去重、评分流程。"}</p>
            <p>{evidence?.analysis_summary?.business_interpretation || `最终生成「${opportunity.playbook_name}」机会。`}</p>
            {evidence?.url && (
              <a className="text-link" href={evidence.url} target="_blank" rel="noreferrer">
                查看原始来源 <ExternalLink size={14} />
              </a>
            )}
          </div>
          <div className="evidence-side">
            <Metric label="来源平台" value={evidence?.source || sources[0] || "--"} />
            <Metric label="所属圈层" value={evidence?.circle || signal?.circle || "--"} />
            <Metric label="平台区域" value={evidence?.region || signal?.region || "--"} />
            <Metric label="采集时间" value={formatDate(evidence?.fetched_at)} />
          </div>
        </div>
      </section>

      <section className="panel span-7">
        <PanelHeader title="为什么说它热门" action={`${hotReasons.length} 条判断`} icon={<Flame size={18} />} />
        <div className="merchant-list compact-list">
          {(hotReasons.length ? hotReasons : ["暂无足够热度解释，需要继续观察更多平台数据。"]).map((item) => (
            <p key={item}>{item}</p>
          ))}
        </div>
      </section>

      <section className="panel span-5">
        <PanelHeader title="平台指标" action="原始数据摘要" icon={<BarChart3 size={18} />} />
        <div className="metric-list">
          {visibleMetrics.map(([key, value]) => (
            <Metric key={key} label={uiLabel(key)} value={Array.isArray(value) ? value.join("、") : String(value)} />
          ))}
          {!visibleMetrics.length && <p className="muted-copy">该来源没有返回可展示的数值指标。</p>}
        </div>
      </section>

      <section className="panel span-12 merchant-analysis-panel">
        <PanelHeader title="商业解读" action={merchantAnalysis?.plain_type || "商人行动卡"} icon={<Sparkles size={18} />} />
        <div className="agent-contract-card">
          <article>
            <span>智能体设定</span>
            <h3>{agentConfig?.name || "MerchantOpportunityAgent"}</h3>
            <p>{agentConfig?.role || "把信号拆成客户、交付物、报价、触达话术和放弃阈值。"}</p>
          </article>
          <article>
            <span>输入</span>
            {(agentConfig?.inputs || [`来源：${evidence?.source || sources[0] || "数据源"}`, `机会分 ${opportunity.score}，验证分 ${opportunity.validation_score}`]).map((item) => (
              <p key={item}>{item}</p>
            ))}
          </article>
          <article>
            <span>输出契约</span>
            <div className="compact-chip-row">
              {(agentConfig?.output_contract || ["先卖什么", "卖给谁", "交付物", "测试价", "触达话术", "放弃阈值"]).map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          </article>
        </div>
        {executionBrief && (
          <div className="merchant-action-card">
            <div>
              <span>现在能干嘛</span>
              <h3>{executionBrief.sell}</h3>
              <p>{executionBrief.buyer}</p>
            </div>
            <div className="merchant-action-grid">
              <article>
                <strong>交付物</strong>
                <p>{executionBrief.deliverable}</p>
              </article>
              <article>
                <strong>测试价</strong>
                <p>{executionBrief.price_test}</p>
              </article>
              <article>
                <strong>第一批去哪找</strong>
                <p>{executionBrief.first_channel}</p>
              </article>
              <article>
                <strong>成功/停止阈值</strong>
                <p>{executionBrief.success_threshold}</p>
                <p>{executionBrief.stop_threshold}</p>
              </article>
            </div>
            <article className="merchant-script-box">
              <strong>第一条触达话术</strong>
              <p>{executionBrief.first_message}</p>
            </article>
          </div>
        )}
        <div className="analysis-brief">
          <article>
            <h3>这是什么</h3>
            <p>{merchantAnalysis?.what_it_is || actionSummary.opportunity || `这是一条来自 ${evidence?.source || sources[0] || "数据源"} 的商业信号，系统把它转成了可验证机会。`}</p>
          </article>
          <article>
            <h3>为什么有机会</h3>
            <p>{merchantAnalysis?.why_opportunity || actionSummary.info_gap || evidence?.analysis_summary?.business_interpretation || "这条信号显示某个需求、风险或注意力正在变化，适合先做小成本验证。"}</p>
          </article>
          <article>
            <h3>我的判断</h3>
            <p>{merchantAnalysis?.merchant_take || `我的判断：这条机会当前 ${opportunity.score} 分、验证分 ${opportunity.validation_score}，先按「${actionSummary.first_step || steps[0]}」做小样本验证，再根据真实点击、回复、询价或试用意向决定是否继续。`}</p>
          </article>
        </div>
        <div className="analysis-grid">
          <article>
            <h3>为什么是现在</h3>
            {commercialWhyNow.map((item) => (
              <p key={item}>{item}</p>
            ))}
          </article>
          <article>
            <h3>第一批客户</h3>
            {customerScenarios.length ? customerScenarios.map((item, index) => (
              <p key={`${item.segment}-${index}`}>
                <strong>{item.segment || `客户 ${index + 1}`}</strong>
                {item.pain || "痛点待验证"} / 用法：{item.use_case || "用途待验证"} / 去哪找：{item.where_to_find || "渠道待验证"}
              </p>
            )) : commercialCustomers.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </article>
          <article>
            <h3>怎么赚钱</h3>
            {offerPackages.length ? offerPackages.map((item, index) => (
              <p key={`${item.name}-${index}`}>
                <strong>{item.name || `报价包 ${index + 1}`}</strong>
                {item.price || "价格待测"} / {item.deliverable || "交付物待定"} / 成交信号：{item.buy_trigger || "客户愿意继续沟通"}
              </p>
            )) : commercialAngles.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </article>
          <article>
            <h3>72 小时怎么验证</h3>
            {merchantNextActions.length ? merchantNextActions.map((item, index) => (
              <p key={`${item.step}-${index}`}>
                <strong>{index + 1}</strong>
                {item.step}：{item.output} / 完成标准：{item.done_when}
              </p>
            )) : commercialValidation.map((item, index) => (
              <p key={item}><strong>{index + 1}</strong>{item}</p>
            ))}
          </article>
          <article>
            <h3>什么情况放弃</h3>
            {commercialNoGo.map((item) => (
              <p key={item}>{item}</p>
            ))}
          </article>
          <article>
            <h3>原始语境</h3>
            <p>{commercialSourceContext}</p>
          </article>
        </div>
      </section>

      <section className="panel span-12">
        <PanelHeader title="谁处理了这条数据" action="Agent 处理链路" icon={<Activity size={18} />} />
        <div className="agent-timeline">
          {(pipelineSteps.length ? pipelineSteps : [
            { agent: "SourceConnector", action: "采集原始平台数据", output: "等待更多证据", status: "done" },
            { agent: "OpportunityScoringAgent", action: "生成机会评分", output: `${opportunity.score} 分`, status: "done" }
          ]).map((step, index) => (
            <article className="agent-step" key={`${step.agent}-${index}`}>
              <strong>{String(index + 1).padStart(2, "0")}</strong>
              <div>
                <h3>{step.agent}</h3>
                <p>{step.action}</p>
                <small>{step.output}</small>
              </div>
              <span>{uiLabel(step.status)}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="panel span-5 chart-panel">
        <PanelHeader title="商人评分卡" action={String(dimensions.agent || dimensions.merged_by || "机会评分 Agent")} icon={<Radar size={18} />} />
        <RadarChartBlock data={chartData} />
      </section>
      <section className="panel span-7">
        <PanelHeader title="为什么值得看" action={`${evidenceCount} 条证据`} icon={<ShieldCheck size={18} />} />
        <div className="merchant-brief">
          {(rationale.length ? rationale : ["系统已基于真实信号对需求、动量、供给、执行和风险完成评分。"]).map((item) => (
            <p key={item}>{item}</p>
          ))}
        </div>
        <div className="score-bars">
          <ScoreBar label="需求" value={dimensionPercent(dimensions, "demand", 0.5)} note="是否有人愿意付钱或持续使用" />
          <ScoreBar label="动量" value={dimensionPercent(dimensions, "momentum", 0.5)} note="热度是否正在上升" />
          <ScoreBar label="供给" value={dimensionPercent(dimensions, "supply", 0.5)} note="可复用资产、开源或供给是否清晰" />
          <ScoreBar label="竞争" value={dimensionPercent(dimensions, "competition_adjusted", 0.5)} note="竞争压力越低分越高" />
          <ScoreBar label="执行" value={dimensionPercent(dimensions, "execution", 0.5)} note="用现有资源能否快速做出最小可行产品" />
          <ScoreBar label="风险缓冲" value={dimensionPercent(dimensions, "risk_adjusted", 0.5)} note="政策、平台、噪声和亏损缓冲" />
        </div>
      </section>

      <section className="panel span-6">
        <PanelHeader title="风险与反方场景" action={risk?.recommendation || uiLabel(opportunity.risk_level) || "实时"} icon={<Check size={18} />} />
        <div className="risk-grid">
          <RiskItem title="拥挤度分数" value={`当前 ${risk?.crowding_score ?? opportunity.crowding_score}/100`} />
          <RiskItem title="风险等级" value={uiLabel(risk?.risk_level || opportunity.risk_level)} />
          <RiskItem title="验证分" value={String(validation?.validation_score || opportunity.validation_score)} />
          <RiskItem title="资金系数" value={String(roi?.capital_factor ?? "--")} />
        </div>
        <div className="merchant-list">
          <h3>风险因子</h3>
          {(riskFactors.length ? riskFactors : ["需要继续验证真实付费意愿和可执行路径"]).map((item) => (
            <p key={item}>{item}</p>
          ))}
          <h3>反方场景</h3>
          <p>{risk?.bear_case || validation?.validation?.bear_case || opportunity.bear_case || "暂无反方场景，建议先小额验证。"}</p>
        </div>
      </section>

      <section className="panel span-6">
        <PanelHeader title="验证与回报" action={oci?.recommendation || "投入估算"} icon={<CircleDollarSign size={18} />} />
        <div className="roi-grid">
          <Metric label="预计投入" value={roi?.estimated_investment || opportunity.estimated_investment} />
          <Metric label="预计回报" value={roi?.estimated_return || opportunity.estimated_return} />
          <Metric label="投资回报率" value={roi?.roi_ratio || opportunity.roi_ratio} />
          <Metric label="证据数" value={String(effectiveEvidenceCount)} />
          <Metric label="机会指数" value={String(oci?.oci_score ?? "--")} />
          <Metric label="建议" value={oci?.recommendation || "--"} />
        </div>
        <div className="source-pills">
          {(sources.length ? sources : signal?.sources || []).map((source) => <span key={source}>{source}</span>)}
          {!sources.length && !signal?.sources?.length && <span>暂无来源</span>}
        </div>
      </section>

      <section className="panel span-12">
        <PanelHeader title="执行路径" action={uiLabel(opportunity.execution_status || "not_started")} icon={<ListChecks size={18} />} />
        <div className="steps merchant-steps">
          {steps.map((step, index) => (
            <article className={`step ${index < currentStep ? "done" : ""}`} key={`${index}-${step}`}>
              <strong>{String(index + 1).padStart(2, "0")}</strong>
              <span>{step}</span>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function ScoreBar({ label, value, note }: { label: string; value: number; note: string }) {
  return (
    <article className="score-bar">
      <div>
        <strong>{label}</strong>
        <span>{value}/100</span>
      </div>
      <div className="progress">
        <span style={{ width: `${value}%` }} />
      </div>
      <p>{note}</p>
    </article>
  );
}

function ActionsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<ActionItem[]>([]);
  const [filter, setFilter] = useState<"all" | "in_progress" | "completed" | "pending">("all");
  const [note, setNote] = useState("");
  const [processingId, setProcessingId] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const query = filter === "all" ? "" : `?status=${filter}`;
      const data = await apiGet<ListResponse<ActionItem>>(`/actions${query}`);
      setItems(data.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "执行项加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const timer = window.setInterval(() => {
      if (!loading) {
        load();
      }
    }, 15000);
    return () => window.clearInterval(timer);
  }, [filter]);

  const advance = async (item: ActionItem) => {
    setProcessingId(item.id);
    try {
      const nextStep = Math.min((item.total_steps || 1), item.current_step + 1);
      await apiPut<{ status: string }>(`/actions/${item.id}/progress`, {
        current_step: nextStep,
        note: note || "手动更新"
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "进度更新失败");
    } finally {
      setProcessingId(null);
    }
  };

  const complete = async (item: ActionItem) => {
    setProcessingId(item.id);
    try {
      await apiPost<{ status: string }>(`/actions/${item.id}/review`, {
        result: "profit",
        rating: 5,
        amount: 0,
        notes: note || "在界面中关闭"
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "复盘提交失败");
    } finally {
      setProcessingId(null);
    }
  };

  const grouped = useMemo(() => {
    const map: Record<string, ActionItem[]> = {
      in_progress: [],
      completed: [],
      pending: []
    };
    for (const row of items) {
      const key = (row.status as keyof typeof map) in map ? row.status : "pending";
      map[key].push(row);
    }
    return map;
  }, [items]);

  return (
    <div className="page-grid">
      <section className="panel span-12">
        <div className="toolbar">
          <Segmented values={["all", "in_progress", "completed", "pending"]} active={filter} setActive={setFilter as (value: string) => void} />
          <div className="toolbar-right">
            <input
              className="select-button"
              placeholder="进度备注"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
            <button className="secondary" data-testid="action-refresh" onClick={load}>
              <RefreshCw size={16} /> 刷新
            </button>
          </div>
        </div>
        {error && <p style={{ color: "#fecaca" }}>{error}</p>}
        <div className="kanban">
          {(["in_progress", "completed", "pending"] as const).map((status) => (
            <section className="panel kanban-column" key={status}>
              <PanelHeader title={uiLabel(status)} action={`${grouped[status].length} 项`} icon={<ListChecks size={18} />} />
              {grouped[status].map((action) => {
                const summary = action.action_summary || fallbackActionSummary(action.opportunity_title || action.opportunity_id, action.current_step_label);
                const progressPct = Math.min(100, (action.current_step / Math.max(1, action.total_steps)) * 100);
                return (
                  <article className="action-card action-flow-card" key={action.id}>
                    <div className="action-flow-head">
                      <div>
                        <span className="eyebrow">{uiLabel(action.playbook)} / {uiLabel(action.status)}</span>
                        <h3>{action.opportunity_title || `机会 ${action.opportunity_id}`}</h3>
                        <p>{summary.info_gap || summary.opportunity}</p>
                      </div>
                      <strong>{action.current_step}/{action.total_steps}</strong>
                    </div>
                    <div className="current-task-box">
                      <span>当前任务</span>
                      <h3>{action.current_step_label || summary.first_step || "推进当前验证步骤"}</h3>
                      <p>交付物：{summary.action_plan?.[Math.max(0, action.current_step - 1)]?.deliverable || summary.what_to_sell || "验证记录与客户反馈"}</p>
                      <p>成功标准：{action.success_metric || summary.success_metric || "拿到真实互动或付费意向"}</p>
                    </div>
                    <div className="next-step-row">
                      <span>下一步：{action.next_step_label || "复盘本步结果"}</span>
                      <span>预算：{summary.budget || "小额验证"}</span>
                      <span>ROI：{summary.roi || "待验证"}</span>
                    </div>
                    {summary.blockers?.length ? (
                      <div className="action-checklist">
                        <h3>阻塞原因</h3>
                        {summary.blockers.slice(0, 2).map((item) => <p key={item}>{item}</p>)}
                      </div>
                    ) : null}
                    <Metric label="热度（开始/当前）" value={`${action.signal_heat_at_start}/${action.signal_heat_current}`} />
                    <div className="progress">
                      <span style={{ width: `${progressPct}%` }} />
                    </div>
                    <div className="feedback compact">
                      <button
                        className="secondary small"
                        disabled={processingId === action.id}
                        onClick={() => navigate(`/workspace/strategy/${action.opportunity_id}`)}
                      >
                        详情
                      </button>
                      <button
                        className="secondary small"
                        data-testid={`action-next-step-${action.id}`}
                        disabled={processingId === action.id || action.status === "completed"}
                        onClick={() => advance(action)}
                      >
                        {processingId === action.id ? "更新中..." : "下一步"}
                      </button>
                      <button
                        className="primary small"
                        data-testid={`action-complete-${action.id}`}
                        disabled={processingId === action.id || action.status === "completed"}
                        onClick={() => complete(action)}
                      >
                        复盘完成
                      </button>
                    </div>
                  </article>
                );
              })}
            </section>
          ))}
          {loading && <p style={{ marginTop: "12px" }}>加载中...</p>}
        </div>
      </section>
    </div>
  );
}

function BriefPage() {
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [savingBoxId, setSavingBoxId] = useState<string | null>(null);
  const [latest, setLatest] = useState<Brief | null>(null);
  const [history, setHistory] = useState<Brief[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [latestData, historyData] = await Promise.all([
        apiGet<Brief | null>("/brief/latest"),
        apiGet<ListResponse<Brief>>("/brief/history?days=30")
      ]);
      setLatest(latestData && latestData.id ? latestData : null);
      setHistory(historyData.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "简报加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const generated = await apiPost<Brief>("/brief/generate");
      setLatest(generated);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成简报失败");
    } finally {
      setGenerating(false);
    }
  };

  const saveToBox = async (item: BriefOpportunity) => {
    setSavingBoxId(item.id);
    setError(null);
    try {
      await apiPost<OpportunityBoxItem>("/opportunity-box", {
        opportunity_id: item.id,
        source_type: "daily",
        title: item.title,
        source: item.source,
        score: item.score,
        risk_level: item.risk_level,
        rationale: item.hot_reasons || [],
        prediction: { action_summary: item.action_summary },
        notes: `来自每日简报 ${latest?.date_key || ""}`
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "存入机会箱失败");
    } finally {
      setSavingBoxId(null);
    }
  };

  const payload = latest?.payload || {};
  const metrics = payload.metrics || {};
  const conclusion = payload.today_conclusion || {};
  const topOpportunities = payload.top_opportunities || [];
  const sourceStatus = payload.source_status || {};
  const signalCategories = payload.signal_categories || [];
  const todos = payload.todo || [];
  const risks = payload.risks || [];
  const successSources = sourceStatus.success || [];
  const failedSources = sourceStatus.failed || [];
  const configSources = sourceStatus.needs_config || [];
  const noNewSources = sourceStatus.no_new || [];

  return (
    <div className="page-grid brief-page">
      <section className="panel span-12 brief-hero">
        <div className="toolbar">
          <PanelHeader title="每日简报" action="最新与归档" icon={<BookOpen size={18} />} />
          <div className="toolbar-right">
            <button className="secondary" data-testid="brief-generate-new" onClick={generate} disabled={generating}>
              <RefreshCw size={16} /> {generating ? "生成中..." : "生成新简报"}
            </button>
          </div>
        </div>
        {error && <p style={{ color: "#fecaca" }}>{error}</p>}
        {loading ? (
          <p>简报加载中...</p>
        ) : latest ? (
          <>
            <div className="brief-title-row">
              <div>
                <span className="eyebrow">{payload.generated_by || "DailyBriefAgent"} / {latest.date_key}</span>
                <h2>{conclusion.headline || latest.summary || latest.title}</h2>
                <p>{conclusion.recommended_action || "先看机会，再看风险和数据源状态。"}</p>
              </div>
              <div className="brief-main-action">
                <strong>{metrics.actionable_count || 0}</strong>
                <span>可优先执行</span>
              </div>
            </div>
            <div className="brief-kpis">
              <Metric label="24h 信号" value={`${metrics.signal_count ?? payload.signals?.length ?? 0}`} />
              <Metric label="24h 机会" value={`${metrics.opportunity_count ?? payload.opportunities?.length ?? 0}`} />
              <Metric label="信号变化" value={metricDelta(metrics.signal_delta)} />
              <Metric label="异常来源" value={`${metrics.source_failed_count ?? failedSources.length}`} />
            </div>
            <div className="brief-conclusion-list">
              {(conclusion.bullets || [latest.summary || "暂无摘要。"]).map((item) => (
                <p key={item}>{item}</p>
              ))}
            </div>
          </>
        ) : (
          <div className="brief-empty">
            <Sparkles size={22} />
            <h3>暂无最新简报</h3>
            <p>点击“生成新简报”，系统会把最近 24 小时的信号、机会、数据源状态和待办整理成行动版日报。</p>
          </div>
        )}
      </section>

      {latest && (
        <>
          <section className="panel span-8">
            <PanelHeader title="Top 机会" action={`${topOpportunities.length} 个候选`} icon={<Target size={18} />} />
            <div className="brief-opportunity-list">
              {topOpportunities.map((item) => {
                const summary = item.action_summary || fallbackActionSummary(item.title, item.suggested_action, item.source);
                return (
                  <article className="brief-opportunity" key={item.id}>
                    <div className="brief-rank">#{item.rank}</div>
                    <div>
                      <div className="brief-card-title">
                        <button className="text-link" onClick={() => navigate(`/workspace/strategy/${item.id}`)}>
                          {item.title}
                        </button>
                        <LevelBadge level={item.level} score={item.score} />
                      </div>
                      <p>{summary.opportunity || `${item.playbook_name} / ${item.source} / ${item.window_hours} 小时窗口`}</p>
                      <div className="tags">
                        <span className="badge">{summary.decision_label || item.decision}</span>
                        <span className="badge">验证分 {item.validation_score}</span>
                        <span className="badge">风险 {uiLabel(summary.risk_level || item.risk_level)}</span>
                        <span className="badge">{summary.budget || item.estimated_investment || "小额验证"}</span>
                      </div>
                      <div className="brief-action-box">
                        <span>信息差</span>
                        <p>{summary.info_gap}</p>
                        <strong>下一步：{summary.first_step || item.suggested_action}</strong>
                      </div>
                      <div className="brief-reasons">
                        {firstItems(summary.no_go_signals?.length ? summary.no_go_signals : item.hot_reasons, 3).map((reason) => (
                          <span key={reason}>{reason}</span>
                        ))}
                      </div>
                      <div className="feedback compact" style={{ marginTop: 10 }}>
                        <button className="secondary small" onClick={() => saveToBox(item)} disabled={savingBoxId === item.id}>
                          <Archive size={14} /> {savingBoxId === item.id ? "保存中..." : "存入机会箱"}
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
              {!topOpportunities.length && <p className="muted-copy">今日暂无可展示机会，建议先运行采集管线。</p>}
            </div>
          </section>

          <section className="panel span-4">
            <PanelHeader title="今日待办" action={`${todos.length} 项`} icon={<ListChecks size={18} />} />
            <div className="brief-todo-list">
              {todos.map((todo, index) => (
                <article className="brief-todo" key={`${todo.title}-${index}`}>
                  <strong>{String(index + 1).padStart(2, "0")}</strong>
                  <div>
                    <h3>{todo.title}</h3>
                    <p>{todo.where}</p>
                    <small>预算：{todo.budget}</small>
                    <small>成功：{todo.success_metric}</small>
                    <small>失败：{todo.fail_metric}</small>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="panel span-7">
            <PanelHeader title="数据源状态" action={`${successSources.length} 成功 / ${failedSources.length} 异常`} icon={<Database size={18} />} />
            <div className="brief-source-grid">
              <BriefSourceBucket title="有新增" items={successSources} tone="good" />
              <BriefSourceBucket title="异常" items={failedSources} tone="bad" />
              <BriefSourceBucket title="待配置" items={configSources} tone="warn" />
              <BriefSourceBucket title="无新增" items={noNewSources} tone="quiet" />
            </div>
          </section>

          <section className="panel span-5">
            <PanelHeader title="风险提醒" action={`${risks.length} 条`} icon={<ShieldCheck size={18} />} />
            <div className="brief-risk-list">
              {risks.map((risk) => (
                <p key={risk}>{risk}</p>
              ))}
            </div>
          </section>

          <section className="panel span-7">
            <PanelHeader title="新增信号摘要" action={`${signalCategories.length} 类`} icon={<Flame size={18} />} />
            <div className="brief-category-grid">
              {signalCategories.map((category) => (
                <article className="brief-category" key={category.category}>
                  <div>
                    <h3>{category.category}</h3>
                    <span>{category.count} 条</span>
                  </div>
                  {firstItems(category.items, 4).map((item) => (
                    <p key={item.id}>
                      <strong>{item.source}</strong>
                      {item.title}
                    </p>
                  ))}
                </article>
              ))}
              {!signalCategories.length && <p className="muted-copy">最近 24 小时暂无新增信号。</p>}
            </div>
          </section>

          <section className="panel span-5">
            <PanelHeader title="市场动态" action={`${payload.market_events?.length || 0} 条`} icon={<TrendingUp size={18} />} />
            <div className="brief-market-list">
              {(payload.market_events || []).map((event, index) => (
                <article key={`${String(event.id || index)}`}>
                  <strong>{String(event.institution || event.event_type || "机构事件")}</strong>
                  <p>{String(event.description || event.target || "暂无描述")}</p>
                </article>
              ))}
              {!payload.market_events?.length && <p className="muted-copy">暂无 SEC、36Kr、TechCrunch 相关机构动态。</p>}
            </div>
          </section>
        </>
      )}

      <section className="panel span-12 brief-history">
        <PanelHeader title="简报历史（30 天）" action={`${history.length} 条`} icon={<Download size={18} />} />
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>日期</th>
                <th>标题</th>
                <th>摘要</th>
              </tr>
            </thead>
            <tbody>
              {history.map((item) => (
                <tr key={item.id}>
                  <td>{item.date_key}</td>
                  <td>{item.title}</td>
                  <td>
                    <strong>{item.summary}</strong>
                    <small>
                      信号 {item.payload?.metrics?.signal_count ?? item.payload?.signals?.length ?? 0} / 机会 {item.payload?.metrics?.opportunity_count ?? item.payload?.opportunities?.length ?? 0}
                    </small>
                  </td>
                </tr>
              ))}
              {!history.length && (
                <tr>
                  <td colSpan={3}>暂无历史简报。</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function OpportunityBoxPage() {
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [boxItems, setBoxItems] = useState<OpportunityBoxItem[]>([]);
  const [predictions, setPredictions] = useState<PredictedOpportunity[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [boxResp, predictionResp] = await Promise.all([
        apiGet<ListResponse<OpportunityBoxItem>>("/opportunity-box"),
        apiGet<ListResponse<PredictedOpportunity> & { hours: number }>("/opportunity-box/predictions?hours=72&limit=8")
      ]);
      setBoxItems(boxResp.items || []);
      setPredictions(predictionResp.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "机会箱加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const savePrediction = async (item: PredictedOpportunity) => {
    setSavingId(item.id);
    setMessage(null);
    setError(null);
    try {
      await apiPost<OpportunityBoxItem>("/opportunity-box", {
        source_type: "predicted",
        title: item.title,
        source: item.source,
        score: item.score,
        risk_level: item.risk_level,
        rationale: item.rationale,
        prediction: {
          ...item.prediction,
          id: item.id,
          prediction_id: item.id,
          action_summary: actionSummaryFromPrediction(item.prediction) || fallbackActionSummary(item.title, item.suggested_action, item.source)
        },
        notes: `预测窗口 ${item.horizon_days} 天，置信度 ${item.confidence}`
      });
      setMessage("预测机会已存入机会箱。");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存预测机会失败");
    } finally {
      setSavingId(null);
    }
  };

  const removeBoxItem = async (item: OpportunityBoxItem) => {
    setSavingId(item.id);
    setMessage(null);
    setError(null);
    try {
      await apiDelete<{ deleted: string }>(`/opportunity-box/${item.id}`);
      setMessage("已从机会箱移除。");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "移除失败");
    } finally {
      setSavingId(null);
    }
  };

  const dailyCount = boxItems.filter((item) => item.source_type === "daily").length;
  const predictedCount = boxItems.filter((item) => item.source_type === "predicted").length;

  return (
    <div className="page-grid opportunity-box-page">
      <section className="panel span-12">
        <div className="toolbar">
          <PanelHeader title="机会箱" action="收藏、跟踪与预测" icon={<Archive size={18} />} />
          <button className="secondary" onClick={load} disabled={loading}>
            <RefreshCw size={16} /> {loading ? "刷新中..." : "刷新"}
          </button>
        </div>
        {error && <p style={{ color: "#fca5a5" }}>{error}</p>}
        {message && <div className="story-card">{message}</div>}
        <div className="summary-grid" style={{ marginTop: 12 }}>
          <Metric label="已存机会" value={String(boxItems.length)} />
          <Metric label="来自日报" value={String(dailyCount)} />
          <Metric label="预测机会" value={String(predictedCount)} />
        </div>
      </section>

      <section className="panel span-7">
        <PanelHeader title="我的机会箱" action={`${boxItems.length} 个跟踪项`} icon={<Archive size={18} />} />
        <div className="box-grid">
          {boxItems.map((item) => {
            const summary = actionSummaryFromPrediction(item.prediction) || fallbackActionSummary(item.title, item.notes || undefined, item.source);
            const stage = item.status === "completed" ? "completed" : summary.execution_stage || (item.opportunity_id ? "needs_validation" : "watch");
            return (
              <article className="box-card" key={item.id}>
                <div className="box-card-head">
                  <div>
                    <h3>{item.title}</h3>
                    <p>{uiLabel(item.source_type)} / {item.source} / {formatDate(item.created_at)}</p>
                  </div>
                  <LevelBadge level={item.score >= 88 ? "S" : item.score >= 76 ? "A" : "B"} score={item.score || 0} />
                </div>
                <div className="box-stage-row">
                  {["候选", "验证", "执行", "复盘"].map((label, index) => (
                    <span className={index <= (stage === "completed" ? 3 : stage === "executable" ? 2 : stage === "needs_validation" ? 1 : 0) ? "active" : ""} key={label}>
                      {label}
                    </span>
                  ))}
                </div>
                <div className="box-action-summary">
                  <span>{summary.decision_label || uiLabel(stage)}</span>
                  <p>{summary.opportunity}</p>
                  <strong>下一步：{summary.first_step}</strong>
                </div>
                <div className="tags">
                  <span className="badge">状态 {uiLabel(item.status)}</span>
                  <span className="badge">风险 {uiLabel(summary.risk_level || item.risk_level)}</span>
                  <span className="badge">预算 {summary.budget || "小额验证"}</span>
                </div>
                <div className="brief-reasons">
                  {firstItems(summary.no_go_signals?.length ? summary.no_go_signals : item.rationale || [], 3).map((reason) => (
                    <span key={reason}>{reason}</span>
                  ))}
                </div>
                {item.notes && <p>{item.notes}</p>}
                <div className="feedback compact">
                  {item.opportunity_id && (
                    <button className="secondary small" onClick={() => navigate(`/workspace/strategy/${item.opportunity_id}`)}>
                      详情
                    </button>
                  )}
                  {item.opportunity_id && (
                    <button className="secondary small" onClick={() => navigate("/workspace/actions")}>
                      看执行
                    </button>
                  )}
                  <button className="ghost small" onClick={() => removeBoxItem(item)} disabled={savingId === item.id}>
                    移除
                  </button>
                </div>
              </article>
            );
          })}
          {!boxItems.length && <p className="muted-copy">还没有保存机会。可以从每日简报 Top 机会或右侧预测机会存入。</p>}
        </div>
      </section>

      <section className="panel span-5">
        <PanelHeader title="预测机会" action="基于当前信号推演" icon={<Sparkles size={18} />} />
        <div className="box-grid">
          {predictions.map((item) => {
            const summary = actionSummaryFromPrediction(item.prediction) || fallbackActionSummary(item.title, item.suggested_action, item.source);
            return (
              <article className="box-card predicted" key={item.id}>
                <div className="box-card-head">
                  <div>
                    <h3>{item.title}</h3>
                    <p>{item.category} / {item.horizon_days} 天窗口</p>
                  </div>
                  <strong>{item.confidence}%</strong>
                </div>
                <p>{item.reason}</p>
                <div className="prediction-validate">
                  <span>建议验证动作</span>
                  <strong>{summary.first_step || item.suggested_action}</strong>
                  <small>成功：{summary.success_metric}</small>
                </div>
                <div className="tags">
                  <span className="badge">预测分 {item.score}</span>
                  <span className="badge">风险 {uiLabel(summary.risk_level || item.risk_level)}</span>
                  <span className="badge">{item.source}</span>
                </div>
                <div className="feedback compact">
                  <button className="secondary small" onClick={() => savePrediction(item)} disabled={savingId === item.id || item.saved}>
                    <Archive size={14} /> {item.saved ? "已保存" : savingId === item.id ? "保存中..." : "存入机会箱"}
                  </button>
                </div>
              </article>
            );
          })}
          {!predictions.length && <p className="muted-copy">暂无预测机会，建议先运行采集管线。</p>}
        </div>
      </section>
    </div>
  );
}

function AgentsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [registry, setRegistry] = useState<ModelRegistryItem[]>([]);
  const [allocations, setAllocations] = useState<ModelAllocationItem[]>([]);
  const [configs, setConfigs] = useState<AgentConfigPayload[]>([]);
  const [usage, setUsage] = useState<ModelUsageSummary>({ total_tokens: 0, estimated_cost_cny: 0, daily_avg_cost_cny: 0, items: [] });
  const [pipelineStatus, setPipelineStatus] = useState<PipelineRunResult | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [registryResp, allocationsResp, configsResp, usageResp, pipelineResp] = await Promise.all([
        apiGet<ModelRegistryItem[]>("/settings/models/registry"),
        apiGet<ModelAllocationItem[]>("/settings/models/allocation"),
        apiGet<AgentConfigPayload[]>("/agents/configs"),
        apiGet<ModelUsageSummary>("/settings/models/usage"),
        apiGet<PipelineRunResult>("/pipeline/status").catch(() => ({ id: "pending", status: "idle", steps: [] } as PipelineRunResult))
      ]);
      setRegistry(registryResp || []);
      setAllocations(allocationsResp || []);
      setConfigs(configsResp || []);
      setUsage(usageResp || { total_tokens: 0, estimated_cost_cny: 0, daily_avg_cost_cny: 0, items: [] });
      setPipelineStatus(pipelineResp || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "智能体配置加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const agents = buildAgentViews(allocations, configs, pipelineStatus);
  const activeModels = registry.filter((item) => item.state === "active" || item.is_active);

  const updateAgent = (agentName: string, patch: Partial<ModelAllocationItem>) => {
    setAllocations((prev) => {
      const current = prev.find((item) => item.agent_name === agentName);
      if (current) {
        return prev.map((item) => (item.agent_name === agentName ? { ...item, ...patch } : item));
      }
      const catalog = agentCatalog.find((item) => item.agent_name === agentName);
      return [
        ...prev,
        {
          agent_name: agentName,
          model_name: patch.model_name || catalog?.recommended_model || "",
          recommended_model: patch.recommended_model || catalog?.recommended_model || ""
        }
      ];
    });
  };

  const updateAgentConfig = (agentName: string, patch: Partial<AgentConfigPayload>) => {
    setConfigs((prev) => {
      const current = prev.find((item) => item.agent_name === agentName);
      if (current) {
        return prev.map((item) => (item.agent_name === agentName ? { ...item, ...patch } : item));
      }
      const catalog = agentCatalog.find((item) => item.agent_name === agentName);
      const base: AgentConfigPayload = {
        agent_name: agentName,
        display_name: catalog?.display_name || agentName,
        role: catalog?.role || "",
        system_prompt: catalog?.system_prompt || "",
        status: catalog?.status || "active",
        cadence: catalog?.cadence || "manual",
        budget: catalog?.budget || "medium",
        allowed_tools: catalog?.allowed_tools || [],
        fail_strategy: catalog?.fail_strategy || "retry_then_warn",
        max_daily_runs: catalog?.max_daily_runs || 20,
        max_daily_cost_cny: catalog?.max_daily_cost_cny || 5
      };
      return [...prev, { ...base, ...patch }];
    });
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const agentViews = buildAgentViews(allocations, configs, pipelineStatus);
      const allocationPayload = agentViews.map((item) => ({
        agent_name: item.agent_name,
        model_name: item.model_name,
        recommended_model: item.recommended_model
      }));
      const configPayload = agentViews.map(({ model_name, recommended_model, last_run, ...item }) => item);
      await Promise.all([
        apiPut<{ updated: number }>("/settings/models/allocation", allocationPayload),
        apiPut<{ updated: number }>("/agents/configs", configPayload)
      ]);
      setAllocations(allocationPayload);
      setConfigs(configPayload);
      setMessage("智能体配置已保存。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "智能体配置保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page-grid agents-page">
      <section className="panel span-12">
        <div className="toolbar">
          <PanelHeader title="智能体配置" action={`${agents.length} 个智能体`} icon={<Bot size={18} />} />
          <div className="toolbar-right">
            <button className="secondary" onClick={load} disabled={loading}>
              <RefreshCw size={16} /> {loading ? "刷新中..." : "刷新"}
            </button>
            <button className="primary" onClick={save} disabled={saving}>
              <Check size={16} /> {saving ? "保存中..." : "保存配置"}
            </button>
          </div>
        </div>
        {error && <p style={{ color: "#fca5a5" }}>{error}</p>}
        {message && <div className="story-card">{message}</div>}
        <div className="summary-grid" style={{ marginTop: "12px" }}>
          <Metric label="活跃模型" value={String(activeModels.length)} />
          <Metric label="Agent 数" value={String(agents.length)} />
          <Metric label="日均成本" value={String(usage.daily_avg_cost_cny)} />
        </div>
      </section>

      <section className="panel span-12">
        <PanelHeader title="Agent 总览" action={pipelineStatus ? uiLabel(pipelineStatus.status) : "空闲"} icon={<SlidersHorizontal size={18} />} />
        <div className="agent-config-grid">
          {agents.map((agent) => (
            <article className="agent-config-card" key={agent.agent_name}>
              <div className="agent-config-head">
                <div>
                  <h3>{agent.display_name || agent.agent_name}</h3>
                  <small>{agent.agent_name}</small>
                  <p>{agent.role}</p>
                </div>
                <span className={`badge ${agent.status === "running" ? "teal" : ""}`}>{uiLabel(agent.status)}</span>
              </div>
              <div className="agent-controls">
                <label>
                  <span>显示名称</span>
                  <input
                    className="select-button"
                    value={agent.display_name}
                    onChange={(event) => updateAgentConfig(agent.agent_name, { display_name: event.target.value })}
                  />
                </label>
                <label>
                  <span>状态</span>
                  <select
                    className="select-button"
                    value={agent.status}
                    onChange={(event) => updateAgentConfig(agent.agent_name, { status: event.target.value })}
                  >
                    <option value="active">启用</option>
                    <option value="paused">暂停</option>
                    <option value="disabled">停用</option>
                    <option value="running">运行中</option>
                  </select>
                </label>
                <label>
                  <span>当前模型</span>
                  <select
                    className="select-button"
                    value={agent.model_name}
                    onChange={(event) => updateAgent(agent.agent_name, { model_name: event.target.value })}
                  >
                    <option value={agent.model_name}>{agent.model_name}</option>
                    {registry.map((model) => (
                      <option key={model.name} value={model.name}>
                        {model.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>推荐模型</span>
                  <input
                    className="select-button"
                    value={agent.recommended_model}
                    onChange={(event) => updateAgent(agent.agent_name, { recommended_model: event.target.value })}
                  />
                </label>
                <label>
                  <span>运行频率</span>
                  <input
                    className="select-button"
                    value={agent.cadence}
                    onChange={(event) => updateAgentConfig(agent.agent_name, { cadence: event.target.value })}
                  />
                </label>
                <label>
                  <span>预算等级</span>
                  <input
                    className="select-button"
                    value={agent.budget}
                    onChange={(event) => updateAgentConfig(agent.agent_name, { budget: event.target.value })}
                  />
                </label>
                <label>
                  <span>失败策略</span>
                  <select
                    className="select-button"
                    value={agent.fail_strategy}
                    onChange={(event) => updateAgentConfig(agent.agent_name, { fail_strategy: event.target.value })}
                  >
                    <option value="retry_then_warn">重试后预警</option>
                    <option value="fallback_local">本地降级</option>
                    <option value="use_cached_evidence">使用缓存证据</option>
                    <option value="mark_for_review">标记人工复核</option>
                    <option value="answer_with_context_only">仅按现有上下文回答</option>
                  </select>
                </label>
                <label>
                  <span>日运行上限</span>
                  <input
                    className="select-button"
                    type="number"
                    min="0"
                    value={agent.max_daily_runs}
                    onChange={(event) => updateAgentConfig(agent.agent_name, { max_daily_runs: Number(event.target.value) })}
                  />
                </label>
                <label>
                  <span>日成本上限（元）</span>
                  <input
                    className="select-button"
                    type="number"
                    min="0"
                    step="0.1"
                    value={agent.max_daily_cost_cny}
                    onChange={(event) => updateAgentConfig(agent.agent_name, { max_daily_cost_cny: Number(event.target.value) })}
                  />
                </label>
                <label className="wide">
                  <span>工具权限</span>
                  <input
                    className="select-button"
                    value={agent.allowed_tools.join(", ")}
                    onChange={(event) => updateAgentConfig(agent.agent_name, {
                      allowed_tools: event.target.value.split(",").map((item) => item.trim()).filter(Boolean)
                    })}
                  />
                </label>
                <label className="wide">
                  <span>职责说明</span>
                  <textarea
                    className="agent-textarea"
                    value={agent.role}
                    onChange={(event) => updateAgentConfig(agent.agent_name, { role: event.target.value })}
                  />
                </label>
                <label className="wide">
                  <span>系统提示词</span>
                  <textarea
                    className="agent-textarea prompt"
                    value={agent.system_prompt}
                    onChange={(event) => updateAgentConfig(agent.agent_name, { system_prompt: event.target.value })}
                  />
                </label>
              </div>
              <div className="agent-meta">
                <span>频率：{agent.cadence}</span>
                <span>预算：{agent.budget}</span>
                <span>工具：{agent.allowed_tools.length}</span>
                <span>上限：{agent.max_daily_runs} 次 / {agent.max_daily_cost_cny} 元</span>
                <span>最近：{formatDate(agent.last_run)}</span>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="panel span-12">
        <PanelHeader title="模型注册表" action={`${registry.length} 个模型`} icon={<Database size={18} />} />
        <div className="source-grid">
          {registry.map((model) => (
            <article className="source-card" key={model.name}>
              <h3>{model.name}</h3>
              <p>{model.provider} / {uiLabel(model.state)}</p>
              <small>{model.endpoint}</small>
            </article>
          ))}
          {!registry.length && <p>暂无模型注册数据。</p>}
        </div>
      </section>
    </div>
  );
}

function ChatPage() {
  const [loading, setLoading] = useState(true);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [input, setInput] = useState("今天最值得先做哪个？");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "我已准备好读取最新日报、机会池和数据源状态。"
    }
  ]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [briefResp, opportunityResp, sourceResp] = await Promise.all([
        apiGet<Brief | null>("/brief/latest"),
        apiGet<ListResponse<Opportunity>>("/opportunities?sort=score&limit=8"),
        apiGet<ListResponse<SourceItem>>("/sources/status")
      ]);
      setBrief(briefResp && briefResp.id ? briefResp : null);
      setOpportunities(opportunityResp.items || []);
      setSources(sourceResp.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "对话上下文加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const send = () => {
    const text = input.trim();
    if (!text) return;
    const userMessage: ChatMessage = { id: `u-${Date.now()}`, role: "user", content: text };
    const assistantMessage: ChatMessage = {
      id: `a-${Date.now()}`,
      role: "assistant",
      content: buildAdvisorReply(text, brief, opportunities, sources)
    };
    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput("");
  };

  const ask = (question: string) => {
    setInput(question);
  };

  const top = brief?.payload?.top_opportunities?.[0];

  return (
    <div className="page-grid chat-page">
      <section className="panel span-8 chat-panel">
        <div className="toolbar">
          <PanelHeader title="AI 对话" action={loading ? "加载中" : "上下文已就绪"} icon={<MessageSquareText size={18} />} />
          <button className="secondary" onClick={load} disabled={loading}>
            <RefreshCw size={16} /> 刷新上下文
          </button>
        </div>
        {error && <p style={{ color: "#fca5a5" }}>{error}</p>}
        <div className="chat-box advisor-chat">
          {messages.map((message) => (
            <article className={message.role === "assistant" ? "assistant-msg" : "user-msg"} key={message.id}>
              {message.content}
            </article>
          ))}
        </div>
        <div className="chat-composer">
          <textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => {
            if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) send();
          }} />
          <button className="primary" onClick={send}>
            <Send size={16} /> 发送
          </button>
        </div>
      </section>

      <section className="panel span-4">
        <PanelHeader title="上下文" action={brief?.date_key || "暂无日报"} icon={<BookOpen size={18} />} />
        <div className="metric-list">
          <Metric label="机会" value={String(brief?.payload?.metrics?.opportunity_count ?? opportunities.length)} />
          <Metric label="信号" value={String(brief?.payload?.metrics?.signal_count ?? brief?.payload?.signals?.length ?? 0)} />
          <Metric label="异常来源" value={String(brief?.payload?.metrics?.source_failed_count ?? 0)} />
          <Metric label="待配置" value={String(brief?.payload?.metrics?.source_needs_config_count ?? 0)} />
        </div>
        {top && (
          <article className="story-card chat-context-card">
            <h3>{top.title}</h3>
            <p>{top.playbook_name} / {top.source}</p>
            <small>分数 {top.score} / 验证 {top.validation_score} / 风险 {uiLabel(top.risk_level)}</small>
          </article>
        )}
        <div className="prompt-list">
          {["今天最值得先做哪个？", "为什么第一个机会排第一？", "哪些数据源异常？", "按低风险和小预算推荐一个。"].map((question) => (
            <button className="secondary" key={question} onClick={() => ask(question)}>
              {question}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function ScenariosPage() {
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [presets, setPresets] = useState<ScenarioPreset[]>([]);
  const [history, setHistory] = useState<ScenarioHistory[]>([]);
  const [scenarioText, setScenarioText] = useState("如果短视频搬运内容监管收紧，会影响哪些机会？");
  const [presetId, setPresetId] = useState<string>("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [presetsData, historyData] = await Promise.all([
        apiGet<ListResponse<ScenarioPreset>>("/scenarios/presets"),
        apiGet<ListResponse<ScenarioHistory>>("/scenarios/history?limit=20")
      ]);
      setPresets(presetsData.items || []);
      setHistory(historyData.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "情景数据加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const runAnalyze = async () => {
    setRunning(true);
    setMessage(null);
    setError(null);
    try {
      const result = await apiPost<ScenarioHistory>("/scenarios/analyze", {
        scenario: scenarioText,
        preset_id: presetId || undefined
      });
      setMessage(result.result || "分析已返回。");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "情景分析失败");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="page-grid">
      <section className="panel span-12">
        <PanelHeader title="情景推演" action="假设分析" icon={<Sparkles size={18} />} />
        <div className="feedback" style={{ marginBottom: "12px", alignItems: "stretch" }}>
          <textarea
            style={{ minHeight: "84px", width: "100%", borderRadius: "8px", background: "#0f1726", color: "#f9fafb", border: "1px solid #1f2937", padding: "10px" }}
            value={scenarioText}
            onChange={(event) => setScenarioText(event.target.value)}
          />
        </div>
        <div className="toolbar">
          <select value={presetId} onChange={(event) => setPresetId(event.target.value)} className="select-button">
            <option value="">使用自定义情景</option>
            {presets.map((preset) => (
              <option key={preset.id} value={preset.id}>
                {preset.name}
              </option>
            ))}
          </select>
          <button className="primary" data-testid="scenario-run" onClick={runAnalyze} disabled={running || !scenarioText.trim()}>
            <Plus size={16} /> {running ? "推演中..." : "开始推演"}
          </button>
        </div>
        {message && <div className="story-card">{message}</div>}
        {error && <p style={{ color: "#fca5a5" }}>{error}</p>}
      </section>
      <section className="panel span-12">
        <PanelHeader title="预设列表" action={`${presets.length} 个预设`} icon={<CircleDollarSign size={18} />} />
        <div className="source-grid">
          {presets.length ? (
            presets.map((preset) => (
              <article className="source-card" key={preset.id}>
                <h3>{preset.name}</h3>
                <p>{preset.scenario}</p>
                <small>{preset.description}</small>
              </article>
            ))
          ) : (
            <p>暂无预设。</p>
          )}
        </div>
      </section>
      <section className="panel span-12">
        <PanelHeader title="历史记录" action="最近输出" icon={<MessageSquareText size={18} />} />
        {loading ? (
          <p>加载中...</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>情景</th>
                  <th>置信度</th>
                  <th>结果</th>
                </tr>
              </thead>
              <tbody>
                {history.map((row) => (
                  <tr key={row.id}>
                    <td>{formatDate(row.created_at)}</td>
                    <td>{row.scenario}</td>
                    <td>{Math.round((row.confidence || 0) * 100)}%</td>
                    <td>{row.result}</td>
                  </tr>
                ))}
                {!history.length && (
                  <tr>
                    <td colSpan={4}>暂无情景推演历史。</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function SourcesPage() {
  const initialSources = useMemo(() => mergeSourceCatalog([]), []);
  const [items, setItems] = useState<SourceItem[]>(initialSources);
  const [selected, setSelected] = useState<SourceDetail | null>(initialSources[0] || null);
  const [loading, setLoading] = useState(false);
  const [refreshingId, setRefreshingId] = useState<string | null>(null);
  const [batchRunning, setBatchRunning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sourceQuery, setSourceQuery] = useState("");

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiGet<ListResponse<SourceItem>>('/sources/status');
      const nextItems = mergeSourceCatalog(res.items || []);
      setItems(nextItems);
      setSelected((current) => nextItems.find((item) => item.source === current?.source) || nextItems[0] || null);
    } catch (err) {
      setItems(mergeSourceCatalog([]));
      setSelected((current) => current || initialSources[0] || null);
      setError(err instanceof Error ? `已展示静态目录，状态同步失败：${err.message}` : '已展示静态目录，状态同步失败');
    } finally {
      setLoading(false);
    }
  };

  const refreshSource = async (source: SourceItem) => {
    setRefreshingId(source.id);
    setError(null);
    try {
      const detail = await apiGet<SourceDetail>(`/sources/${encodeURIComponent(source.source)}/freshness`);
      const next = { ...source, ...detail, source: source.source, category: source.category, source_type: source.source_type, is_static: false };
      setSelected(next);
      setItems((prev) => prev.map((item) => item.source === source.source ? next : item));
    } catch (err) {
      setError(err instanceof Error ? err.message : '数据源刷新失败');
    } finally {
      setRefreshingId(null);
    }
  };

  const runSourceBatch = async (sources: SourceItem[], reason: string) => {
    const targetSources = Array.from(new Set(sources.filter(isRetryableSource).map((source) => source.source)));
    if (!targetSources.length) return;
    setBatchRunning(reason);
    setError(null);
    setMessage(null);
    try {
      const result = await apiPost<PipelineRunResult>("/pipeline/run", {
        steps: ["collect", "clean", "analyze", "score"],
        sources: targetSources,
        reason,
      });
      setMessage(
        result.status === "running"
          ? `已提交 ${targetSources.length} 个数据源采集，完成后点“同步状态”查看结果。`
          : `流水线状态：${uiLabel(result.status)}`
      );
      window.setTimeout(() => {
        load();
      }, 3500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "批量刷新失败");
    } finally {
      setBatchRunning(null);
    }
  };

  const onSelectSource = (source: SourceItem) => {
    setSelected(source);
  };

  useEffect(() => {
    load();
  }, []);

  const primaryItems = useMemo(() => items.filter((source) => !isLegacySource(source)), [items]);
  const legacyItems = useMemo(() => items.filter(isLegacySource), [items]);
  const statusSyncedItems = useMemo(() => primaryItems.filter((source) => !source.is_static), [primaryItems]);

  const sourceSummary = useMemo(() => {
    return primaryItems.reduce(
      (acc, source) => {
        const state = sourceCollectionState(source);
        const freshness = sourceDataFreshness(source);
        const operational = sourceOperationalState(source);
        const capability = sourceCapability(source);
        acc.total += 1;
        acc.collection[state] += 1;
        acc.freshness[freshness] += 1;
        acc.operational[operational] = (acc.operational[operational] || 0) + 1;
        acc.capability[capability] = (acc.capability[capability] || 0) + 1;
        if (isNormalExpiredSource(source)) acc.normalExpired += 1;
        if (isNormalStaleSource(source)) acc.normalStale += 1;
        return acc;
      },
      {
        total: 0,
        normalExpired: 0,
        normalStale: 0,
        collection: { normal: 0, issue: 0, config: 0, pending: 0 },
        freshness: { fresh: 0, stale: 0, expired: 0, unknown: 0, not_configured: 0 },
        operational: {} as Record<string, number>,
        capability: { live: 0, auth: 0, integration: 0, restricted: 0, legacy: 0, pending: 0 } as Record<SourceCapability, number>,
      }
    );
  }, [primaryItems]);

  const sourceQueues = useMemo(() => {
    const live = primaryItems.filter((source) => sourceCapability(source) === "live");
    const auth = primaryItems.filter((source) => sourceCapability(source) === "auth");
    const integration = primaryItems.filter((source) => sourceCapability(source) === "integration");
    const restricted = primaryItems.filter((source) => sourceCapability(source) === "restricted");
    const pending = primaryItems.filter((source) => sourceCapability(source) === "pending");
    const ready = primaryItems.filter((source) => sourceOperationalState(source) === "ready");
    const noNew = primaryItems.filter((source) => sourceOperationalState(source) === "no_new");
    const normalExpired = primaryItems.filter(isNormalExpiredSource);
    const normalStale = primaryItems.filter(isNormalStaleSource);
    const issue = primaryItems.filter((source) => sourceCollectionState(source) === "issue");
    const unsyncedLive = live.filter((source) => source.is_static);
    return { live, auth, integration, restricted, pending, ready, noNew, normalExpired, normalStale, issue, unsyncedLive, legacy: legacyItems };
  }, [legacyItems, primaryItems]);

  const categories = useMemo(() => {
    const visiblePool = statusFilter === "legacy" ? legacyItems : primaryItems;
    return ["all", ...Array.from(new Set(visiblePool.map((item) => item.category || "未分类"))).sort()];
  }, [legacyItems, primaryItems, statusFilter]);

  const filteredItems = useMemo(() => {
    const query = sourceQuery.trim().toLowerCase();
    const pool = statusFilter === "legacy" ? legacyItems : primaryItems;
    return pool.filter((source) => {
      const collectionState = sourceCollectionState(source);
      const freshnessState = sourceDataFreshness(source);
      const operationalState = sourceOperationalState(source);
      const capability = sourceCapability(source);
      const matchesStatus =
        statusFilter === "all" ||
        capability === statusFilter ||
        operationalState === statusFilter ||
        (statusFilter === "normal_expired" && isNormalExpiredSource(source)) ||
        (statusFilter === "normal_stale" && isNormalStaleSource(source)) ||
        collectionState === statusFilter ||
        freshnessState === statusFilter;
      const matchesCategory = categoryFilter === "all" || (source.category || "未分类") === categoryFilter;
      const haystack = `${source.source} ${source.category || ""} ${source.source_type || ""} ${source.notes || ""}`.toLowerCase();
      return matchesStatus && matchesCategory && (!query || haystack.includes(query));
    });
  }, [legacyItems, primaryItems, statusFilter, categoryFilter, sourceQuery]);

  const capabilityTabs = [
    { key: "all", label: "全部收录", count: sourceSummary.total, hint: "权威目录口径" },
    { key: "live", label: "实际拉取", count: sourceQueues.live.length, hint: "pipeline 会执行" },
    { key: "auth", label: "需要授权", count: sourceQueues.auth.length, hint: "补 key/token/relay" },
    { key: "integration", label: "待接入", count: sourceQueues.integration.length, hint: "需要 adapter 或依赖" },
    { key: "restricted", label: "受限源", count: sourceQueues.restricted.length, hint: "需服务商或授权数据" },
    { key: "issue", label: "异常", count: sourceQueues.issue.length, hint: "失败或需重试" },
    { key: "legacy", label: "历史源", count: legacyItems.length, hint: "不计入权威目录" },
  ];

  const healthTabs = [
    { key: "normal_expired", label: "过期待刷新", count: sourceQueues.normalExpired.length },
    { key: "no_new", label: "正常无新增", count: sourceQueues.noNew.length },
    { key: "pending", label: "未初始化状态", count: sourceQueues.unsyncedLive.length },
    { key: "config", label: "待配置状态", count: sourceSummary.collection.config },
  ];

  return (
    <div className="page-grid">
      <section className="panel span-12">
        <div className="toolbar">
          <PanelHeader title="数据源中心" action={loading ? "同步运行状态中" : `权威目录 ${sourceSummary.total} · 已同步 ${statusSyncedItems.length}`} icon={<Database size={18} />} />
          <button className="secondary" data-testid="sources-refresh" onClick={load} disabled={loading}>
            <RefreshCw size={16} /> {loading ? '同步中...' : '同步状态'}
          </button>
        </div>
        {error && <p style={{ color: '#fecaca' }}>{error}</p>}
        {message && <div className="story-card source-message">{message}</div>}
        <div className="source-hero-grid">
          <article>
            <span>收录数据源</span>
            <strong>{sourceSummary.total}</strong>
            <small>权威目录，不含历史遗留源</small>
          </article>
          <article>
            <span>实际拉取</span>
            <strong>{sourceQueues.live.length}</strong>
            <small>pipeline 会直接执行采集</small>
          </article>
          <article>
            <span>需要授权</span>
            <strong>{sourceQueues.auth.length}</strong>
            <small>补 key、token、账号或 relay</small>
          </article>
          <article>
            <span>待接入/受限</span>
            <strong>{sourceQueues.integration.length + sourceQueues.restricted.length}</strong>
            <small>需要 adapter、服务商或合规授权</small>
          </article>
          <article>
            <span>状态快照</span>
            <strong>{statusSyncedItems.length}</strong>
            <small>后端当前返回的运行状态数</small>
          </article>
        </div>
        <div className="source-status-strip source-capability-strip">
          {capabilityTabs.map((tabItem) => (
            <button
              key={tabItem.key}
              className={statusFilter === tabItem.key ? "selected" : ""}
              onClick={() => setStatusFilter(tabItem.key)}
            >
              <strong>{tabItem.count}</strong>
              <span>{tabItem.label}</span>
              <small>{tabItem.hint}</small>
            </button>
          ))}
        </div>
        <div className="source-action-panel source-action-panel-compact">
          <article className="source-action-card">
            <div>
              <Filter size={16} />
              <strong>需要刷新</strong>
              <span>{sourceQueues.normalExpired.length + sourceQueues.issue.length} 个</span>
            </div>
            <p>这些源已经进入实际采集链路，但状态过期或曾失败。适合一键补采集。</p>
            <div className="model-actions">
              <button className="ghost small" onClick={() => setStatusFilter("normal_expired")}>看过期</button>
              <button
                className="primary small"
                onClick={() => runSourceBatch([...sourceQueues.normalExpired, ...sourceQueues.issue], "refresh_live_sources")}
                disabled={(!sourceQueues.normalExpired.length && !sourceQueues.issue.length) || batchRunning !== null}
              >
                <RefreshCw size={14} /> {batchRunning === "refresh_live_sources" ? "提交中..." : "批量采集"}
              </button>
            </div>
          </article>
          <article className="source-action-card">
            <div>
              <Settings size={16} />
              <strong>授权清单</strong>
              <span>{sourceQueues.auth.length} 个</span>
            </div>
            <p>这里不是采集失败，而是缺少明确的 key、token、账号或 relay。应该单独配置。</p>
            <div className="model-actions">
              <button className="ghost small" onClick={() => setStatusFilter("auth")}>查看授权项</button>
            </div>
          </article>
          <article className="source-action-card">
            <div>
              <Database size={16} />
              <strong>待接入</strong>
              <span>{sourceQueues.integration.length} 个</span>
            </div>
            <p>这类源通常要补依赖、批处理 adapter、限流策略或解析器，不能只靠刷新解决。</p>
            <div className="model-actions">
              <button className="ghost small" onClick={() => setStatusFilter("integration")}>查看接入项</button>
            </div>
          </article>
          <article className="source-action-card">
            <div>
              <ShieldCheck size={16} />
              <strong>受限与历史</strong>
              <span>{sourceQueues.restricted.length + legacyItems.length} 个</span>
            </div>
            <p>受限源需要服务商或自有授权；历史源只用于解释旧状态，不进入权威总数。</p>
            <div className="model-actions">
              <button className="ghost small" onClick={() => setStatusFilter("restricted")}>受限源</button>
              <button className="ghost small" onClick={() => setStatusFilter("legacy")}>历史源</button>
            </div>
          </article>
        </div>
        <div className="source-health-strip">
          {healthTabs.map((tabItem) => (
            <button
              key={tabItem.key}
              className={statusFilter === tabItem.key ? "selected" : ""}
              onClick={() => setStatusFilter(tabItem.key)}
            >
              <span>{tabItem.label}</span>
              <strong>{tabItem.count}</strong>
            </button>
          ))}
        </div>
        <div className="source-filter-bar">
          <div className="search source-search">
            <Search size={16} />
            <input
              value={sourceQuery}
              onChange={(event) => setSourceQuery(event.target.value)}
              placeholder="搜索数据源、分类或备注"
            />
          </div>
          <select className="select-button" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
            {categories.map((category) => (
              <option key={category} value={category}>{category === "all" ? "全部分类" : category}</option>
            ))}
          </select>
        </div>
        <div className="source-workbench">
          <div className="source-table-wrap">
            <table className="source-table">
              <thead>
                <tr>
                  <th>数据源</th>
                  <th>采集能力</th>
                  <th>运行状态</th>
                  <th>配置/授权</th>
                  <th>最近检查</th>
                  <th>24h</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((source) => (
                  <tr key={source.source} className={selected?.source === source.source ? "selected" : ""}>
                    <td>
                      <strong>{source.source}</strong>
                      <small>{source.category || "未分类"} · {source.source_type || "unknown"}</small>
                    </td>
                    <td><SourceCapabilityBadge source={source} /></td>
                    <td><SourceStatusBadge source={source} /></td>
                    <td><small>{sourceConfigText(source)}</small></td>
                    <td>{formatDate(source.last_checked)}</td>
                    <td>{source.signal_count_24h || 0}</td>
                    <td>
                      <div className="source-row-actions">
                        <button className="secondary small" onClick={() => onSelectSource(source)}>详情</button>
                        {sourceCapability(source) === "live" ? (
                          <button
                            className="ghost small"
                            data-testid={`source-freshness-${source.id}`}
                            onClick={() => refreshSource(source)}
                            disabled={refreshingId === source.id}
                          >
                            {refreshingId === source.id ? "同步中..." : "同步"}
                          </button>
                        ) : (
                          <button className="ghost small" onClick={() => onSelectSource(source)}>配置</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {!filteredItems.length && (
                  <tr>
                    <td colSpan={7}>当前筛选条件下暂无数据源。</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <aside className="source-side-detail">
            {selected ? (
              <>
                <div>
                  <span className="eyebrow">当前选中</span>
                  <h3>{selected.source}</h3>
                </div>
                <SourceCapabilityBadge source={selected} />
                <p>{selected.notes || selected.freshness_reason || "暂无说明"}</p>
                <div className="source-detail-list">
                  <span>采集能力</span><strong>{sourceCapabilityText(selected)}</strong>
                  <span>配置项</span><strong>{sourceConfigText(selected)}</strong>
                  <span>运行状态</span><strong>{uiLabel(sourceOperationalState(selected))}</strong>
                  <span>最近检查</span><strong>{formatDate(selected.last_checked)}</strong>
                  <span>24h 信号</span><strong>{String(selected.signal_count_24h || 0)}</strong>
                  <span>状态说明</span><strong>{selected.freshness_reason || (selected.is_static ? "尚未写入运行状态" : "--")}</strong>
                </div>
              </>
            ) : (
              <p>选择一个数据源查看配置和运行状态。</p>
            )}
          </aside>
        </div>
      </section>

      <section className="panel span-6">
        <PanelHeader title="平台分布" action="按数据源统计" icon={<BarChart3 size={18} />} />
        <PlatformBar />
      </section>
      <section className="panel span-6">
        <PanelHeader title="信号趋势" action="最近 24 小时" icon={<LineChart size={18} />} />
        <TrendChart />
      </section>
    </div>
  );
}
function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [registry, setRegistry] = useState<ModelRegistryItem[]>([]);
  const [allocations, setAllocations] = useState<ModelAllocationItem[]>([]);
  const [usage, setUsage] = useState<ModelUsageSummary>({
    total_tokens: 0,
    estimated_cost_cny: 0,
    daily_avg_cost_cny: 0,
    items: []
  });
  const [pipelineStatus, setPipelineStatus] = useState<PipelineRunResult | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [registryResp, usageResp, allocationsResp, pipelineResp] = await Promise.all([
        apiGet<ModelRegistryItem[]>('/settings/models/registry'),
        apiGet<ModelUsageSummary>('/settings/models/usage'),
        apiGet<ModelAllocationItem[]>('/settings/models/allocation'),
        apiGet<PipelineRunResult>('/pipeline/status').catch(() => ({ id: 'pending', status: 'idle' } as PipelineRunResult))
      ]);
      setRegistry(registryResp || []);
      setUsage(usageResp || { total_tokens: 0, estimated_cost_cny: 0, daily_avg_cost_cny: 0, items: [] });
      setAllocations(allocationsResp || []);
      setPipelineStatus(pipelineResp || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '设置加载失败');
    } finally {
      setLoading(false);
    }
  };

  const runPipeline = async () => {
    setPipelineRunning(true);
    setError(null);
    setMessage(null);
    try {
      const result = await apiPost<PipelineRunResult>('/pipeline/run', { steps: ['collect', 'clean', 'analyze', 'score'] });
      setPipelineStatus(result);
      setMessage(result.status === 'running' ? '流水线已启动，正在刷新状态...' : `流水线状态：${uiLabel(result.status)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '流水线启动失败');
    } finally {
      setPipelineRunning(false);
    }
  };

  const saveAllocation = async () => {
    setError(null);
    setMessage(null);
    try {
      await apiPut<{ updated: number }>('/settings/models/allocation', allocations);
      setMessage('模型分配设置已保存。');
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败');
    }
  };

  const updateAllocation = (index: number, patch: Partial<ModelAllocationItem>) => {
    setAllocations((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], ...patch };
      return next;
    });
  };

  const testModel = async (model: ModelRegistryItem) => {
    setError(null);
    try {
      const response = await apiPost<{ test: string }>(`/settings/models/registry/${encodeURIComponent(model.name)}/test`);
      setMessage(`模型连接测试通过：${response.test}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '模型连接测试失败');
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (pipelineStatus?.status !== 'running') return;
    const timer = window.setInterval(async () => {
      try {
        const latest = await apiGet<PipelineRunResult>('/pipeline/status');
        setPipelineStatus(latest);
        if (latest.status !== 'running') {
          setMessage(latest.message || `流水线状态：${uiLabel(latest.status)}`);
          window.clearInterval(timer);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '流水线状态刷新失败');
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [pipelineStatus?.status]);

  return (
    <div className="page-grid">
      <section className="panel span-12">
        <div className="toolbar">
          <PanelHeader title="设置" action="模型治理与运营控制" icon={<Settings size={18} />} />
          <div className="toolbar-right">
            <button className="secondary" data-testid="settings-refresh" onClick={load} disabled={loading}>
              <RefreshCw size={16} /> {loading ? '刷新中...' : '刷新'}
            </button>
            <button className="primary" data-testid="settings-run-pipeline" onClick={runPipeline} disabled={pipelineRunning}>
              <RefreshCw size={16} /> {pipelineRunning ? '运行中...' : '运行流水线'}
            </button>
          </div>
        </div>
        {error && <p style={{ color: '#fca5a5' }}>{error}</p>}
        {message && <div className="story-card">{message}</div>}

        <div className="summary-grid" style={{ marginTop: '12px' }}>
          <Metric label="总令牌用量" value={String(usage.total_tokens)} />
          <Metric label="预估成本（元）" value={String(usage.estimated_cost_cny)} />
          <Metric label="日均成本" value={String(usage.daily_avg_cost_cny)} />
        </div>
        <div className="story-card" style={{ marginTop: '12px' }}>
          <p>流水线状态：{pipelineStatus ? uiLabel(pipelineStatus.status) : '空闲'} </p>
          <p>最新消息：{pipelineStatus?.message || '暂无'}</p>
        </div>
      </section>

      <section className="panel span-12">
        <PanelHeader title="模型用量" action="近期汇总" icon={<Gauge size={18} />} />
        <div className="source-grid">
          {usage.items.map((item) => (
            <article className="source-card" key={`${item.model}-${item.skill_name}`}>
              <h3>{item.skill_name}</h3>
              <Metric label="模型" value={item.model} />
              <Metric label="令牌用量" value={String(item.tokens)} />
              <Metric label="成本" value={`${item.cost}`} />
            </article>
          ))}
          {!usage.items.length && <p>暂无用量记录。</p>}
        </div>
      </section>

      <section className="panel span-12">
        <PanelHeader title="模型分配" action="智能体到模型映射" icon={<Target size={18} />} />
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>智能体</th>
                <th>当前模型</th>
                <th>推荐模型</th>
              </tr>
            </thead>
            <tbody>
              {allocations.map((item, idx) => (
                <tr key={`${item.agent_name}-${idx}`}>
                  <td>
                    <input
                      className="select-button"
                      value={item.agent_name}
                      onChange={(event) => updateAllocation(idx, { agent_name: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="select-button"
                      value={item.model_name}
                      onChange={(event) => updateAllocation(idx, { model_name: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="select-button"
                      value={item.recommended_model}
                      onChange={(event) => updateAllocation(idx, { recommended_model: event.target.value })}
                    />
                  </td>
                </tr>
              ))}
              {!allocations.length && (
                <tr>
                  <td colSpan={3}>暂无分配数据。</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="toolbar" style={{ marginTop: '12px' }}>
          <button className="primary" data-testid="settings-save-allocation" onClick={saveAllocation}>
            保存分配
          </button>
        </div>
      </section>

      <section className="panel span-12">
        <PanelHeader title="模型注册表" action="模型注册与操作" icon={<Database size={18} />} />
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>名称</th>
                <th>供应商</th>
                <th>端点</th>
                <th>状态</th>
                <th>用量</th>
                <th>成本</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {registry.map((item) => (
                <tr key={item.name}>
                  <td>{item.name}</td>
                  <td>{item.provider}</td>
                  <td>{item.endpoint}</td>
                  <td>{uiLabel(item.state)}</td>
                  <td>{String(item.usage || 0)}</td>
                  <td>{String(item.cost || 0)}</td>
                  <td>
                    <button className="secondary small" data-testid={`settings-test-model-${encodeURIComponent(item.name)}`} onClick={() => testModel(item)}>
                      测试连接
                    </button>
                  </td>
                </tr>
              ))}
              {!registry.length && (
                <tr>
                  <td colSpan={7}>暂无模型。</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
function StatCard({ label, value, trend, icon }: { label: string; value: string; trend: string; icon: React.ReactNode }) {
  return (
    <article className="stat-card">
      <span>{icon}</span>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        <small>{trend}</small>
      </div>
    </article>
  );
}

function PanelHeader({ title, action, icon }: { title: string; action: string; icon: React.ReactNode }) {
  return (
    <div className="panel-header">
      <div>
        {icon}
        <h2>{title}</h2>
      </div>
      <span>{action}</span>
    </div>
  );
}

function Segmented({ values, active, setActive }: { values: string[]; active: string; setActive: (value: string) => void }) {
  return (
    <div className="segmented">
      {values.map((value) => (
        <button
          key={value}
          className={value === active ? "selected" : ""}
          onClick={() => setActive(value)}
        >
          {uiLabel(value)}
        </button>
      ))}
    </div>
  );
}

function LevelBadge({ level, score }: { level: string; score: number }) {
  return <span className={`level level-${level}`}>{`${level}-${score}`}</span>;
}

function CrowdingBadge({ value }: { value: string }) {
  return <span className={`badge crowding-${normalizeTag(value)}`}>{uiLabel(value)}</span>;
}

function RiskBadge({ value }: { value: string }) {
  return <span className={`badge risk-${normalizeTag(value)}`}>{uiLabel(value)}</span>;
}

function GateBadge({ stage, freshness }: { stage?: string | null; freshness?: string | null }) {
  const safeStage = normalizeState(stage || "watch");
  const safeFreshness = normalizeState(freshness || "unknown");
  return (
    <span className={`badge gate-badge gate-${safeStage} freshness-${safeFreshness}`}>
      {uiLabel(stage || "watch")} · {uiLabel(freshness || "unknown")}
    </span>
  );
}

function SourceStatusBadge({ source }: { source: SourceItem }) {
  const state = sourceCollectionState(source);
  const freshness = sourceDataFreshness(source);
  const operationalState = sourceOperationalState(source);
  const labels: Record<SourceCollectionState, string> = {
    normal: "正常",
    issue: "采集失败",
    config: "待配置/受限",
    pending: "未初始化",
  };
  return (
    <span className={`badge source-status-badge source-status-${state} source-operational-${operationalState}`}>
      {uiLabel(operationalState)} · {labels[state]} · {source.is_static ? "未初始化" : uiLabel(freshness)}
    </span>
  );
}

function SourceCapabilityBadge({ source }: { source: SourceItem }) {
  const capability = sourceCapability(source);
  return (
    <span className={`badge source-capability-badge source-capability-${capability}`}>
      {SOURCE_CAPABILITY_LABELS[capability]}
    </span>
  );
}

function DifficultyBadge({ value }: { value: string }) {
  return <span className="badge difficulty">{uiLabel(value)}</span>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function BriefSourceBucket({ title, items, tone }: { title: string; items: BriefSource[]; tone: "good" | "bad" | "warn" | "quiet" }) {
  return (
    <article className={`brief-source-bucket ${tone}`}>
      <div>
        <h3>{title}</h3>
        <strong>{items.length}</strong>
      </div>
      {firstItems(items, 4).map((item) => (
        <p key={item.id || item.source}>
          <span>{item.source}</span>
          <small>{item.signal_count_24h || 0} 条 / {uiLabel(item.status)}</small>
        </p>
      ))}
      {!items.length && <small>暂无</small>}
    </article>
  );
}

function RiskItem({ title, value }: { title: string; value: string }) {
  return (
    <article className="risk-item">
      <h3>{title}</h3>
      <p>{value}</p>
    </article>
  );
}

function TrendChart() {
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={trendData}>
          <defs>
            <linearGradient id="signalFill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.42} />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.04} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#223047" strokeDasharray="3 3" />
          <XAxis dataKey="time" stroke="#9ca3af" />
          <YAxis stroke="#9ca3af" />
          <Tooltip contentStyle={{ background: "#111827", border: "1px solid #253248", color: "#f9fafb" }} />
          <Area type="monotone" dataKey="signals" stroke="#3b82f6" fill="url(#signalFill)" />
          <Area type="monotone" dataKey="high" stroke="#f59e0b" fill="#f59e0b22" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function PlatformBar() {
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={platformData}>
          <CartesianGrid stroke="#223047" strokeDasharray="3 3" />
          <XAxis dataKey="name" stroke="#9ca3af" />
          <YAxis stroke="#9ca3af" />
          <Tooltip contentStyle={{ background: "#111827", border: "1px solid #253248", color: "#f9fafb" }} />
          <Bar dataKey="value" radius={[6, 6, 0, 0]}>
            {platformData.map((_, index) => (
              <Cell key={index} fill={["#3b82f6", "#14b8a6", "#f59e0b", "#ef4444", "#a78bfa"][index]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function RadarChartBlock({ data, color = "#3b82f6" }: { data: { axis: string; value: number }[]; color?: string }) {
  return (
    <div className="radar-chart">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data}>
          <PolarGrid stroke="#2a3a55" />
          <PolarAngleAxis dataKey="axis" stroke="#d1d5db" />
          <PolarRadiusAxis angle={90} domain={[0, 100]} stroke="#64748b" />
          <RadarShape dataKey="value" stroke={color} fill={color} fillOpacity={0.35} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

function IconButton({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <button className="icon-button" title={title} aria-label={title}>
      {children}
    </button>
  );
}

createRoot(document.getElementById("root")!).render(<App />);


