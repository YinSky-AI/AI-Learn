# P0/P1 验收遗留项补全实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以当前运行证据补齐 P0/P1 未完成验收项，并让完整交付门禁成为可重复的通过标准。

**Architecture:** 先运行完整门禁区分旧报告与当前缺口，再按服务边界补齐任务持久化、学习状态契约和运行韧性。每项只在隔离数据库验证，最后统一运行 Docker 与浏览器验收。

**Tech Stack:** FastAPI、SQLAlchemy/Alembic、PostgreSQL、Redis、Next.js、TypeScript、Playwright、Docker Compose。

## Global Constraints

- 保持“出题 Agent + 审题 Agent”两层生成约束。
- 不修改用户现有未提交文件；不执行 P2-20 数据治理决策。
- 数据库迁移先在可丢弃库验证；生产/原始库操作仅使用既有授权、备份和审批记录。

---

### Task 1: 重建 P0-07/P0-08 交付证据

**Files:**
- Modify: `scripts/run_schema_migration_drill.py`（仅在复现确认诊断或基线确有缺口时）
- Modify: `scripts/verify.py`（仅在可重复门禁编排确有缺口时）
- Test: `scripts/tests/test_schema_migration_drill.py`
- Test: `scripts/tests/test_verify_delivery.py`

- [ ] 在 600 秒上限内运行 `python scripts/verify.py full`，记录实际失败步骤或完整通过结果。
- [ ] 若失败，先为该诊断写最小回归测试，再仅修改根因路径。
- [ ] 运行 `python -m unittest discover -s scripts/tests -p "test_*.py" -v`、`python scripts/verify.py full`。

### Task 2: 建立 P1-13 可恢复生成任务

**Files:**
- Modify: `backend/app/models/generated_question.py`
- Create: `backend/app/models/generation_job.py`
- Create: `backend/migrations/primary/versions/<revision>_generation_jobs.py`
- Modify: `backend/app/services/question_generation_service.py`
- Test: `backend/tests/test_question_generation_service.py`

- [ ] 写入幂等键、状态迁移、租约取得、重试和终态拒绝的失败测试。
- [ ] 在服务层实现 `GenerationJob` 的创建/获取、租约和终态转换；现有出题与审题链路仅作为任务执行内容。
- [ ] 在隔离库执行迁移与目标测试，随后运行完整后端测试。

### Task 3: 统一 P1-14/P1-15/P1-16 客户端状态与契约

**Files:**
- Modify: `frontend/src/components/quiz/quiz-practice.tsx`
- Modify: `frontend/src/stores/learning-store.ts`
- Create: `frontend/src/lib/streaming.ts`
- Create: `frontend/src/lib/learning-contract.ts`
- Test: `frontend/tests/*.test.mjs`

- [ ] 写入跨 chunk SSE、取消请求、练习会话转换和无效 DTO 的失败测试。
- [ ] 实现可中止 SSE 解析器、共享状态机和运行时 DTO 适配器。
- [ ] 运行前端测试、类型检查、生产构建；用内部浏览器保存练习路径截图。

### Task 4: 收敛 P1-17 复习调度语义

**Files:**
- Modify: `backend/app/services/wrong_book_service.py`
- Modify: `backend/app/api/v1/learning.py`
- Test: `backend/tests/test_wrong_book_service.py`

- [ ] 写入同一时区/并发更新下统计、取题和 `next_review_at` 一致的失败测试。
- [ ] 让到期查询和今日统计共用 `next_review_at`，并显式保存调度版本与 UTC 时间。
- [ ] 运行目标测试和完整后端测试。

### Task 5: 补齐账户、预算、诊断与跨库证据

**Files:**
- Modify: `backend/app/services/auth_service.py`
- Modify: `backend/app/services/ai_budget_service.py`
- Modify: `backend/app/core/observability.py`
- Modify: `backend/app/services/content_service.py`
- Test: `backend/tests/test_auth.py`
- Test: `backend/tests/test_ai_budget*.py`
- Test: `backend/tests/test_learning_dimensions.py`

- [ ] 为账户状态/审计、预算结算、诊断持久化和跨库适配分别先写失败测试。
- [ ] 逐一实现并在隔离双数据库验证；不得将密钥或学生内容写入日志。
- [ ] 运行完整后端、前端、全量门禁、Docker 健康检查和浏览器回归。
