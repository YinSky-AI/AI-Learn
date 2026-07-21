# prompts_3 第一阶段实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付稳定底座、两层 AI 出题、四 Agent 辅导、答题反馈和对应的中文 UI。

**Architecture:** `QuestionPipeline` 独立执行“出题 Agent → 审题 Agent → 有限重试”，并写入题目批次与审计记录。`TutorHarness` 只编排辅导角色，使用 `SharedState` 传递会话上下文。答题 API 在单一事务中保存结果、反馈和错题候选记录。

**Tech Stack:** FastAPI、SQLAlchemy async、PostgreSQL、pytest、Next.js 14、TypeScript、Zustand、Playwright、Docker Compose。

## Global Constraints

- AI 出题只有出题 Agent 和审题 Agent 两层；不得恢复 `prompts_2` 的 8 层出题流程。
- 用户可见的错误必须是简短中文纯文本；dict 异常只读取 `message`。
- 保留当前未提交的课程与题库改动，不重置、不覆盖。
- 修改应用代码后必须执行 `docker compose up -d --build`，并检查容器状态和日志。
- UI 变更必须进行真实浏览器桌面、移动端截图验收，最多三轮修复。

---

## 文件结构

- `backend/app/ai/question_pipeline.py`：两层出题编排与有限重试。
- `backend/app/ai/prompts/question_review.py`：审题 Agent 的结构化提示词。
- `backend/app/ai/tools/question_memory_tool.py`：相似题与用户历史检索。
- `backend/app/ai/tools/question_save_tool.py`：批次、题目和审题结果持久化。
- `backend/app/ai/harness.py`、`backend/app/ai/tutor/*`：四 Agent 辅导与共享状态。
- `backend/app/api/v1/questions.py`、`backend/app/api/v1/ai.py`、`backend/app/api/v1/learning.py`：生成、辅导和答题反馈契约。
- `backend/app/models/*`、`backend/app/schemas/*`：新增错题候选和响应模型。
- `frontend/src/components/tutor/*`、`frontend/src/components/quiz/*`：辅导与答题反馈组件。
- `frontend/src/app/(main)/*`、`frontend/src/types/*`、`frontend/src/lib/api-client.ts`：页面、类型与客户端接入。
- `backend/tests/*`、`frontend/e2e/*`：API、单元与浏览器验收。

### Task 1: 建立可测试的服务底座

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/middlewares/error_handler.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_error_responses.py`
- Create: `frontend/playwright.config.ts`

**Produces:** `pytest` 可在 backend 容器运行；所有异常响应为 `{code, message, data, meta}` 且不泄露堆栈。

- [ ] **Step 1: 写出失败的错误响应测试。**

```python
async def test_dict_exception_returns_message_only(client):
    response = await client.get('/test-error-dict')
    assert response.status_code == 500
    assert response.json()['message'] == '服务暂时不可用'
    assert 'traceback' not in response.text.lower()
```

- [ ] **Step 2: 运行测试确认失败。**

Run: `docker compose exec -T backend pytest tests/test_error_responses.py -q`

- [ ] **Step 3: 实现统一异常格式与受控消息提取。**

```python
def user_message(detail: object, fallback: str) -> str:
    if isinstance(detail, dict):
        return str(detail.get('message') or fallback)
    return str(detail) if isinstance(detail, str) else fallback
```

将该函数用于 HTTP、校验和未处理异常处理器；未处理异常固定返回“服务暂时不可用，请稍后重试”。

- [ ] **Step 4: 在 requirements 中加入 `pytest==8.3.4` 与 `pytest-asyncio==0.25.0`，运行测试。**

Run: `docker compose up -d --build && docker compose exec -T backend pytest tests/test_error_responses.py -q`

- [ ] **Step 5: 提交。**

Run: `git add backend && git commit -m "test: establish backend test baseline"`

### Task 2: 实现两层出题流水线

**Files:**
- Create: `backend/app/ai/question_pipeline.py`
- Create: `backend/app/ai/prompts/question_review.py`
- Modify: `backend/app/ai/prompts/question_generation.py`
- Modify: `backend/app/ai/__init__.py`
- Create: `backend/tests/test_question_pipeline.py`

**Consumes:** `AIProvider.generate(messages)`。

**Produces:** `QuestionPipeline.generate(request, user_id, db) -> GeneratedBatchResult`，仅调用出题与审题两个 Agent，最多重试两次。

- [ ] **Step 1: 写出 Agent 调用顺序测试。**

```python
async def test_rejected_review_retries_generation_once(fake_provider, db):
    fake_provider.responses = [generated_payload, rejected_review, revised_payload, accepted_review]
    result = await QuestionPipeline(fake_provider).generate(request, user_id, db)
    assert result.questions[0].stem == '修订后的题目'
    assert fake_provider.call_count == 4
