# Task 3 Implementer Report

## 状态

完成。`POST /api/v1/questions/generate` 现同步执行两层 `QuestionPipeline`，只在审题通过后将批次、题目和审题记录原子写入 `learning_platform`；三轮审题拒绝返回 422，事务不留下批次数据。

## 契约与边界

- 保存契约采用 `QuestionSaveTool(request).save_batch(db, result, user_id)`。原因是 Task 2 的 `GeneratedBatchResult` 只包含题目和审题结论，不含 `GeneratedQuestionBatch` 的必填请求元数据；由构造参数传入请求可保持简报要求的三参数 `save_batch`，且无需修改 Task 2 已交付的数据类。
- `GeneratedQuestionBatch`、`GeneratedQuestion`、`QuestionQualityCheck` 含 `users` / `knowledge_nodes` 外键，全部使用 `get_db` 对应的 `learning_platform`。外部导入题库 `ai_learn` 不参与生成持久化。
- 事务只由 `question_generation_service.generate_reviewed_batch()` 的 `async with db.begin()` 管理；工具层只 `flush`，不自行 `commit`、`rollback` 或吞掉异常。
- 生成路径只调用出题 Agent 和审题 Agent 的 `QuestionPipeline`，未调用或恢复旧 8 层 `AIHarness`。

## 实现

- `question_memory_tool.py`
  - 按用户、学科、主题和 `quality_status=passed` 检索历史生成题。
  - 支持可选 `similarity_hash` 精确去重检索。
  - 数据库异常只写服务端日志，对调用方返回空结果，不暴露技术详情。
- `question_save_tool.py`
  - 对规范化题干生成 SHA-256 `similarity_hash`。
  - 保存 `completed` 批次、全部已通过题目及每题一条审题通过记录。
  - 未通过审题直接拒绝保存；任一字段/数据库错误交给外层事务整体回滚。
- `question_generation_service.py`
  - 新增单事务的生成、审核、保存编排。
- `questions.py`
  - `/generate` 接入 `QuestionPipeline(get_ai_provider())`。
  - 成功返回 `batch_id` 和 `completed`；`QuestionGenerationError` 映射为 422 中文纯文本消息。
- 测试
  - 新增 API 成功持久化、hash 检索和失败零批次测试。
  - 补充三轮拒绝后规定中文错误及 provider 恰好 6 次调用测试。

## TDD 证据

RED（挂载当前源码的一次性 backend 容器）：

```text
test_generate_persists_reviewed_questions: expected completed, got pending
test_generate_rolls_back_when_review_fails: expected 422, got 200
2 failed, 2 passed
```

GREEN（实现后同环境）：

```text
tests/test_question_generation_api.py ..
tests/test_question_pipeline.py ..
4 passed
```

## 最终验收证据

- 重建：`docker compose up -d --build backend`，退出码 0，backend 镜像重建并容器重建成功。
- 容器测试：

  ```text
  docker compose exec -T -e QUESTION_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/learning_platform_test backend pytest tests/test_question_generation_api.py tests/test_question_pipeline.py tests/test_error_responses.py -q
  7 passed, 5 warnings in 2.11s
  ```

- 编译：`docker compose exec -T backend python -m compileall -q app tests/test_question_generation_api.py tests/test_question_pipeline.py`，退出码 0。
- `docker compose ps`：backend、frontend、postgres、redis 均 `healthy`，nginx 正常运行。
- backend 日志：应用启动完成、数据库表检查完成、Redis 连接成功，健康检查均为 HTTP 200；未发现新增错误。
- Docker Desktop GUI：`ai-learn` 组内 nginx、postgres、redis、frontend、backend 均显示绿色运行状态，未显示容器错误。
- `git diff --check`：退出码 0。

## 已知非任务警告

- 测试输出包含现有 `BaseModel.created_at` 使用 `datetime.utcnow()` 的 SQLAlchemy 弃用警告。
- pytest 输出包含现有 `asyncio_default_fixture_loop_scope` 未配置的弃用警告。
- 两项均不影响本任务测试结果，且对应文件不在 Task 3 修改范围内。
