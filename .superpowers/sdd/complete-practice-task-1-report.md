# Complete Practice Loops — Task 1 Report

Status: DONE

## Summary

- 新增 `POST /api/v1/questions/batches/{batch_id}/submit`，只允许当前用户提交自己的已完成批次，且必须完整、精确地提交全部 `quality_status == "passed"` 题目。
- 服务端统一判定单选、按逗号分隔的多选集合和填空题；标准答案与解析只在所有权、批次状态和精确题集校验后返回，原有生成/详情/历史接口仍脱敏。
- 新增 `generated_practice_submissions`、`generated_practice_answers`、`generated_practice_reward_events` 和 `wrong_practice_attempts` 四张表及 `lp_0009_practice_contract` 迁移。
- `submission_id`/`attempt_id` 与规范化 payload 指纹实现幂等：同请求原样重放且零副作用，同 ID 不同 payload 返回 HTTP 409。已持久化的 AI 提交在批次状态后续改变时仍可原样重放。
- AI 作答投影到行为报告和用户答题统计；同一用户同一生成题只有首次答对获得积分，错误作答仅保留在 AI 提交历史与报告，未写入 canonical `wrong_book`。
- 错题练习 GET 返回 `question_type`，POST 接受 `attempt_id`；重放不会重复增加 `review_count`。已完成且归属当前用户的 learning session 再次 complete 会返回既有统计。

## Files Changed

- 新增：`backend/migrations/primary/versions/lp_0009_practice_submission_contract.py`
- 新增：`backend/app/services/generated_practice_service.py`
- 修改：`backend/app/models/ai_generated.py`、`backend/app/models/wrong_book.py`、`backend/app/models/__init__.py`
- 修改：`backend/app/schemas/question.py`
- 修改：`backend/app/api/v1/questions.py`、`backend/app/api/v1/wrong_book.py`
- 修改：`backend/app/services/wrong_book_service.py`、`backend/app/services/learning_service.py`、`backend/app/services/behavior_service.py`、`backend/app/services/gamification_service.py`
- 修改：`backend/app/core/schema_version.py`、`backend/schema_admin.py`
- 测试：`backend/tests/test_question_generation_api.py`、`backend/tests/test_wrong_book_service.py`、`backend/tests/test_answer_submission_transaction.py`、`backend/tests/test_schema_migration.py`
- 报告：`.superpowers/sdd/complete-practice-task-1-report.md`

## Tests

- RED：`python scripts/run_backend_tests.py -q tests/test_question_generation_api.py tests/test_wrong_book_service.py tests/test_answer_submission_transaction.py tests/test_schema_migration.py`
  - 重建测试镜像后真实收集 91 项；新增提交表/API、多选集合、错题 attempt、`question_type`、会话重放与 lp_0009 断言均按预期失败。
- GREEN 定向：同上命令。
  - 结果：`91 passed`，隔离数据库迁移和 Alembic drift check 通过，`postgres-test` 自动移除。
- 全量后端回归：`python scripts/run_backend_tests.py -q`
  - 结果：`185 passed`，隔离数据库自动移除。
- 幂等状态变化补充 RED/GREEN：`python scripts/run_backend_tests.py -q tests/test_question_generation_api.py::test_submit_completed_generated_batch_persists_feedback_and_replays_without_side_effects`
  - RED：`1 failed`（批次状态变化后误返 409）；GREEN：`1 passed`。
- 显式迁移回滚演练（可丢弃 `postgres-test/learning_platform_test`）：`lp_0009_practice_contract -> lp_0008_review_contract -> lp_0009_practice_contract -> check`
  - 结果：三步均成功，最终 `No new upgrade operations detected.`，容器与临时凭据已清理。
- 静态检查：`python -m compileall -q backend/app`、`git diff --check`
  - 结果：通过。
- Docker Desktop GUI：已截图核验 Engine running、后端容器 Running，日志持续返回 `/health 200 OK`，未见新错误。

## Commit(s)

- `feat(practice): persist verified AI practice submissions`（本报告随该提交一并交付，提交哈希以 `git log -1` 为准）

## Concerns

- Task 2/3 尚需前端消费新的 AI 提交端点、错题 `question_type`/`attempt_id` 和完成重放契约；本 Task 按要求未修改前端。
- 本轮只在可丢弃测试库演练迁移，未对常规/生产数据库执行迁移，也未重建正在运行的完整应用编排；集成重建属于 Task 4。
- 测试保留了仓库既有的 `datetime.utcnow()` 弃用警告与一条 health resource warning，本次没有新增对应调用。
- 定向测试中的旧变式题断言与当前持久化队列事实不一致；已只将测试更新为当前 `queued/job_id` 契约，未改动变式题实现。

## Review Fix (2026-07-23)

