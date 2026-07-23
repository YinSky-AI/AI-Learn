# 挑战与练习统一入口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现“每日挑战 / 自定义练习”统一入口，支持年龄段等筛选、每日固定 15 题和 12 分钟、难度分榜、明确题型交互和一空一答，并修复 AI 出题 500。

**Architecture:** 每日挑战从 `Question` 抽题，日期与规范化筛选范围决定一套可重放的 15 题。服务端保存结构化答案并统一计分与排名；`/challenge` 是唯一入口，`/ai-questions` 兼容跳转到自定义模式。

**Tech Stack:** FastAPI、Pydantic v2、SQLAlchemy async、Alembic、PostgreSQL、Next.js、React、TypeScript、Tailwind、pytest、Node test、Docker Compose。

## Global Constraints

- AI 出题只保留“出题 Agent → 审题 Agent”两层；TutorHarness 不参与出题或审题。
- 每日挑战固定 15 题、服务端限时 720 秒；排行榜仅按难度分组，排序为正确率、得分、用时、完成时间。
- 年龄段、学科、主题、题型仅限定题目范围和成绩详情；不增加学段。
- 单选使用 radio 和“单选题 · 请选择 1 项”；多选使用 checkbox 和“多选题 · 可选择多项”；每个填空 blank 独立输入和校验。
- 不泄露正确答案、`answer_key`、堆栈或 SQL；不触碰无关工作区变更。
- 数据库迁移须先在隔离库演练；迁移与 `docker compose up -d --build` 须等待用户对精确数据库目标的授权。

---

### Task 1: 修复认证后 AI 出题的嵌套事务

**Files:**
- Modify: `backend/app/services/question_generation_service.py`
- Modify: `backend/tests/test_question_generation_api.py`

**Interfaces:** 真实 `get_current_user_id()` 已在同一 `AsyncSession` 查询用户并开启隐式事务；`generate_reviewed_batch()` 必须在其内创建 savepoint。

- [ ] 写真实 Bearer token 生成测试，只 monkeypatch `questions_api.get_ai_provider`，不得 override `get_current_user_id`；断言 `/api/v1/questions/generate` 为 200，另测连续审题拒绝为 422 且无 batch 残留。
- [ ] 运行 `pytest backend/tests/test_question_generation_api.py -k real_authenticated -v`，确认旧代码失败于 `InvalidRequestError`。
- [ ] 将 `generate_reviewed_batch()` 的 `async with db.begin():` 改为 `async with db.begin_nested():`，不改认证依赖、`get_db` 或 AI 层级。
- [ ] 运行 `pytest backend/tests/test_question_generation_api.py backend/tests/test_question_pipeline.py -v` 并提交：`fix(ai): support authenticated generation transactions`。

### Task 2: 建立每日挑战 scope、答案和排行榜数据契约

**Files:**
- Modify: `backend/app/models/content.py`
- Modify: `backend/app/models/daily_challenge.py`
- Create: `backend/migrations/primary/versions/lp_0009_daily_challenge_scope_and_answers.py`
- Modify: `backend/tests/test_schema_migration.py`

**Interfaces:** `Question` 新增公开 `answer_schema` 和仅服务端 `answer_key`；challenge 保存 `filter_fingerprint`、年龄段、学科、主题、难度、题型；attempt 保存整数 `accuracy_basis_points`；answer 保存 JSONB `answer_payload`。

- [ ] 先测试模型/迁移含 `answer_schema`、`answer_key`、`filter_fingerprint`、`accuracy_basis_points`、`answer_payload`，唯一约束为 `(challenge_date, filter_fingerprint)`，排行榜索引覆盖 challenge、completed、accuracy、score、time。
- [ ] 实现模型和迁移。旧 challenge 回填 legacy scope；旧填空题变为单空 `blank-1`。多空结构为 `{"blanks":[{"id":"blank-1","position":1},{"id":"blank-2","position":2}]}`，答案键为 `{"blanks":{"blank-1":["答案一"],"blank-2":["答案二"]}}`。
- [ ] 先记录隔离库 host、database、environment、备份和回滚；未授权时不得升级共享数据库。运行 `pytest backend/tests/test_schema_migration.py -v`。
- [ ] 提交：`feat(challenge): persist scoped challenge answers`。

### Task 3: 实现每日挑战筛选、判题和难度排行榜 API

**Files:**
- Modify: `backend/app/api/v1/daily_challenge.py`
- Modify: `backend/app/services/daily_challenge_service.py`
- Modify: `backend/app/services/question_access.py`
- Modify: `backend/app/schemas/content.py`
- Modify: `backend/tests/test_daily_challenge_service.py`
- Create: `backend/tests/test_daily_challenge_api.py`