```

- [ ] **Step 2: 运行失败测试。**

Run: `docker compose exec -T backend pytest tests/test_question_pipeline.py -q`

- [ ] **Step 3: 实现输入、审题输出和循环。**

```python
for attempt in range(3):
    questions = await self._generate_questions(request, revision_notes)
    review = await self._review_questions(request, questions)
    if review.passed:
        return GeneratedBatchResult(questions=questions, review=review)
    revision_notes = review.revision_notes
raise QuestionGenerationError('题目未能通过审核，请调整条件后重试')
```

- [ ] **Step 4: 运行流水线测试和编译检查。**

Run: `docker compose exec -T backend pytest tests/test_question_pipeline.py -q && docker compose exec -T backend python -m compileall -q app`

- [ ] **Step 5: 提交。**

Run: `git add backend/app/ai backend/tests/test_question_pipeline.py && git commit -m "feat(ai): add two-agent question pipeline"`

### Task 3: 接通生成 API 与持久化

**Files:**
- Modify: `backend/app/ai/tools/question_memory_tool.py`
- Modify: `backend/app/ai/tools/question_save_tool.py`
- Modify: `backend/app/api/v1/questions.py`
- Modify: `backend/app/services/question_generation_service.py`
- Create: `backend/tests/test_question_generation_api.py`

**Consumes:** `QuestionPipeline.generate` 和现有 `GeneratedQuestionBatch`、`GeneratedQuestion`、`QuestionQualityCheck` 模型。

**Produces:** `POST /api/v1/questions/generate` 在同一请求内返回已审核且已保存的批次；失败时不留下半完成数据。

- [ ] **Step 1: 写 API 成功和回滚测试。**

```python
async def test_generate_persists_reviewed_questions(client, auth_headers):
    response = await client.post('/api/v1/questions/generate', json=request_payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()['data']['status'] == 'completed'

async def test_generate_rolls_back_when_review_fails(client, auth_headers):
    response = await client.post('/api/v1/questions/generate', json=request_payload, headers=auth_headers)
    assert response.status_code == 422
    assert await count_generated_batches() == 0
```

- [ ] **Step 2: 运行失败测试。**

Run: `docker compose exec -T backend pytest tests/test_question_generation_api.py -q`

- [ ] **Step 3: 实现 similarity_hash 检索、保存和事务边界。**

```python
async with db.begin():
    result = await pipeline.generate(request, user_id, db)
    batch = await question_save_tool.save_batch(db, result, user_id)
return success_response(data={'batch_id': str(batch.id), 'status': 'completed'})
```

- [ ] **Step 4: 运行生成 API 测试。**

Run: `docker compose exec -T backend pytest tests/test_question_generation_api.py -q`

- [ ] **Step 5: 提交。**

Run: `git add backend && git commit -m "feat(questions): persist reviewed generation batches"`

### Task 4: 实现四 Agent 辅导与答题反馈 API

**Files:**
- Create: `backend/app/ai/tutor/shared_state.py`
- Create: `backend/app/ai/tutor/agents.py`
- Modify: `backend/app/ai/harness.py`
- Modify: `backend/app/api/v1/ai.py`
- Modify: `backend/app/api/v1/learning.py`
- Modify: `backend/app/services/learning_service.py`
- Modify: `backend/app/schemas/learning.py`
- Create: `backend/tests/test_tutor_api.py`

**Produces:** `TutorHarness.reply(context) -> TutorResponse` 与答题结果中的 `explanation`、`knowledge_point`、`tutor_prompt` 字段。

- [ ] **Step 1: 写共享状态和答题反馈测试。**

```python
async def test_tutor_response_contains_role_messages(client, auth_headers):
    response = await client.post('/api/v1/ai/chat', json=chat_payload, headers=auth_headers)
    roles = {item['role'] for item in response.json()['data']['messages']}
    assert {'teacher', 'assistant', 'diagnostician', 'encourager'} <= roles

async def test_wrong_answer_contains_explanation(client, auth_headers):
    response = await client.post(answer_url, json=wrong_answer, headers=auth_headers)
    assert response.json()['data']['explanation']
```

- [ ] **Step 2: 运行失败测试。**

Run: `docker compose exec -T backend pytest tests/test_tutor_api.py -q`

- [ ] **Step 3: 实现 SharedState 与非代答提示词。**

```python
@dataclass
class SharedState:
    question: dict | None
    student_answer: str | None
    diagnosis: str | None = None
    messages: list[dict] = field(default_factory=list)
```

每个 Agent 只追加带角色标记的消息；老师输出必须包含思考提示而非答案。

- [ ] **Step 4: 运行 API 测试。**

Run: `docker compose exec -T backend pytest tests/test_tutor_api.py -q`

- [ ] **Step 5: 提交。**

Run: `git add backend && git commit -m "feat(tutor): add collaborative tutoring feedback"`

### Task 5: 接入中文辅导与答题反馈 UI

**Files:**
- Create: `frontend/src/components/tutor/tutor-panel.tsx`
- Create: `frontend/src/components/quiz/answer-feedback.tsx`
- Modify: `frontend/src/components/quiz/quiz-practice.tsx`
- Modify: `frontend/src/app/(main)/learning/[id]/page.tsx`
- Modify: `frontend/src/types/api.ts`
- Create: `frontend/e2e/learning-feedback.spec.ts`

**Consumes:** Task 4 的 `TutorResponse` 和增强后的答题响应。

**Produces:** 学生答题后立即查看解析并打开中文辅导面板；面板清楚标注四个辅导角色。

- [ ] **Step 1: 写浏览器用例。**

```ts
test('错误答案显示解析并能打开 AI 辅导', async ({ page }) => {
  await page.goto('/learning/course-1')
  await page.getByRole('button', { name: '提交答案' }).click()
  await expect(page.getByText('答案解析')).toBeVisible()
  await page.getByRole('button', { name: '向 AI 老师求助' }).click()
  await expect(page.getByRole('heading', { name: 'AI 辅导团队' })).toBeVisible()
})
```

- [ ] **Step 2: 运行失败用例。**

Run: `npx playwright test e2e/learning-feedback.spec.ts`

- [ ] **Step 3: 实现反馈卡与面板。**

```tsx
<AnswerFeedback result={answerResult} onAskTutor={() => setTutorOpen(true)} />
<TutorPanel open={tutorOpen} context={tutorContext} onOpenChange={setTutorOpen} />
```

所有可见文本使用简体中文；加载、空状态和失败状态使用现有组件样式。

- [ ] **Step 4: 构建与浏览器测试。**

Run: `npm run build && npx playwright test e2e/learning-feedback.spec.ts`

- [ ] **Step 5: 提交。**

Run: `git add frontend && git commit -m "feat(learning): add answer feedback and tutor panel"`

### Task 6: 第一阶段容器、日志与截图验收

**Files:**
- Create: `test/acceptance/phase-1-visual-review.md`
- Create: `test/acceptance/screenshots/phase-1-desktop.png`
- Create: `test/acceptance/screenshots/phase-1-mobile.png`

- [ ] **Step 1: 重建服务。**

Run: `docker compose up -d --build && docker compose ps`

Expected: postgres、redis、backend、frontend 均为 healthy；nginx-gateway 为 running。

- [ ] **Step 2: 运行回归测试。**

Run: `docker compose exec -T backend pytest -q && npm --prefix frontend run build`

- [ ] **Step 3: 执行真实浏览器旅程并保存截图。**

桌面 1440×1000 与移动端 390×844 均执行：打开学习页 → 提交错误答案 → 查看解析 → 打开 AI 辅导 → 发送追问。

- [ ] **Step 4: 检查日志。**

Run: `docker compose logs --tail 200 backend frontend`

Expected: 没有 traceback、Unhandled exception、500 或前端编译错误。

- [ ] **Step 5: 写验收结论并提交。**

Run: `git add test/acceptance && git commit -m "test: record phase one acceptance evidence"`
