# InfoEdge 产品规格摘要

InfoEdge 是一个面向开源维护者、研究者和小团队的情报工作台，用于把公开数据源、授权数据源和第三方 connector 统一组织成可验证的趋势信号、机会评分和风险提示。

## 目标

- 建立一个公开、可维护的数据源目录。
- 区分 public、needs_config、third_party、restricted 等来源状态。
- 用 FastAPI 后端统一采集、规范化、缓存和评分。
- 用 React/Vite 前端展示仪表盘、机会池、数据源状态和配置入口。
- 让 connector 扩展、测试和审查流程适合外部贡献者参与。

## 非目标

- 不提交真实 API key、cookie、账号凭据或私有数据。
- 不绕过平台限制抓取 restricted source。
- 不把静态 demo 伪装成完整生产环境。
- 不把模型输出作为自动投资或商业决策依据。

## 用户场景

1. 维护者希望快速查看哪些数据源可公开采集、哪些需要授权。
2. 贡献者希望添加一个新 source connector，并通过离线 fixture 测试验证规范化结果。
3. 研究者希望从新闻、开源项目、社媒热榜、灾害、金融和供应链信号中发现趋势。
4. 项目 owner 希望用 CI、issue、release 和 demo 保持项目可持续维护。

## 核心模块

### 前端工作台

- 仪表盘：展示信号数、数据源状态、趋势和平台分布。
- 机会池：展示机会评分、验证状态、风险和执行摘要。
- 数据源：展示 source registry、授权需求和状态解释。
- 设置：配置模型供应商和后端连接。

### 后端 API

- FastAPI 提供 dashboard、signal、source、settings 等接口。
- PostgreSQL 存储业务数据。
- Redis 用于缓存和后续队列能力。
- OpenAI-compatible provider 设置用于可选分析能力。

### Source Connector

Connector 应遵守：

- public source 可以在无凭据情况下测试。
- needs_config source 必须保留授权说明，未配置时不能进入 live collection。
- restricted source 只做目录说明，除非有明确授权。
- 测试覆盖 source_item_id、URL、timestamp、metrics、payload 和 malformed payload。

## 当前状态

- Public repository: `gaoyu666/infoedge`
- License: MIT
- Demo: `https://gaoyu666.github.io/infoedge/`
- CI: frontend build + backend source-expansion tests
- Releases: `v0.1.0`, `v0.1.1`
- Roadmap: `ROADMAP.md`
- Architecture: `docs/ARCHITECTURE.md`

## 近期路线

- Connector health status 和 refresh metadata。
- 更多 connector normalization fixtures。
- 更清晰的 backend offline / static demo 空状态。
- 更完整的部署说明和 source compliance review。
