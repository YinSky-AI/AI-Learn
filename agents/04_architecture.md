# 架构设计 (04)

> **文件标识**: agents/04_architecture.md
> **关联文件**: 引用 00_project_overview.md、01_feature_design.md、03_tech_stack.md；被 05_implementation_steps.md、06_sub_agent_tasks.md 引用。

---

## 1. 系统架构总览

```
+-- 客户端层 -----------------------------------+
|   Web App (Next.js SSR + CSR)                  |
|   Mobile / Tablet / Desktop 自适应              |
+-----------------------+------------------------+
                        | HTTPS / WSS
+-- API 网关层 ---------v------------------------+
|   Nginx (反向代理 + SSL 终结 + 静态资源缓存)      |
+-----------------------+------------------------+
                        |
+-- 应用层 --------------v------------------------+
|   FastAPI Server                                |
|   +-- REST API (/api/v1/*)                      |
|   +-- SSE 端点 (/api/v1/ai/stream)              |
|   +-- WebSocket (/api/v1/ws/*)                  |
|   +-- 中间件 (认证/限流/日志/CORS)              |
+--------+---------------+-----------------------+
         |               |
+--------v------+  +-----v---------+
|  AI Harness   |  | Content API   |
|  (出题编排)    |  | (课程/主题筛选) |
+---------------+  +---------------+
         |               |
+--------v---------------v--------+
|   Service Layer (业务逻辑)       |
|   UserService                   |
|   LearningService               |
|   QuestionGenerationService      |
|   QuestionMemoryService          |
|   ProgressService               |
|   AchievementService            |
+--------+-----------------------+
         |
+--------v-----------------------+
|   Data Layer                    |
|   SQLAlchemy ORM + Alembic      |
|   PostgreSQL + Redis            |
+--------------------------------+
```

---

## 2. 模块划分

### 2.1 前端模块

| 模块 | 路径 | 职责 |
|------|------|------|
| auth | features/auth | 注册、登录、Token 管理 |
| discover | features/discover | 知识探索、筛选、搜索 |
| learning | features/learning | 学习引擎：阅读 + 问答 + 游戏 |
| ai-assistant | features/ai-assistant | AI 助手对话浮窗 |
| profile | features/profile | 个人中心、设置 |
| progress | features/progress | 学习进度、成就展示 |
| theme | lib/theme | 年龄分级主题系统 |
| content | lib/content | 内容获取与缓存 |
| api-client | lib/api | API 客户端封装 |

### 2.2 后端模块