**Interfaces:** start 接受 `{age_group_code, subject_code, course_topic, difficulty_level, question_types}`，返回固定 15/720、filters 和无答案题目；submit 每题接收 discriminated answer；daily leaderboard 接受 `difficulty_level`。

- [ ] 写失败测试：同日同 filters 重放相同 15 题；不同难度不同 challenge；题库不足 15 安全 422；无答案泄露；排行榜按目标难度和 accuracy→score→time 排序；单选值、多选数组、双空逐空和超时 720 秒结算。
- [ ] 定义 `DAILY_QUESTION_COUNT = 15` 和 `DAILY_TIME_LIMIT_SECONDS = 720`。规范化 filters 后以稳定 JSON + SHA-256 生成 fingerprint；通过 `Question` 与 `KnowledgeNode` 筛出恰好 15 题；不足时不创建 challenge。
- [ ] 公开 payload 仅含 `answer_schema`；结构化 answer 按 kind 判题；完成时设置 `accuracy_basis_points = correct_count * 10_000 // total_count`；`_rank()` 与 `leaderboard()` 复用同一排序表达式。
- [ ] 运行 `pytest backend/tests/test_daily_challenge_service.py backend/tests/test_daily_challenge_api.py backend/tests/test_question_access_api.py -v` 并提交：`feat(challenge): add scoped daily challenge flow`。

### Task 4: 构建统一入口和一空一答组件

**Files:**
- Create: `frontend/src/types/practice.ts`
- Create: `frontend/src/components/practice/practice-filter-form.tsx`
- Create: `frontend/src/components/practice/question-answer-card.tsx`
- Modify: `frontend/src/app/(main)/challenge/page.tsx`
- Modify: `frontend/src/app/(main)/ai-questions/page.tsx`
- Modify: `frontend/src/components/layout/sidebar.tsx`
- Modify: `frontend/src/components/ai/floating-ai-button.tsx`
- Create: `frontend/tests/unified-challenge-practice.test.mjs`
- Create: `frontend/tests/practice-question-answer-card.test.mjs`
- Modify: `frontend/tests/ai-question-generation.test.mjs`
- Modify: `frontend/tests/main-layout-pages.test.mjs`

**Interfaces:** `/challenge?mode=daily|custom` 是唯一 UI；daily 消费 Task 3 API，custom 调用既有 `/v1/questions/generate`；旧 `/ai-questions` 跳转到 custom。

- [ ] 先测试唯一导航、浮动 AI 入口、daily 的 `15 题 · 12 分钟` 与无题数控件、custom 的生成接口、daily start filters；测试 radio、checkbox、`answer_schema.blanks.map()`，且填空答案没有逗号拼接。
- [ ] `practice.ts` 定义 filters、公共题目、blank 和 discriminated answer。筛选表单只有年龄、学科、主题、难度、题型；daily 固定 15，custom 显示题数。
- [ ] 答题卡为受控纯组件：choice 值、multiple 数组、fill blank slots；不得复用会创建 learning session 的 `QuizPractice`。挑战页做 mode container；custom 不写每日榜；ai 页跳转并清理重复导航。
- [ ] 在 `frontend` 运行 `npm test && npm run lint && npm run build` 并提交：`feat(practice): unify challenge and custom practice`。

### Task 5: 适配难度排行榜并完成浏览器验收

**Files:**
- Modify: `frontend/src/app/(main)/leaderboard/page.tsx`
- Create: `frontend/tests/daily-leaderboard.test.mjs`
- Create: `test/acceptance/challenge-and-practice/` 中的截图、控制台和接口记录

**Interfaces:** 仅 daily 榜显示简单/中等/困难并携带 `difficulty_level`；total/streak 不变。

- [ ] 测试 daily 请求包含 `difficulty_level`、total/streak 不带该参数；实现三个难度切换。
- [ ] 获授权后才升级隔离目标并运行 `docker compose up -d --build`、`docker compose ps`、`docker compose logs --tail=200 backend generation-worker frontend nginx-gateway`。
- [ ] 用内部浏览器验收 daily/custom 筛选、15/12、三种作答控件、三个难度榜和 AI 出题；保存截图、控制台和接口状态到验收目录。
- [ ] 运行后端核心 pytest 以及 frontend `npm test && npm run lint && npm run build`，提交：`feat(leaderboard): filter daily rankings by difficulty`。

## Plan Self-Review

- AI 事务、数据结构、后端契约、统一 UI、排行榜与验收均有独立任务和测试门槛。
- 前端只消费 Task 3 定义的契约；未加入学段。
- 数据库写入与 Docker 重建均设置了显式授权门槛。
