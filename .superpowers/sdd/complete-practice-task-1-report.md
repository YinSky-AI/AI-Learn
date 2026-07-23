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
