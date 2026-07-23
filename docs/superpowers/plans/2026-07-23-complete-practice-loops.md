# Complete Practice Loops Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 AI 自定义练习、错题重练和通用测验都具备可重试、可判题、可反馈、可记录的完整作答闭环。

**Architecture:** AI 生成题保持独立题库，新增独立的批次提交与逐题作答记录，不把生成题伪装成课程题。所有判题只在服务端执行，客户端提交前永远拿不到标准答案。错题重练和通用测验沿用现有服务，但补齐题型契约、幂等事件 ID 和完成状态重放。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、PostgreSQL、Pydantic、Next.js 14、React、TypeScript、Node test、pytest。

## Global Constraints

- 保持“出题 Agent + 审题 Agent”两层架构，不增加第三层 Agent。
- 正确答案和解析只能在服务端确认提交后返回给题目所有者；生成、批次详情和历史题面接口不得泄露。
- 所有提交操作必须使用客户端生成的 UUID 幂等键；同键同载荷返回原结果，同键不同载荷返回 HTTP 409。
- AI 自定义练习的作答必须进入学习报告和用户答题统计；不强行写入只接受 `questions.id` 的课程错题本。同一道生成题只允许首次答对事件获得积分，避免重复练习刷分。
- 单选提交单个选项键，多选提交按字母排序的逗号分隔键，填空题一空一答。
- 面向学生的错误均为简体中文纯文本，不暴露异常、SQL、JSON 对象或上游错误。
- 不创建 worktree；遵循用户明确要求，在当前分支工作。不同子 Agent 不得并行修改共享文件。

---

### Task 1: 服务端作答契约、持久化与幂等

**Files:**
- Create: `backend/migrations/primary/versions/lp_0009_practice_submission_contract.py`
- Create: `backend/app/services/generated_practice_service.py`
- Modify: `backend/app/models/ai_generated.py`
- Modify: `backend/app/models/wrong_book.py`
- Modify: `backend/app/schemas/question.py`
- Modify: `backend/app/api/v1/questions.py`
- Modify: `backend/app/api/v1/wrong_book.py`
- Modify: `backend/app/services/wrong_book_service.py`
- Modify: `backend/app/services/learning_service.py`
- Modify: `backend/app/services/behavior_service.py`
- Modify: `backend/app/services/gamification_service.py`
- Test: `backend/tests/test_question_generation_api.py`
- Test: `backend/tests/test_wrong_book_service.py`
- Test: `backend/tests/test_answer_submission_transaction.py`
- Test: `backend/tests/test_schema_migration.py`

**Interfaces:**
- Produces: `POST /api/v1/questions/batches/{batch_id}/submit`.
- Consumes body:
  `{"submission_id": UUID, "answers": [{"question_id": UUID, "user_answer": str, "time_spent_seconds": int}]}`.
- Produces data:
  `{"submission_id": UUID, "batch_id": UUID, "total_count": int, "correct_count": int, "accuracy_rate": float, "time_spent_seconds": int, "results": [{"question_id": UUID, "is_correct": bool, "correct_answer": str, "explanation": str | null}], "gamification": dict}`.
- Wrong-book `GET /practice` must include `question_type`; `POST /practice/answer` must accept `attempt_id: UUID` and replay the original result without incrementing `review_count` twice.
- `POST /learning/sessions/{session_id}/complete` becomes idempotent: an already completed owned session returns its existing `SessionStats` instead of an error.

- [ ] **Step 1: Write failing API and transaction tests**

  Cover exact batch ownership, approved-question-only lookup, complete-and-exact answer set, no pre-submit answer leakage, single/multiple/fill judging, persisted submission rows, behavior report projection, user counters, same-ID replay, different-payload conflict, wrong-book attempt replay, and completed-session replay.

- [ ] **Step 2: Run tests and verify RED**

  Run: `python scripts/run_backend_tests.py -q tests/test_question_generation_api.py tests/test_wrong_book_service.py tests/test_answer_submission_transaction.py tests/test_schema_migration.py`

  Expected: new submission, attempt-id and completion-replay assertions fail because the contracts do not exist.

- [ ] **Step 3: Add the migration and ORM models**

  Add `generated_practice_submissions`, `generated_practice_answers`, `generated_practice_reward_events`, and `wrong_practice_attempts`. Store a canonical payload fingerprint on each idempotent aggregate. Add foreign keys to users, batches and generated questions, unique `(submission_id, generated_question_id)`, unique `(user_id, generated_question_id)` reward eligibility, non-negative time checks, and indexes for user/batch history. Downgrade must remove only these new objects.

- [ ] **Step 4: Implement server-side submission**

  Lock the owned completed batch and user, load only `quality_status == "passed"` questions, require the submitted question IDs to equal the batch question IDs, judge using shared normalized answer rules, persist all answers atomically, project each new answer through `BehaviorService`, update user answer counters once, award points only for the first correct event per generated question, and return verified feedback. A replay with the same fingerprint must perform no writes.

- [ ] **Step 5: Complete the wrong-book and learning reliability contracts**

  Include `question_type` in practice payloads. Persist/replay wrong-book attempts before changing scheduling fields. Make session completion return the existing completed aggregate for the same owner.

- [ ] **Step 6: Run targeted backend tests and migration drill**

  Run: `python scripts/run_backend_tests.py -q tests/test_question_generation_api.py tests/test_wrong_book_service.py tests/test_answer_submission_transaction.py tests/test_schema_migration.py`

  Expected: all selected tests pass and the disposable database container is removed afterward.

