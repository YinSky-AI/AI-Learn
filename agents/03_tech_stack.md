# 技术栈决策 (03)

> **文件标识**: agents/03_tech_stack.md
> **关联文件**: 引用 00_project_overview.md；被 04_architecture.md、05_implementation_steps.md 引用。

---

## 1. 技术选型总览

| 层 | 技术 | 版本 | 选型理由 |
|----|------|------|---------|
| 前端框架 | Next.js | 14+ | SSR + CSR 混合，SEO 友好，React 生态 |
| 前端语言 | TypeScript | 5+ | 类型安全，减少运行时错误 |
| UI 组件 | shadcn/ui + Tailwind CSS | latest | 可定制性强，组件质量高，Tree-shaking 友好 |
| 状态管理 | Zustand | 4+ | 轻量、无 boilerplate、React 18 兼容 |
| 动画 | Framer Motion | 10+ | 声明式动画，易用性强 |
| 后端框架 | FastAPI | 0.110+ | 异步原生，自动 OpenAPI 文档，性能优 |
| 后端语言 | Python | 3.12+ | AI 生态丰富，类型提示支持好 |
| ORM | SQLAlchemy 2.0 + Alembic | latest | 成熟稳定，异步支持，迁移管理 |
| 数据库 | PostgreSQL | 16 | 功能丰富，JSONB 支持，全文检索 |
| 缓存 | Redis | 7+ | 会话管理、缓存加速、限流 |
| AI API | OpenAI GPT-4o | latest | 最强通用能力，函数调用，流式输出 |
| AI SDK | 原生 API 优先，LangChain 可选 | latest | v0.1 需要可控、可审计的出题链路，避免过早引入重型链式框架 |
| AI Harness | 自研轻量 Harness | v0.1 | 编排多层 Agent、工具调用、日志和质量检查 |
| 生成题目知识库检索 | PostgreSQL tsvector + pg_trgm | 16 | v0.1 保存并检索用户使用过程中沉淀的历史生成题，避免重复；暂不引入独立向量数据库 |
| 外置文档数据库 | - | - | v0.1 暂不预置教材库或接入外部文档知识库 |
| 容器化 | Docker + docker-compose | latest | 环境一致性，一键部署 |
| CI/CD | GitHub Actions | - | 自动测试 + 自动部署 |

---

## 2. 前端技术细节

### 2.1 项目结构

```
frontend/
  src/
    app/              # Next.js App Router 页面
    components/       # 通用组件 (ui/ 来自 shadcn)
    features/         # 功能模块 (按领域组织)
    hooks/            # 通用 Hooks
    lib/              # 工具函数、API 客户端
    stores/           # Zustand 状态管理
    types/            # TypeScript 类型定义
    content/          # 知识内容数据 (JSON/MD)
  public/             # 静态资源
  tests/              # 测试
```

### 2.2 关键依赖

- next: ^14.2
- react: ^18.3
- tailwindcss: ^3.4
- zustand: ^4.5
- framer-motion: ^10.18
- @tanstack/react-query: ^5 (服务端状态)
- lucide-react: 图标库
- katex: 数学公式渲染
- react-markdown: Markdown 渲染

### 2.3 年龄分级 UI 策略

前端维护四个年龄主题包，通过 Context 切换：

```
themes/
  age_06_09/   # 卡通风格、大圆角、高饱和度
  age_10_12/   # 活泼风格、中等圆角
  age_13_15/   # 简约风格、小圆角
  age_16_18/   # 极简风格、直边为主
```

每个主题包包含：颜色、字号、间距、圆角、动画速度、组件变体。

---

## 3. 后端技术细节

### 3.1 项目结构

```
backend/
  app/
    api/              # API 路由
    core/             # 配置、依赖注入
    models/           # SQLAlchemy 模型
    schemas/          # Pydantic 模型
    services/         # 业务逻辑
    ai/               # AI 集成层
    content/          # 内容管理
    utils/            # 工具函数
    migrations/       # Alembic 迁移
  tests/
  Dockerfile
```

### 3.2 API 设计规范

- RESTful 风格，版本前缀 /api/v1/
- 统一响应格式: { code, message, data, meta }
- 认证: JWT Token (access + refresh)
- 分页: cursor-based 分页（内容列表类）
- 错误处理: 全局异常处理器，结构化错误码

### 3.3 AI 集成

- 封装 AI Service 层，支持多 Provider 切换
- Prompt 模板管理：按年龄分级 + 难度 + 学科 组合
- 流式输出支持 Server-Sent Events (SSE)
- 上下文窗口管理：控制 Token 消耗
- 速率限制：基于 Redis 的滑动窗口限流
- v0.1 不实现联网搜索；AI 出题仅基于用户课程选择、生成题目知识库和模型生成能力
- 采用轻量 Harness 编排层，将 Query 理解、出题计划、题目生成、生成题目知识库检索、质量检查拆成独立步骤

### 3.4 AI 出题 Harness 结构