- 修复错题重练竞态：更新 `review_count`、`difficulty_factor` 和 `next_review_at` 前对归属当前用户的 `wrong_questions` 行执行 `FOR UPDATE`；真实双会话测试确认两个不同 attempt 均被保留，最终 `review_count=2`、`difficulty_factor=120`。
- AI 提交与错题 attempt 的幂等指纹改为只依赖初始请求快照，不再读取当前 `question_type`；历史答案/奖励/attempt 的题目 ID 改为不可变引用值，不再因题目删除被级联清除。同 ID 同原请求在题目删除、题型变化或批次状态变化后仍返回持久化快照，不同请求返回 HTTP 409，所有权校验保持不变。
- 错题 API 在 Task 3 前保持兼容：`attempt_id` 可省略，服务端生成 UUID；显式 ID 仍提供幂等语义。
- 新增错题 attempt 的 `created` / `replayed` / `conflict` 追踪日志，只记录 attempt 哈希键，不记录答案或完整用户 ID。
- 新增 AI 提交真实双会话并发测试，以及第二题奖励写入后注入异常的事务回滚测试；回滚后 submission、answers、reward events、用户统计和行为报告均无半成品。
- 定向回归：`97 passed`；全量后端：`191 passed`。隔离库执行 `lp_0009 -> lp_0008 -> lp_0009 -> check`，结果均成功且 `No new upgrade operations detected.`；临时测试容器及密钥文件已清理。
- Docker Desktop GUI 已目视核验：Engine running，`ai-learn` 的 frontend/backend/generation-worker/nginx/postgres/redis 均为绿色运行状态，未见错误提示；`docker compose ps --all` 同步确认 backend/frontend/nginx healthy，未残留 `postgres-test`。
- 变式题测试断言未回退：当前生产实现明确返回持久化队列契约 `status=queued` 与 `job_id`；回退为旧 `failed/variant_id` 断言会使未改动生产代码的基线测试失败，因此保留现有断言并未修改任何变式题生产实现。

## Review Fix Round 2 (2026-07-23)

- 将已发布的 `lp_0009_practice_submission_contract.py` 精确恢复为 `8c9a72d` 中的原始内容，保留三条题目级联外键，保证迁移历史不可变。
- 新增 `lp_0010_practice_history` 前向迁移，只删除经真实 PostgreSQL `pg_constraint` 核验的三条约束：`generated_practice_answers_generated_question_id_fkey`、`generated_practice_reward_events_generated_question_id_fkey`、`wrong_practice_attempts_question_id_fkey`；downgrade 使用相同名称和 `ON DELETE CASCADE` 精确恢复。
- 应用批准 head 更新为 `lp_0010_practice_history`。`schema_admin` 通过当前迁移目录动态批准精确 revision，测试确认 `lp_0009` 和 `lp_0010` 都可作为显式 downgrade 目标；`models/__init__.py` 已正确导出四个相关历史模型，新增契约断言防止遗漏。
- RED：expected head 仍为 `lp_0009` 且被改写的旧迁移缺失三条 FK，新增两个迁移断言均按预期失败。
- 真实旧库路径：用恢复后的不可变迁移链将可丢弃数据库建到旧 head `lp_0009`，查询确认三条 FK 均存在；同一数据库升级到 `lp_0010` 后计数 `3 -> 0`，降级回 `lp_0009` 后 `0 -> 3`，再次升级后 `3 -> 0`，最终 drift check 返回 `No new upgrade operations detected.`。
- 验收：迁移定向 `67 passed`；四文件定向 `98 passed`；全量后端 `192 passed`。`postgres-test` 和运行时测试密钥均已清理，`docker compose ps --all` 未见测试容器残留。

## Review Fix Round 3 (2026-07-23)

- 在标准 `backend/tests/test_schema_migration.py` 路径新增真实 PostgreSQL 自动回归。测试内创建两个随机 `learning_platform_*_test` 数据库，并在 `finally` 中终止残留连接、删除精确数据库目标。
- 数据迁移库自动升级到旧 head `lp_0009`，插入用户、批次、生成题、提交、答案快照、奖励事件、标准题和错题 attempt；确认三条旧 FK 存在后升级 `lp_0010`。
- 升级后自动确认三条 FK 消失，三类历史行、非空列、唯一约束与查询索引完整保留；删除生成题和标准题后，历史答案、奖励和错题 attempt 仍各保留一行。
- 第二个干净库自动完成 `lp_0010 -> lp_0009 -> lp_0010`，验证 downgrade/upgrade 均可执行。该回归随标准迁移测试命令运行，不再依赖人工演练。
- 验收：迁移定向 `68 passed`；四文件定向 `99 passed`；全量后端 `193 passed`。标准脚本已移除 `postgres-test`，运行时 secret 目录无残留文件。