- [ ] **Step 7: Commit**

  Commit: `feat(practice): persist verified AI practice submissions`

---

### Task 2: AI 自定义练习前端闭环

**Files:**
- Modify: `frontend/src/app/(main)/ai-questions/page.tsx`
- Modify: `frontend/tests/ai-question-generation.test.mjs`

**Interfaces:**
- Consumes the Task 1 batch submission endpoint exactly as documented.
- Generates one `submission_id` per submission and reuses it for retry until answers change or a new batch is generated.

- [ ] **Step 1: Write failing UI contract tests**

  Assert Chinese question-type labels, complete-answer gating, one submit control, submitting disable state, stable `submission_id`, per-question verified feedback, correct answer and explanation after submission, batch summary, and reset on a new generation.

- [ ] **Step 2: Run tests and verify RED**

  Run: `cd frontend; node --test tests/ai-question-generation.test.mjs`

  Expected: submit and feedback assertions fail.

- [ ] **Step 3: Implement the state machine**

  Use explicit states `answering | submitting | submitted | error`. Record batch start and question timing, freeze inputs while submitting/submitted, post every answer, display per-question green/red feedback plus explanation, and provide “重新出题” after completion. Preserve selected answers on recoverable failure and reuse the same submission ID.

- [ ] **Step 4: Normalize user-facing errors**

  Map timeout, authentication, review rejection, validation and provider-unavailable cases to concise Chinese messages; never return arbitrary `error.message` to the page.

- [ ] **Step 5: Verify frontend**

  Run: `cd frontend; node --test tests/ai-question-generation.test.mjs tests/challenge-experience.test.mjs tests/main-layout-pages.test.mjs; npm run typecheck; npm run build`

  Expected: all tests, typecheck and production build pass.

- [ ] **Step 6: Commit**

  Commit: `feat(ai): complete custom practice submission flow`

---

### Task 3: 错题重练与通用测验可靠性

**Files:**
- Modify: `frontend/src/app/(main)/wrong-book/practice/page.tsx`
- Modify: `frontend/src/components/quiz/quiz-practice.tsx`
- Modify: `frontend/tests/wrong-book-practice.test.mjs`
- Modify: `frontend/tests/learning-loop.test.mjs`

**Interfaces:**
- Consumes wrong-book `question_type` and `attempt_id` from Task 1.
- Reuses one learning `answer_id` for the same displayed question until a successful response or navigation to another question.

- [ ] **Step 1: Write failing reliability tests**

  Assert multi-select toggling and canonical comma answers, stable wrong-book attempt ID, submit-in-progress disable, inline retry without losing the answer, stable QuizPractice answer ID across retries, controls disabled during submit, and completion replay using server stats.

- [ ] **Step 2: Run tests and verify RED**

  Run: `cd frontend; node --test tests/wrong-book-practice.test.mjs tests/learning-loop.test.mjs`

  Expected: multi-select and idempotent retry assertions fail.

- [ ] **Step 3: Implement wrong-book multi-select and retry state**

  Render by `question_type`; maintain a set for multi-select; keep the current question and answer visible on failure; disable all inputs while submitting; reuse `attempt_id` for retry and create a new ID only after moving to another question.

- [ ] **Step 4: Implement QuizPractice stable event IDs**

  Store the current answer event ID in state/ref, reuse it after network or timeout errors, rotate only when the question changes, disable answer mutation during submit, and use the server completion response as the final authoritative summary.

- [ ] **Step 5: Verify frontend**

  Run: `cd frontend; node --test tests/wrong-book-practice.test.mjs tests/learning-loop.test.mjs tests/knowledge-practice-ui.test.mjs; npm run typecheck; npm run build`

  Expected: all tests, typecheck and production build pass.

- [ ] **Step 6: Commit**

  Commit: `fix(practice): make answer retries idempotent`

---

### Task 4: 集成审查与真实 UI 验收

**Files:**
- Create: `test/acceptance/complete-practice-loops/` screenshots and logs only
- Modify only when a verified integration defect requires a focused fix.

**Interfaces:**
- Consumes all Task 1–3 contracts.
- Produces evidence for generation → answer → submit → feedback, wrong-book multi-select, retry safety, report update, and container health.

- [ ] **Step 1: Run the combined verification suites**

  Run the targeted backend suite from Task 1, all affected frontend Node tests, `npm run typecheck`, `npm run build`, and `git diff --check`.

- [ ] **Step 2: Rebuild the application**

  Run: `docker compose up -d --build`

  Verify: `docker compose ps` shows required services healthy; inspect backend, frontend and generation-worker logs for new errors.

- [ ] **Step 3: Perform browser acceptance**

  In the internal browser, execute a real authenticated AI generation and submission, verify selected options freeze, result/解析 appear, and report total changes once. Exercise a wrong-book multi-select if available. Capture initial and final screenshots after each meaningful state change under the acceptance directory.

- [ ] **Step 4: Independent final review**

  Review the whole task diff for answer leakage, ownership bypass, duplicate rewards, retry ambiguity, migration reversibility and UI dead ends. Fix all Critical/Important findings and re-run their covering tests.

- [ ] **Step 5: Commit verified integration fixes if any**

  Commit only focused fixes with Conventional Commits; do not mix screenshot artifacts or secrets into commits.