```
backend/app/ai/
  harness.py                 # 编排入口，负责步骤调用、错误处理、日志
  agents/
    course_intent.py         # 小模型/低成本模型：理解课程选择，补齐结构化参数
    question_planner.py      # 制定题目数量、题型、难度分布
    question_generator.py    # 生成题目、答案、解析
    question_memory.py       # 检索生成题目知识库中的历史生成题和错题，提供去重上下文
    quality_checker.py       # 检查答案、适龄性、难度、重复度
  tools/
    question_memory_tool.py  # 生成题目知识库检索工具
    question_save_tool.py    # 题目保存工具
    audit_log_tool.py        # 工具调用和 AI 步骤日志
    error_logger.py              # 错误日志中间件（ErrorLogger）
    safety_auditor.py             # 安全审计 Agent（SafetyAuditAgent）
    quality_reviewer.py           # 质量审查 Agent（QualityReviewAgent）
    summary.py                    # 总结 Agent（SummaryAgent）
    feedback_aggregator.py        # 反馈聚合器（FeedbackAggregator，内嵌于 Harness）
    skills/                       # Skill 文件存储目录
    evolution/                    # 进化记录目录
  prompts/
    question_generation/     # 出题 Prompt 模板
    quality_check/           # 质量检查 Prompt 模板
```

**职责边界**:
- Harness 只负责编排，不直接写业务数据库；持久化通过工具或 Service 完成。
- Agent 只负责单一推理任务，不直接调用外部系统。
- Tool 负责可审计的副作用，如检索、保存、写日志。
- LearningService 负责学习会话和答题判定，不负责生成题目。
- v0.1 不接搜索 API、不爬网页、不构建外置教材/外部文档知识库；但必须保存用户使用过程中生成的题目，形成可检索的生成题目知识库。

### 3.5 错误日志基础设施

**ErrorLogger 中间件模式**: ErrorLogger 作为 FastAPI 中间件嵌入 AI Harness，拦截所有 Agent 步骤的异常和错误信号，按以下四类分类处理：

| 错误分类 | 编码 | 说明 | 路由目标 |
|---------|------|------|---------|
| SAFE_AUDIT | E_SAFE | 安全审查不通过，题目被否决 | SafetyAuditAgent（记录+统计） |
| QUALITY_FAIL | E_QUAL | 质量检查不通过，题目被退回 | QualityReviewAgent（趋势分析） |
| PERF_DEGRADE | E_PERF | 性能指标下降（延迟/错误率） | FeedbackAggregator（PID调整） |
| LOGIC_ERROR | E_LOGIC | Agent 逻辑错误或 LLM 输出异常 | ErrorLogger（持久化+告警） |

**存储**: 所有错误记录写入 PostgreSQL `error_log` 表，包含错误分类、严重度、Agent 标识、批次 ID、原始数据、时间戳。

**路由**: ErrorLogger 根据错误分类将记录路由到对应 Agent 进行进一步分析或处理，但不负责修复错误本身。

### 3.6 自进化基础设施

**Skill 版本管理**:
- 采用文件级版本控制：每个 Skill 文件以 YAML 格式存储，文件名包含版本号（如 `math_fraction_v3.yaml`）。
- 每次更新时备份原版文件至 `evolution/backups/` 目录，保留完整更新历史。
- Skill 元数据中记录创建时间、版本号、适用条件、效果指标。

**记忆 TTL 实现**:
- SessionMemory 记录写入 PostgreSQL 时设置 `expires_at` 字段（默认 90 天）。
- PostgreSQL 定时任务（pg_cron 或应用层 Cron）每日清理过期记录。
- 清理前将即将过期的记忆标记为"低优先级"，SummaryAgent 可选择性地将高价值记忆升级为长期 Skill。

**进化回滚机制**:
- 系统持续监控最近 72 小时的质量指标趋势（通过率、安全否决率、用户满意度）。
- 若连续指标下降超过阈值，自动触发回滚：恢复最近一个稳定版本的 Skill 文件，并通知管理员。
- 回滚操作记录写入 `evolution/rollback_log/`，包含回滚原因、回滚版本、回滚时间。

---

## 4. 数据库设计原则

- 所有表使用 UUID 主键
- 包含 created_at / updated_at 时间戳
- 软删除使用 deleted_at 字段
- JSONB 存储灵活配置和扩展属性
- 全文检索使用 PostgreSQL tsvector
- 读写分离：主库写入，只读副本查询（v0.1 暂用单库）

---

## 5. 安全准则

- 密码 bcrypt 加密存储
- JWT 密钥环境变量注入
- API 速率限制（每人每分钟 60 次）
- 输入校验（Pydantic / Zod）
- CORS 白名单配置
- SQL 注入防御（ORM 参数化查询）
- XSS 防御（React 默认转义 + Content-Security-Policy）

---

## 6. 开发工具

| 工具 | 用途 |
|------|------|
| ESLint | 前端代码规范 |
| Prettier | 前端代码格式化 |
| Ruff | 后端 Python 代码规范 |
| mypy | Python 类型检查 |
| Husky | Git 提交前钩子 |
| lint-staged | 暂存区文件检查 |
| pytest | 后端测试 |
| Jest + Playwright | 前端 + E2E 测试 |
