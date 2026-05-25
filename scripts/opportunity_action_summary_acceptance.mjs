const API_BASE = (process.env.VITE_API_BASE_URL || process.env.INFOEDGE_API_BASE || "http://127.0.0.1:8000")
  .replace(/\/api\/?$/, "")
  .replace(/\/+$/, "");

function baseUrl(path) {
  return `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;
}

async function request(path) {
  const response = await fetch(baseUrl(path.startsWith("/api") ? path : `/api${path}`), {
    headers: { Accept: "application/json" }
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }
  const payload = await response.json();
  if (payload?.success === false) {
    throw new Error(payload.error || "API returned success=false");
  }
  return payload.data;
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function cjkCount(text) {
  return Array.from(String(text || "")).filter((char) => /[\u3400-\u9fff]/u.test(char)).length;
}

function assertChineseNarrative(text, context, minLength = 80) {
  const value = String(text || "");
  assert(value.length >= minLength, `${context}: too short (${value.length} < ${minLength})`);
  const cjk = cjkCount(value);
  assert(cjk >= Math.floor(minLength * 0.55), `${context}: not enough Chinese narrative`);
  assert(!/\b(open_source|saas|crypto|dropshipping|affiliate|leadgen)\b/i.test(value), `${context}: contains untranslated playbook token`);
}

function assertSpecificPredictionMarket(summary, title, context) {
  const combined = [
    title,
    summary.opportunity,
    summary.info_gap,
    summary.what_to_sell,
    summary.first_step,
    ...(summary.validation_plan || [])
  ].join("\n");
  assert(!/Prediction market leading-signal watch/i.test(combined), `${context}: raw English playbook leaked`);
  assert(!/Hantavirus pandemic in 2026\?/i.test(combined), `${context}: raw English market title leaked`);
  assert(/盘口|概率|成交量|流动性/.test(combined), `${context}: missing concrete market mechanics`);
  assert(/官方|世卫组织|第二来源|结算|触发条件/.test(combined), `${context}: missing official-source validation`);
  assert(/客户|付费|订阅|简报|监控页/.test(combined), `${context}: missing monetization path`);
}

function assertSpecificMerchantAnalysis(merchantAnalysis, context) {
  assert(merchantAnalysis && typeof merchantAnalysis === "object", `${context}: missing merchant_analysis`);
  assert(merchantAnalysis.analysis_version === "merchant_analysis_v7", `${context}: expected merchant_analysis_v7`);

  const combined = [
    merchantAnalysis.plain_type,
    merchantAnalysis.agent_config?.role,
    ...(merchantAnalysis.agent_config?.inputs || []),
    ...(merchantAnalysis.agent_config?.output_contract || []),
    ...(merchantAnalysis.agent_config?.guardrails || []),
    merchantAnalysis.execution_brief?.sell,
    merchantAnalysis.execution_brief?.buyer,
    merchantAnalysis.execution_brief?.deliverable,
    merchantAnalysis.execution_brief?.price_test,
    merchantAnalysis.execution_brief?.first_channel,
    merchantAnalysis.execution_brief?.first_message,
    ...(merchantAnalysis.execution_brief?.data_to_track || []),
    merchantAnalysis.execution_brief?.success_threshold,
    merchantAnalysis.execution_brief?.stop_threshold,
    ...(merchantAnalysis.customer_scenarios || []).flatMap((item) => [item.segment, item.pain, item.use_case, item.where_to_find]),
    ...(merchantAnalysis.offer_packages || []).flatMap((item) => [item.name, item.price, item.deliverable, item.buy_trigger]),
    ...(merchantAnalysis.next_actions || []).flatMap((item) => [item.step, item.output, item.done_when]),
    merchantAnalysis.opportunity_summary,
    merchantAnalysis.what_it_is,
    merchantAnalysis.why_opportunity,
    merchantAnalysis.merchant_take,
    merchantAnalysis.source_context,
    merchantAnalysis.what_to_sell,
    merchantAnalysis.who_pays,
    merchantAnalysis.why_they_pay,
    merchantAnalysis.first_test,
    ...(merchantAnalysis.validation_plan || []),
    ...(merchantAnalysis.no_go_signals || []),
    ...(merchantAnalysis.business_angles || []),
    ...(merchantAnalysis.who_needs_it || [])
  ].join("\n");

  assertChineseNarrative(merchantAnalysis.what_it_is, `${context}: what_it_is`, 180);
  assertChineseNarrative(merchantAnalysis.why_opportunity, `${context}: why_opportunity`, 120);
  assertChineseNarrative(merchantAnalysis.merchant_take, `${context}: merchant_take`, 150);
  assertChineseNarrative(merchantAnalysis.source_context, `${context}: source_context`, 100);
  assertChineseNarrative(merchantAnalysis.execution_brief?.first_message, `${context}: first_message`, 120);
  assert(Array.isArray(merchantAnalysis.customer_scenarios) && merchantAnalysis.customer_scenarios.length >= 3, `${context}: missing concrete customer_scenarios`);
  assert(Array.isArray(merchantAnalysis.offer_packages) && merchantAnalysis.offer_packages.length >= 3, `${context}: missing offer_packages`);
  assert(Array.isArray(merchantAnalysis.next_actions) && merchantAnalysis.next_actions.length >= 4, `${context}: missing next_actions`);
  assert(!/Prediction market leading-signal watch/i.test(combined), `${context}: raw English playbook leaked`);
  assert(!/Hantavirus pandemic in 2026\?/i.test(combined), `${context}: raw English market title leaked`);

  const requiredTerms = [
    "\u6c49\u5766\u75c5\u6bd2",
    "\u4e16\u536b\u7ec4\u7ec7",
    "Polymarket",
    "\u6982\u7387",
    "\u6210\u4ea4\u91cf",
    "\u6d41\u52a8\u6027",
    "\u4e2d\u6587\u4e8b\u4ef6\u76d1\u63a7\u9875",
    "\u89e6\u8fbe\u8bdd\u672f",
    "\u6d4b\u8bd5\u4ef7",
    "\u4ea4\u4ed8\u7269",
    "72 \u5c0f\u65f6"
  ];
  for (const term of requiredTerms) {
    assert(combined.includes(term), `${context}: missing specific term ${term}`);
  }
}

function assertClearDetailVerdict(verdict, context) {
  assert(verdict && typeof verdict === "object", `${context}: missing detail_verdict`);
  assert(verdict.analysis_version === "opportunity_verdict_v1", `${context}: expected opportunity_verdict_v1`);
  assert(["可执行", "需验证", "仅观察", "应放弃"].includes(verdict.label), `${context}: invalid label`);
  assert(verdict.label === "仅观察", `${context}: hantavirus market should be observation, got ${verdict.label}`);
  assert(String(verdict.headline || "").length >= 12 && String(verdict.headline || "").length <= 80, `${context}: headline must be short and clear`);
  assert(String(verdict.summary || "").length >= 20 && String(verdict.summary || "").length <= 180, `${context}: summary must be concise`);
  assert(Array.isArray(verdict.why) && verdict.why.length >= 2 && verdict.why.length <= 4, `${context}: why must have 2-4 items`);
  assert(Array.isArray(verdict.next_steps) && verdict.next_steps.length > 0 && verdict.next_steps.length <= 3, `${context}: next_steps must have at most 3 items`);
  assert(Array.isArray(verdict.missing_evidence) && verdict.missing_evidence.length >= 2 && verdict.missing_evidence.length <= 4, `${context}: missing_evidence must have 2-4 items`);
  assert(Array.isArray(verdict.evidence_facts) && verdict.evidence_facts.length >= 3, `${context}: evidence_facts missing`);

  const combined = [
    verdict.headline,
    verdict.summary,
    verdict.do_not_do,
    ...(verdict.why || []),
    ...(verdict.next_steps || []),
    ...(verdict.missing_evidence || []),
    ...(verdict.evidence_facts || []).flatMap((item) => [item.label, item.value])
  ].join("\n");

  for (const term of ["不是可直接执行机会", "单一来源", "当前 Yes 概率", "第二来源", "3 个目标客户"]) {
    assert(combined.includes(term), `${context}: missing clear verdict term ${term}`);
  }
  assert(!/测试价|报价|定制清单|第一条触达话术|中文事件监控页样张/.test(combined), `${context}: verdict still reads like sales copy`);
  assert(!/Prediction market leading-signal watch|Hantavirus pandemic in 2026\?/i.test(combined), `${context}: raw English leaked`);
}

function assertFabraixDetail(verdict, context) {
  assert(verdict && typeof verdict === "object", `${context}: missing detail_verdict`);
  assert(verdict.label === "需验证", `${context}: Fabraix should need validation, got ${verdict.label}`);
  assert(verdict.detail_story && typeof verdict.detail_story === "object", `${context}: missing detail_story`);
  const combined = [
    verdict.headline,
    verdict.summary,
    verdict.detail_story.what_it_is,
    verdict.detail_story.why_it_matters,
    verdict.detail_story.opportunity_angle,
    verdict.detail_story.current_limit,
    verdict.key_question,
    ...(verdict.next_steps || []),
    ...(verdict.missing_evidence || []),
    ...(verdict.evidence_facts || []).flatMap((item) => [item.label, item.value])
  ].join("\n");
  for (const term of ["Fabraix", "Product Hunt", "AI Agent", "上线前", "测试清单", "评论", "定价"]) {
    assert(combined.includes(term), `${context}: missing concrete detail term ${term}`);
  }
  assert(!/可以小步执行，但仍要按证据推进|这条机会已有基本证据|目标行业用户|可验证的小产品、服务包或线索清单/.test(combined), `${context}: generic detail copy leaked`);
  assert((verdict.next_steps || []).length <= 3, `${context}: too many next steps`);
}

function assertActionSummary(summary, context) {
  assert(summary && typeof summary === "object", `${context}: missing action_summary`);
  assert(summary.opportunity && typeof summary.opportunity === "string", `${context}: missing opportunity`);
  assert(summary.info_gap && typeof summary.info_gap === "string", `${context}: missing info_gap`);
  assert(summary.first_step && typeof summary.first_step === "string", `${context}: missing first_step`);
  assert(Array.isArray(summary.validation_plan) && summary.validation_plan.length > 0, `${context}: missing validation_plan`);
  assert(Array.isArray(summary.no_go_signals) && summary.no_go_signals.length > 0, `${context}: missing no_go_signals`);
  assert(summary.budget && typeof summary.budget === "string", `${context}: missing budget`);
  assert(summary.roi && typeof summary.roi === "string", `${context}: missing roi`);
  assert(summary.execution_stage && typeof summary.execution_stage === "string", `${context}: missing execution_stage`);
  assertChineseNarrative(summary.opportunity, `${context}: opportunity`, 150);
  assertChineseNarrative(summary.info_gap, `${context}: info_gap`, 90);
  assertChineseNarrative(summary.what_to_sell, `${context}: what_to_sell`, 42);
  assertChineseNarrative(summary.who_pays, `${context}: who_pays`, 34);
  assertChineseNarrative(summary.first_step, `${context}: first_step`, 42);
}

async function main() {
  const opportunities = await request("/opportunities?sort=score&limit=5");
  const first = opportunities.items?.[0];
  assert(first?.id, "opportunity list is empty");
  assertActionSummary(first.action_summary, "list item");
  assert(!/[A-Za-z]{4,}\/[A-Za-z0-9_-]{4,}/.test(first.business_title || ""), "list item: business_title contains raw English repo identifier");
  assert(Array.isArray(first.strategies) && first.strategies.length > 0, "list item: strategies missing");
  assert(first.estimated_investment, "list item: estimated_investment missing");
  assert(first.roi_ratio, "list item: roi_ratio missing");

  const detail = await request(`/opportunities/${first.id}`);
  assertActionSummary(detail.opportunity?.action_summary, "detail opportunity");
  assertChineseNarrative(detail.opportunity.action_summary.first_step, "detail opportunity: first_step", 42);

  const largerPool = await request("/opportunities?sort=score&limit=100");
  const predictionItem = largerPool.items?.find((item) => String(item.source || "").includes("Polymarket"));
  assert(predictionItem?.id, "polymarket opportunity missing from acceptance sample");
  assertActionSummary(predictionItem.action_summary, "polymarket list item");
  assertSpecificPredictionMarket(predictionItem.action_summary, predictionItem.business_title || predictionItem.title || "", "polymarket list item");
  const predictionDetail = await request(`/opportunities/${predictionItem.id}`);
  assertSpecificPredictionMarket(
    predictionDetail.opportunity?.action_summary,
    predictionDetail.opportunity?.business_title || predictionDetail.opportunity?.title || "",
    "polymarket detail opportunity"
  );
  const hantavirusDetail = await request("/opportunities/op-live-223693ecf77b164fc8");
  assertClearDetailVerdict(hantavirusDetail.opportunity?.detail_verdict, "hantavirus detail verdict");
  assertSpecificMerchantAnalysis(hantavirusDetail.evidence?.merchant_analysis, "hantavirus merchant analysis");
  const fabraixDetail = await request("/opportunities/op-live-33149f4508845988b0");
  assertFabraixDetail(fabraixDetail.opportunity?.detail_verdict, "fabraix detail verdict");

  const actions = await request("/actions?limit=5");
  const action = actions.items?.[0];
  assert(action?.id, "action list is empty");
  assert(action.opportunity_title && typeof action.opportunity_title === "string", "action: missing opportunity_title");
  assert(action.current_step_label && typeof action.current_step_label === "string", "action: missing current_step_label");
  assert(action.next_step_label && typeof action.next_step_label === "string", "action: missing next_step_label");
  assert(action.success_metric && typeof action.success_metric === "string", "action: missing success_metric");

  console.log("[OK] opportunity action summary API acceptance");
}

main().catch((error) => {
  console.error(`[FAIL] ${error.message}`);
  process.exitCode = 1;
});