| 模块 | 路径 | 职责 |
|------|------|------|
| auth | api/auth.py, services/auth.py | 认证注册、JWT |
| users | api/users.py, models/user.py | 用户管理 |
| content | api/content.py, services/content.py | 知识内容 CRUD、筛选 |
| learning | api/learning.py, services/learning.py | 学习记录、答题判定 |
| progress | api/progress.py, services/progress.py | 进度追踪、知识图谱 |
| ai | ai/harness.py, ai/agents/*, ai/tools/*, ai/prompts.py | AI 出题编排、Prompt 管理、工具调用 |
| question-generation | api/questions.py, services/question_generation.py | AI 动态出题、题目质量检查、题目保存 |
| question-memory | services/question_memory.py | 生成题目知识库检索、历史生成题检索、错题变式、重复度检查 |
| achievement | api/achievement.py, services/achievement.py | 积分、成就 |

---

## 3. 数据流

### 3.1 学习主流程

```
用户选择内容 -> GET /api/v1/content/:id
  -> 后端返回内容 + 题目
  -> 前端渲染 (阅读/问答)
  -> 用户作答 -> POST /api/v1/learning/answer
  -> 后端判定正误 -> 更新学习记录
  -> 返回判定结果 + 反馈文案
  -> 前端展示正误 + 反馈动画
  -> (可选) 触发 AI 错题解析 -> SSE 流式返回
```

### 3.2 AI 助手流程

```
用户点击 AI 助手 -> 浮窗展开
  -> 加载上下文 (当前知识点 + 学习历史)
  -> 用户输入问题 -> POST /api/v1/ai/ask
  -> 后端组装 Prompt (含年龄分级 + 难度适配)
  -> 调用 OpenAI API -> 流式输出到 SSE
  -> 前端打字机效果展示
  -> 对话记录存入 Redis (临时) + PostgreSQL (持久)
```

### 3.3 AI 动态出题流程

v0.1 不依赖预置教材知识库，也不实现联网搜索。出题流程由 AI Harness 编排，输入来自用户课程选择、学习历史和使用过程中沉淀的生成题目知识库，输出为可保存、可答题、可复查的中文结构化题目。

```
用户选择课程参数
  -> POST /api/v1/questions/generate
  -> QuestionGenerationService 校验请求
  -> AI Harness 启动 run
     1. CourseIntentAgent: 理解/补齐年龄、学科、主题、难度、题型、数量
     2. QuestionPlannerAgent: 规划题型和难度分布
     3. QuestionMemoryAgent: 检索生成题目知识库中的历史生成题、错题、近期练习，形成去重上下文
     4. QuestionGeneratorAgent: 生成题目、选项、答案、解析
     5. QualityCheckAgent: 检查答案正确性、适龄性、难度匹配、重复度
     6. ToolHarness: 保存题目、保存生成日志、保存质量检查结果
     7. SafetyAuditAgent: 四维安全审查（适龄性/准确性/公平性/隐私），独立否决
     8. FeedbackAggregator: 汇聚偏差信号，计算PID，生成ControlSignal
     9. ToolHarness: 保存题目、保存生成日志、保存质量检查结果、保存安全审查结果
  -> 返回 generation_batch_id + questions[]
  -> ControlSignal 注入下一次生成循环的 QuestionPlannerAgent 和 QuestionGeneratorAgent
```

### 3.4 Harness 职责边界

| 层 | 职责 | 不负责 |
|----|------|--------|
| AI Harness | 编排 Agent、工具调用、日志、错误恢复 | 直接处理 HTTP 请求、直接写业务表 |
| CourseIntentAgent | 理解课程选择，补齐结构化参数 | 生成题目 |
| QuestionPlannerAgent | 规划题目数量、题型、难度分布 | 保存题目 |
| QuestionMemoryAgent | 检索生成题目知识库、历史生成题、错题、用户习惯 | 判断答案正误 |
| QuestionGeneratorAgent | 生成题目、答案、解析 | 检索数据库 |
| QualityCheckAgent | 检查适龄性、答案、难度、重复度 | 修改学习进度 |
| Tool Middleware | 提供检索、保存、日志等副作用工具 | 做推理决策 |
| SafetyAuditAgent | 内容安全四维审查，独立否决权 | 修改题目、生成题目 |
| QualityReviewAgent | 深度质量评估+趋势分析+反馈信号 | 修改题目、快检 |
| FeedbackAggregator | PID计算、状态观测、控制信号生成 | 直接处理HTTP请求、LLM推理 |
| SummaryAgent | 会话记忆提炼、Skill创建/自改进、用户建模 | 直接处理HTTP请求、生成题目 |
| ErrorLogger | 实时错误捕获、分类、路由、持久化 | 修复错误（只分类和路由） |
| LearningService | 学习会话、答题记录、正误判定 | 生成题目 |

### 3.5 闭环反馈数据流

```
QualityCheckAgent.QuickCheckResult + SafetyAuditAgent.SafetyAuditResult
  -> FeedbackAggregator
    -> 计算 PID（P=当前批次通过率偏差，I=历史偏差累积，D=质量变化速率）
    -> 生成 ControlSignal
  -> 注入下一次生成循环:
    -> QuestionPlannerAgent: 调整题型分布和难度比例
    -> QuestionMemoryAgent: 调整去重阈值和检索范围
    -> QuestionGeneratorAgent: 调整生成策略参数
```

### 3.6 自进化数据流

```
会话结束
  -> SummaryAgent
    -> 提炼 MemoryItem -> 写入 SessionMemory（PostgreSQL）
    -> 评估并创建/更新 SkillFile -> 写入 Skill 存储目录
    -> 更新 UserProfileUpdate -> 写入 User 表
  -> 新会话开始时
    -> FTS 检索 SessionMemory 中相关记忆
    -> 注入 QuestionMemoryAgent 的上下文
```

---

## 4. API 契约概览

### 4.1 公开接口

| Method | Path | 说明 |
|--------|------|------|
| POST | /api/v1/auth/register | 注册 |
| POST | /api/v1/auth/login | 登录 |
| POST | /api/v1/auth/refresh | 刷新 Token |

### 4.2 内容接口

| Method | Path | 说明 |
|--------|------|------|
| GET | /api/v1/content/tree | 知识树结构 |
| GET | /api/v1/content/search?q=&age=&subject=&type=&difficulty= | 筛选内容列表 |
| GET | /api/v1/content/:id | 内容详情 |

### 4.3 学习接口

| Method | Path | 说明 |
|--------|------|------|
| POST | /api/v1/learning/start | 开始学习会话 |
| POST | /api/v1/learning/answer | 提交答案 |
| GET | /api/v1/learning/history | 学习历史 |
| GET | /api/v1/progress/:userId | 学习进度 |

### 4.4 AI 接口

| Method | Path | 说明 |
|--------|------|------|
| POST | /api/v1/ai/explain | 知识点讲解 (非流式) |
| POST | /api/v1/ai/stream | AI 流式对话 (SSE) |
| POST | /api/v1/ai/error-analysis | 错题解析 |

### 4.5 AI 出题接口

| Method | Path | 说明 |
|--------|------|------|
| POST | /api/v1/questions/generate | 根据课程选择生成题目批次 |
| GET | /api/v1/questions/batches/:id | 查询某次生成批次、题目、质量检查结果 |
| POST | /api/v1/questions/:id/variant | 基于历史题或错题生成变式题 |
| GET | /api/v1/questions/history | 查询用户历史生成题和练习记录 |

### 4.6 AI 审计与进化接口

| Method | Path | 说明 |
|--------|------|------|
| GET | /api/v1/ai/skills | 查询当前 Skill 库 |
| GET | /api/v1/ai/skills/:name | 查询单个 Skill 详情 |
| GET | /api/v1/ai/user-profile/:userId | 查询用户行为模型 |
| GET | /api/v1/ai/evolution/log | 查询自进化记录 |
| GET | /api/v1/ai/error-log | 查询错误日志（支持按类型/严重度/时间筛选） |

---

## 5. 错误码体系

| 错误码 | 含义 | HTTP 状态码 |
|--------|------|------------|
| AUTH_001 | Token 无效 | 401 |
| AUTH_002 | Token 过期 | 401 |
| AUTH_003 | 无权限 | 403 |
| VAL_001 | 参数校验失败 | 422 |
| VAL_002 | 资源不存在 | 404 |
| BIZ_001 | 业务逻辑错误 | 400 |
| SYS_001 | 内部服务错误 | 500 |
| SYS_002 | AI 服务超时 | 503 |
| RATE_001 | 请求频率超限 | 429 |

---

## 6. 部署架构

```
+-- 生产环境 ----------------------------------+
|   Docker Compose / k8s (v0.1 用 Compose)     |
|   +-- Nginx (端口 80/443)                     |
|   +-- Next.js App (端口 3000)                  |
|   +-- FastAPI (端口 8000, 4 workers)           |
|   +-- PostgreSQL (端口 5432)                  |
|   +-- Redis (端口 6379)                       |
+----------------------------------------------+
```
