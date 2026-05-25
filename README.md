# InfoEdge

InfoEdge 是一个面向趋势发现、机会评估和风险监控的情报工作台。项目把公开数据源、需要授权的数据源、第三方采集源和受限平台源统一整理到一个前端数据源界面，并通过 FastAPI 后端做数据采集、标准化、评分和仪表盘输出。

当前仓库地址：

https://github.com/gaoyu666/xxc1

仓库是私有仓库。团队成员需要先接受 GitHub 邀请，才能 clone、push 分支和提交 Pull Request。

## 功能概览

- 数据源看板：展示数据源总览、实际可拉取源、待授权源、第三方/受限源。
- 趋势与机会工作台：从新闻、社区、开源项目、金融、地缘、供应链、自然灾害等信号中生成机会卡片。
- 后端采集管线：FastAPI 服务负责数据源拉取、规范化、缓存、评分和 API 输出。
- 模型配置界面：支持后续配置 GLM / OpenAI-compatible 模型调用。
- 团队协作基础：仓库已排除本地 `.env`、依赖目录、构建目录、日志和测试产物。

## 技术栈

- Frontend: React 19, TypeScript, Vite, Recharts, lucide-react
- Backend: Python, FastAPI, SQLAlchemy, Redis, PostgreSQL
- Tests: TypeScript build, Python unittest, Playwright acceptance scripts

## 项目结构

```text
.
├── src/                       # React 前端
├── backend/
│   ├── app/                   # FastAPI 应用、API、采集管线、数据模型
│   ├── tests/                 # 后端测试
│   ├── .env.example           # 后端环境变量模板
│   └── requirements.txt       # 后端依赖
├── scripts/                   # 前端/API 验收脚本
├── package.json               # 前端依赖与脚本
├── tsconfig.json
└── README.md
```

## 本地开发

### 1. 拉取代码

```powershell
git clone https://github.com/gaoyu666/xxc1.git
cd xxc1
```

### 2. 启动前端

```powershell
npm install
npm run dev
```

默认前端地址：

```text
http://localhost:5173
```

前端默认会尝试连接本地后端：

```text
http://127.0.0.1:8000
http://localhost:8000
```

如果需要指定后端地址，可以在根目录创建本地环境文件，例如：

```powershell
echo VITE_API_BASE_URL=http://127.0.0.1:8000 > .env.local
```

`.env.local` 不要提交到 GitHub。

### 3. 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

默认后端地址：

```text
http://127.0.0.1:8000
```

健康检查：

```text
GET http://127.0.0.1:8000/api/health
```

## 环境变量

后端环境变量模板在：

```text
backend/.env.example
```

每个开发者需要自己复制一份：

```powershell
cd backend
copy .env.example .env
```

必填或常用配置：

```text
PG_USER
PG_PASSWORD
PG_HOST
PG_PORT
PG_DB

REDIS_HOST
REDIS_PORT
REDIS_PASSWORD
REDIS_DB
```

可选授权数据源和模型配置：

```text
APIFY_TOKEN
GLM_API_KEY
GLM_BASE_URL
GLM_MODEL
```

注意：

- 不要提交 `backend/.env`。
- 不要把数据库密码、Redis 密码、API Key 写进代码。
- 需要共享真实密钥时，用团队认可的安全渠道单独分发。

## 数据源说明

前端数据源界面当前登记了 150 个数据源条目：

```text
61  个公共/可尝试拉取候选源
59  个需要 Key、Token、账号或 relay 配置的数据源
28  个第三方/待接入数据源
2   个受限平台源
```

后端当前采集管线里：

```text
43 个 live connector 会被实际采集函数使用
67 个 connector catalog 条目会进入数据源目录
66 个 gated source 条目需要授权或额外配置后才能启用
```

状态含义：

- `pending`：公开源或可尝试拉取源，通常不需要 API Key，但仍可能受网络、限流或地区影响。
- `needs_config`：需要 API Key、Token、账号、代理、relay 或供应商授权。
- `third_party`：已列入目录，但通常还需要第三方库、专用 connector、缓存或合规处理。
- `restricted`：平台限制较强，不建议直接爬取，优先使用授权接口或数据服务商。

数据源相关代码主要在：

```text
backend/app/services/real_pipeline.py
backend/app/services/sources/
src/main.tsx
```

## 常用命令

前端构建：

```powershell
npm run build
```

后端数据源扩展测试：

```powershell
cd backend
python -m unittest tests.test_source_expansion -v
```

前端 API 验收脚本：

```powershell
npm run accept:opportunity-actions:api
npm run accept:buttons:api
```

## 团队协作流程

不要直接在 `main` 上开发。推荐流程：

```powershell
git checkout main
git pull
git checkout -b feature/your-feature-name
```

开发完成后：

```powershell
git status
git add .
git commit -m "Describe your change"
git push -u origin feature/your-feature-name
```

然后在 GitHub 上创建 Pull Request，等待 review 后再合并到 `main`。

分支命名建议：

```text
feature/xxx   新功能
fix/xxx       修复
chore/xxx     工程配置、依赖、文档
docs/xxx      文档
```

提交前至少确认：

```powershell
npm run build
cd backend
python -m unittest tests.test_source_expansion -v
```

## GitHub 邀请

新成员需要把 GitHub 用户名发给仓库管理员。管理员在仓库中邀请后，成员可以通过以下方式接受：

- 打开仓库地址：https://github.com/gaoyu666/xxc1
- 查看 GitHub 右上角通知
- 查看 GitHub 绑定邮箱里的邀请邮件

必须用被邀请的 GitHub 账号登录，否则看不到邀请。

## 安全规则

已经被 `.gitignore` 排除的内容包括：

```text
node_modules/
dist/
backend/.venv/
backend/.env
*.log
*.err
*.out
test-results/
screenshots/
.omx/
```

如果不确定某个文件能不能提交，先不要 `git add .`，可以先运行：

```powershell
git status --short
```

再和团队确认。
