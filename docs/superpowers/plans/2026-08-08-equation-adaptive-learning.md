# Equation Adaptive Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有通用 AI 学习平台收敛为可验证的初中数学一元一次方程错因诊断与自适应练习系统，并形成适合 AI 应用工程岗位的代码、评测和演示证据。

**Architecture:** 学生提交答案和可选步骤后，提交事务只完成判题、幂等持久化和诊断任务入队；独立 Worker 在事务外执行安全方程校验及必要的 LLM 结构化归类，再在短事务中写入诊断、BKT 掌握度和下一步决策。前端轮询任务结果，Tutor 和变式题流水线只消费已验证的诊断证据，不自行猜测错因。

**Tech Stack:** Python 3.12、FastAPI 0.115.6、Pydantic 2.10.4、SQLAlchemy 2.0.36、Alembic 1.14.1、PostgreSQL、OpenAI-compatible Provider、Lark 1.3.1、SymPy 1.14.0、Next.js 14、TypeScript、pytest、Playwright、Docker Compose。

## Global Constraints

- MVP 只支持初中数学一元一次方程，不扩展其他学科和章节。
- 保持“Generator → Reviewer”两层出题流水线，不新增第三层出题 Agent。
- 保留四类 Tutor 策略，但 Tutor 不重新判题、不重新诊断错因。
- 禁止使用 Python `eval`、SymPy `parse_expr` 或 `sympify(str)` 解析用户输入。
- 标准答案和完整解析不得进入 Tutor Prompt 或面向学生的诊断日志。
- 外部模型调用不得发生在持有数据库行锁的事务中。
- 作答提交保持现有 `submission_id`、payload fingerprint 和冲突返回语义。
- 同一答案事件最多产生一个诊断、一次 BKT 更新和一个自适应决策。
- 所有新增请求字段保持可选，旧客户端不传解题步骤时仍能提交。
- 不引入 Celery、RQ、Kafka、向量数据库、模型微调或新微服务框架。
- 不覆盖当前工作区已有的 `shared_state.py`、`content_service.py` 及相关测试改动；执行每项任务前重新读取最新文件。

---

## 1. 技术选型

### 1.1 方程解析：Lark 1.3.1

用途：只解析以下受控语法，不执行任意 Python 表达式。

```text
equation  : sum "=" sum
sum       : product (("+" | "-") product)*
product   : unary (("*" | "/") unary)*
unary     : "-" unary | atom
atom      : NUMBER | "x" | "(" sum ")"
```

输入规范化只处理：

- 中文全角运算符转换为半角。
- `×`、`÷` 转换为 `*`、`/`。
- 在 `2x`、`2(x+1)`、`)x` 等明确位置插入乘号。
- 删除普通空白，但不删除未知字符。

不支持函数调用、属性访问、列表、字典、指数、阶乘、其他变量和代码片段。选择 Lark 而不是正则直接求值，是为了让允许语法明确、可测试；选择它而不是 SymPy `parse_expr`，是因为 SymPy 官方文档明确说明 `parse_expr` 使用 `eval`，不应接收未经清洗的输入。

### 1.2 符号归一化：SymPy 1.14.0

SymPy 不接收原始字符串。Lark Transformer 直接构造 `Integer`、`Rational`、`Symbol`、`Add` 和 `Mul` 对象，然后使用 `expand`、`Poly` 和有理数运算提取：

```python
LinearEquation(
    coefficient: Rational,
    constant: Rational,
    kind: Literal["linear", "identity", "contradiction"],
)
```

一条方程统一表示为 `left - right = 0`。两个正常线性方程 `(a1, b1)` 与 `(a2, b2)` 等价，当且仅当：

```text
a1 * b2 == a2 * b1
```

恒等式和矛盾式分别处理，不能与普通线性方程混为一类。

### 1.3 AI 诊断：规则优先 + 现有 AIProvider

- StepVerifier 先定位第一处不等价步骤和结构特征。
- 规则能唯一归类且置信度达到 `0.85` 时，不调用模型。
- 规则存在歧义时，使用现有 `AIProvider.generate()` 和 JSON object 响应格式。
- Pydantic 校验错因枚举、证据步骤、置信度和知识点。
- 模型引用不存在的步骤、返回未知枚举或解释与校验证据冲突时，降级为 `insufficient_evidence`。

这让 LLM 负责语义归类与教学表达，而不是充当不可验证的数学裁判。

### 1.4 学习状态：Bayesian Knowledge Tracing

使用纯 Python `Decimal` 实现 BKT，不增加机器学习框架。参数固定为版本 `bkt-equation-v1`：

```text
p_initial = 0.35
p_learn   = 0.15
p_slip    = 0.10
p_guess   = 0.20
```

每次作答按正确性更新主知识点的 `p_known`。诊断置信度只影响下一步策略，不直接改变 BKT 观测值，避免模型意见污染学习状态。

### 1.5 异步任务：PostgreSQL 持久化任务表

继续使用项目已有的 PostgreSQL、`FOR UPDATE SKIP LOCKED`、有限租约和重试，不引入 Celery。原因：

- 项目已经依赖 PostgreSQL，并存在 `GenerationJob` 模式。
- 诊断规模不足以证明新增消息中间件的成本合理。
- 任务、答案和诊断可以通过数据库唯一约束形成强幂等证据。

必须修正现有生成 Worker 的事务边界：领取任务后先提交租约，再调用模型，最后使用新事务写结果。

### 1.6 前端状态同步：短轮询

- 提交答案立即获得正确性和 `diagnosis_job_id`。
- 每 1 秒轮询一次诊断任务，前台最多主动等待 10 秒。
- 超过 10 秒保持“诊断中”，再次进入错题详情仍可读取结果。
- 不新增 WebSocket 或 SSE；当前单任务状态不值得引入长连接复杂度。

### 1.7 评测：版本化 JSONL + pytest 运行器

- 评测样本保存在 Git 中的 JSONL。
- 规则路径可在 CI 中完全离线运行。
- 真实模型 A/B/C 评测通过显式命令运行，避免每次 CI 消耗额度。
- 输出 JSON 作为机器证据，Markdown 只作为摘要。
- 不引入 MLflow 或 W&B；当前单项目评测用版本文件即可复现。

## 2. 完整逻辑设计

### 2.1 提交阶段

```text
前端提交 submission_id、答案、步骤、置信度
→ Pydantic 校验长度、步数、置信度
→ payload fingerprint 纳入步骤和置信度
→ 锁定练习批次并检查所有权
→ 服务端判题
→ 保存 submission、answers、积分和行为统计
→ 为每条答案创建唯一 DiagnosisJob
→ 提交事务
→ 立即返回正确性和 diagnosis_job_id
```

相同 `submission_id` 与相同 payload 重放时返回原结果和原任务 ID；相同 ID 携带不同步骤或答案时返回 409。

### 2.2 Worker 阶段

```text
短事务领取 queued 或租约过期任务
→ 写 running、lease_owner、lease_expires_at
→ 提交领取事务
→ 短只读会话加载题目和学生证据快照
→ 关闭数据库会话
→ 在事务外运行 StepVerifier 和必要的 Provider 调用
→ 新短事务锁定任务与掌握度行
→ 插入唯一 AnswerDiagnosis
→ 更新 BKT
→ 生成 AdaptationDecision
→ 标记任务 succeeded
→ 提交结果事务
```

Worker 在模型调用期间退出时，租约到期后可以重新领取。结果事务依赖答案诊断唯一约束，重复执行不会重复更新掌握度。

### 2.3 诊断分支

```text
答案正确
→ diagnosis.status = not_required
→ BKT 按正确观测更新

答案错误且没有步骤
→ diagnosis.status = insufficient_evidence
→ BKT 按错误观测更新
→ next_action = ask_diagnostic_question

答案错误且步骤可解析
→ 找到第一处不等价变形
→ 规则置信度 >= 0.85：直接归类
→ 否则调用 Provider 在白名单错因中归类
→ 校验模型证据是否引用真实步骤
→ 保存 diagnosed 或 insufficient_evidence

步骤无法解析或含禁止语法
→ 不执行表达式
→ 保存 insufficient_evidence
→ 对用户显示“暂时无法识别该写法”，不显示堆栈
```

### 2.4 下一步策略

策略版本固定为 `adaptive-equation-v1`，优先级从高到低：

1. 证据不足：询问一个诊断问题。
2. 最近两次相同错因：保持难度并选择该错因补救题。
3. 错因明确：选择同知识点、只覆盖该错因的题目。
4. `p_known < 0.40`：回到前置知识点。
5. `0.40 <= p_known < 0.75`：同知识点同级变式。
6. `p_known >= 0.75` 且最近两次正确：提高难度。
7. 无匹配题：创建受约束的 GenerationJob，继续经过 Generator—Reviewer。

每次决策保存 `reason_codes`，前端只把白名单原因翻译为用户文案。

## 3. 文件结构

```text
backend/app/domain/
  equation_parser.py          # 白名单语法与 SymPy 对象构造
  equation_verifier.py        # 等价性、第一处错误和结构特征
  equation_taxonomy.py        # 知识点、错因、阈值和版本
  bkt.py                      # 纯函数掌握度计算

backend/app/services/
  diagnosis_service.py        # 规则优先和 LLM 降级诊断
  diagnosis_job_service.py    # 入队、领取、租约、重试与完成
  mastery_service.py          # 数据库行锁与 BKT 持久化
  adaptive_policy.py          # 确定性下一步决策

backend/app/models/adaptive_learning.py
backend/app/schemas/adaptive_learning.py
backend/app/api/v1/adaptive.py
backend/app/ai/prompts/error_diagnosis.py
backend/app/data/equation_misconceptions.py
backend/run_diagnosis_worker.py

backend/evals/equation_diagnosis/
  schema.py
  cases.jsonl
  runner.py
  metrics.py

frontend/src/components/learning/
  solution-steps-input.tsx
  diagnosis-result.tsx
  mastery-change.tsx
```

## 4. 任务依赖顺序

```text
Task 1 方程解析与校验
  ├─ Task 2 诊断契约与规则/LLM 混合服务
  └─ Task 3 BKT 与自适应策略
          │
Task 4 数据库模型与迁移
          │
Task 5 持久化 Worker 与事务边界
          │
Task 6 练习提交集成
          │
Task 7 查询接口与下一题
  ├─ Task 8 Tutor/生成流水线接入
  └─ Task 9 前端交互
          │
Task 10 离线评测
          │
Task 11 全链路验收与求职证据
```

---

### Task 1: 安全方程解析与步骤等价性验证

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/domain/equation_parser.py`
- Create: `backend/app/domain/equation_verifier.py`
- Test: `backend/tests/test_equation_parser.py`
- Test: `backend/tests/test_equation_verifier.py`

**Interfaces:**
- Produces: `parse_linear_equation(text: str) -> LinearEquation`
- Produces: `verify_solution_steps(steps: Sequence[str]) -> StepVerification`
- Produces: `StepVerification.first_invalid_transition: int | None`
- Produces: `StepVerification.features: frozenset[TransitionFeature]`
- Consumes: no application service or database state.

- [ ] **Step 1: Add exact parser dependencies**

Add `lark==1.3.1` and `sympy==1.14.0` to `backend/requirements.txt`.

- [ ] **Step 2: Write parser rejection tests**

```python
@pytest.mark.parametrize("text", [
    "__import__('os').system('whoami')",
    "x.__class__",
    "[x for x in (1, 2)]",
    "sin(x)=0",
    "x^2=4",
    "x+y=2",
])
def test_parser_rejects_non_whitelisted_syntax(text: str):
    with pytest.raises(EquationSyntaxError):
        parse_linear_equation(text)
```

- [ ] **Step 3: Run rejection tests and confirm they fail because the module is absent**

Run: `cd backend; pytest tests/test_equation_parser.py -v`

Expected: collection fails with `ModuleNotFoundError` for `equation_parser`.

- [ ] **Step 4: Implement Lark grammar and direct SymPy object construction**

Implement immutable `LinearEquation`, explicit normalization, maximum 200-character input, and a Lark Transformer that constructs SymPy objects without string evaluation.

- [ ] **Step 5: Add valid parsing and equivalence cases**

Cover integers, negative values, decimals, fractions, parentheses, implicit multiplication and full-width operators. Assert that `2(x+1)=10` and `2x+2=10` are equivalent, while `2x+2=10` and `2x=12` are not.

- [ ] **Step 6: Implement step verification**

```python
@dataclass(frozen=True)
class StepVerification:
    parsed_steps: tuple[LinearEquation, ...]
    first_invalid_transition: int | None
    features: frozenset[TransitionFeature]
    parse_error_step: int | None
```

The transition index means “from step N to step N+1”, using zero-based storage and one-based presentation only at the API boundary.

- [ ] **Step 7: Run focused tests**

Run: `cd backend; pytest tests/test_equation_parser.py tests/test_equation_verifier.py -v`

Expected: all parser, security and equivalence tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/requirements.txt backend/app/domain/equation_parser.py backend/app/domain/equation_verifier.py backend/tests/test_equation_parser.py backend/tests/test_equation_verifier.py
git commit -m "feat(math): add safe linear equation verifier"
```

---

### Task 2: 错因目录与规则优先诊断服务

**Files:**
- Create: `backend/app/domain/equation_taxonomy.py`
- Create: `backend/app/data/equation_misconceptions.py`
- Create: `backend/app/schemas/adaptive_learning.py`
- Create: `backend/app/ai/prompts/error_diagnosis.py`
- Create: `backend/app/services/diagnosis_service.py`
- Test: `backend/tests/test_diagnosis_service.py`
- Test: `backend/tests/test_error_diagnosis_prompt.py`

**Interfaces:**
- Consumes: `StepVerification` from Task 1.
- Consumes: `TutorProvider.generate(messages, **kwargs)` compatible Provider.
- Produces: `diagnose_answer(input: DiagnosisInput, provider: TutorProvider | None) -> ErrorDiagnosisResult`.
- Produces: `MISCONCEPTION_VERSION = "equation-misconception-v1"`.

- [ ] **Step 1: Define closed enums and Pydantic contracts**

```python
class DiagnosisStatus(StrEnum):
    DIAGNOSED = "diagnosed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_REQUIRED = "not_required"

class MisconceptionCode(StrEnum):
    BALANCE_VIOLATION = "balance_violation"
    SIGN_TRANSFER_ERROR = "sign_transfer_error"
    DISTRIBUTION_ERROR = "distribution_error"
    COMBINE_LIKE_TERMS_ERROR = "combine_like_terms_error"
    COEFFICIENT_NORMALIZATION_ERROR = "coefficient_normalization_error"
    ARITHMETIC_SLIP = "arithmetic_slip"
    MULTIPLE_POSSIBLE_CAUSES = "multiple_possible_causes"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
```

- [ ] **Step 2: Write failing rule-path tests**

Test correct answers, missing steps, distribution errors, sign transfer errors, ambiguous transitions and unparseable input. Assert the Provider is not called when a rule has confidence at least `0.85`.

- [ ] **Step 3: Run tests and confirm missing implementation failure**

Run: `cd backend; pytest tests/test_diagnosis_service.py -v`

Expected: import or symbol failure.

- [ ] **Step 4: Implement rule mapping and explicit abstention**

Every `diagnosed` result must include a valid misconception, knowledge point, first invalid transition and evidence derived from input. Missing or ambiguous evidence returns `insufficient_evidence`.

- [ ] **Step 5: Write failing Provider validation tests**

Use fake responses for unknown enums, out-of-range steps, hallucinated evidence, invalid JSON and valid ambiguous classification.

- [ ] **Step 6: Implement structured Provider fallback**

Call:

```python
await provider.generate(
    messages,
    max_tokens=420,
    temperature=0.1,
    response_format={"type": "json_object"},
)
```

Do not include user identity, full conversation history or unrelated answers. Parse with `ErrorDiagnosisLLMOutput.model_validate_json()` and then cross-check evidence against actual steps.

- [ ] **Step 7: Run diagnosis tests**

Run: `cd backend; pytest tests/test_diagnosis_service.py tests/test_error_diagnosis_prompt.py -v`

Expected: all rule, Provider and abstention tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/domain/equation_taxonomy.py backend/app/data/equation_misconceptions.py backend/app/schemas/adaptive_learning.py backend/app/ai/prompts/error_diagnosis.py backend/app/services/diagnosis_service.py backend/tests/test_diagnosis_service.py backend/tests/test_error_diagnosis_prompt.py
git commit -m "feat(ai): add evidence-based error diagnosis"
```

---

### Task 3: BKT 掌握度算法与确定性自适应策略

**Files:**
- Create: `backend/app/domain/bkt.py`
- Create: `backend/app/services/adaptive_policy.py`
- Test: `backend/tests/test_bkt.py`
- Test: `backend/tests/test_adaptive_policy.py`

**Interfaces:**
- Produces: `update_bkt(prior: Decimal, correct: bool, parameters: BKTParameters) -> Decimal`.
- Produces: `decide_next_action(context: AdaptiveContext) -> AdaptationDecisionData`.
- Consumes: `DiagnosisStatus` and `MisconceptionCode` from Task 2.
- No database or Provider dependency.

- [ ] **Step 1: Write failing BKT examples with exact expected decimals**

```python
def test_correct_observation_increases_mastery():
    result = update_bkt(Decimal("0.35"), True, BKT_EQUATION_V1)
    assert result == Decimal("0.7517")

def test_incorrect_observation_reduces_posterior_before_learning():
    result = update_bkt(Decimal("0.35"), False, BKT_EQUATION_V1)
    assert result == Decimal("0.2036")
```

These expected values follow the documented formula and are quantized to four decimal places with `ROUND_HALF_UP`; tests and implementation must use this explicit rounding rule.

- [ ] **Step 2: Implement immutable versioned BKT parameters and pure update**

Reject priors outside `[0, 1]`, guard zero denominators, and never read configuration implicitly.

- [ ] **Step 3: Write failing policy precedence tests**

Cover insufficient evidence, repeated misconception, prerequisite fallback, same-level practice and difficulty increase. Include a case where multiple conditions match and assert the documented priority.

- [ ] **Step 4: Implement deterministic policy**

Return action, target knowledge point, optional misconception, reason codes and `adaptive-equation-v1`. No LLM call is permitted in this module.

- [ ] **Step 5: Run focused tests**

Run: `cd backend; pytest tests/test_bkt.py tests/test_adaptive_policy.py -v`

Expected: all numeric boundary and precedence tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/bkt.py backend/app/services/adaptive_policy.py backend/tests/test_bkt.py backend/tests/test_adaptive_policy.py
git commit -m "feat(learning): add versioned adaptive policy"
```

---

### Task 4: 自适应学习持久化模型与迁移

**Files:**
- Create: `backend/app/models/adaptive_learning.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/content.py`
- Modify: `backend/app/services/seed_bank.py`
- Create: `backend/migrations/primary/versions/lp_0011_adaptive_diagnosis.py`
- Modify: `backend/tests/test_schema_migration.py`
- Test: `backend/tests/test_adaptive_models.py`
- Test: `backend/tests/test_adaptive_knowledge_nodes.py`

**Interfaces:**
- Produces ORM models: `DiagnosisJob`, `AnswerDiagnosis`, `KnowledgeMasteryState`, `AdaptationDecision`.
- Produces canonical `KnowledgeNode.code: str` used by diagnosis, BKT and evaluation data.
- Consumes primary database head `lp_0010`.
- Does not modify question-bank database schema.

- [ ] **Step 1: Write schema metadata tests**

Assert exact table names, required columns, indexes, foreign keys, status checks and uniqueness constraints. Assert `DiagnosisJob` and `AnswerDiagnosis` each reference exactly one of ordinary or generated answers through a check constraint. Assert `KnowledgeNode.code` is non-null and unique.

- [ ] **Step 2: Run metadata tests and confirm they fail**

Run: `cd backend; pytest tests/test_adaptive_models.py -v`

Expected: missing model import failure.

- [ ] **Step 3: Implement ORM models**

Use JSONB only for bounded `reason_codes`, `input_snapshot` and `token_usage`; use typed columns for fields involved in filtering, uniqueness and metrics. Store no full Prompt.

- [ ] **Step 4: Write migration from `lp_0010`**

The migration adds `knowledge_nodes.code`, backfills existing rows deterministically as `legacy-` plus the first 12 hexadecimal UUID characters, then makes the column non-null and unique. It also creates all four adaptive tables, constraints and indexes in the primary database. Downgrade removes the adaptive tables in reverse dependency order and then removes `knowledge_nodes.code`.

- [ ] **Step 5: Add legacy behavior-profile backfill**

Map only behavior-profile keys that resolve to an existing `KnowledgeNode`. Insert `KnowledgeMasteryState` with model version `bkt-equation-v1` and the existing level as the initial `p_known`; preserve unresolvable legacy JSON without manufacturing a knowledge-node relation. Extend `seed_bank.py` to upsert the six documented equation knowledge nodes with canonical codes and UUID prerequisite links; do not hard-code environment-specific UUIDs.

- [ ] **Step 6: Run migration unit and drill tests**

Run: `cd backend; pytest tests/test_adaptive_models.py tests/test_schema_migration.py tests/test_adaptive_knowledge_nodes.py -v`

Expected: metadata, upgrade, downgrade and legacy backfill tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/adaptive_learning.py backend/app/models/__init__.py backend/app/models/content.py backend/app/services/seed_bank.py backend/migrations/primary/versions/lp_0011_adaptive_diagnosis.py backend/tests/test_schema_migration.py backend/tests/test_adaptive_models.py backend/tests/test_adaptive_knowledge_nodes.py
git commit -m "feat(db): persist adaptive diagnosis state"
```

---

### Task 5: 可恢复诊断 Worker 与正确事务边界

**Files:**
- Create: `backend/app/services/diagnosis_job_service.py`
- Create: `backend/app/services/mastery_service.py`
- Create: `backend/run_diagnosis_worker.py`
- Modify: `backend/run_generation_worker.py`
- Modify: `docker-compose.yml`
- Test: `backend/tests/test_diagnosis_job_service.py`
- Test: `backend/tests/test_worker_transaction_boundaries.py`
- Test: `frontend/tests/docker-proxy-config.test.mjs`

**Interfaces:**
- Produces: `enqueue_diagnosis_job(db, answer_ref, user_id) -> DiagnosisJob`.
- Produces: `claim_diagnosis_job(db, worker_id, lease_seconds=120) -> ClaimedDiagnosisJob | None`.
- Produces: `process_diagnosis_job(session_factory: async_sessionmaker, job: ClaimedDiagnosisJob, provider: TutorProvider | None) -> None`.
- Produces: `update_mastery_once(db, diagnosis, correct) -> MasteryChange`.

- [ ] **Step 1: Write failing enqueue and claim tests**

Assert one task per answer, FIFO claim order, `SKIP LOCKED`, expired lease recovery, maximum attempts and safe failure reasons.

- [ ] **Step 2: Write transaction-boundary regression test**

Use an instrumented fake Provider and session factory. Assert the claim transaction has committed before `provider.generate()` starts, and the result transaction begins only after Provider completion. Apply the same assertion to the existing generation worker.

- [ ] **Step 3: Run worker tests and confirm failure**

Run: `cd backend; pytest tests/test_diagnosis_job_service.py tests/test_worker_transaction_boundaries.py -v`

Expected: missing diagnosis service and current generation-worker boundary failure.

- [ ] **Step 4: Implement claim DTO and three-phase worker**

Use a detached immutable DTO containing only job ID and answer reference. Never pass a session-bound ORM object across the external Provider call.

- [ ] **Step 5: Implement exactly-once result transaction**

Lock the job, check for an existing `AnswerDiagnosis`, insert diagnosis, lock or create `KnowledgeMasteryState`, update BKT, insert `AdaptationDecision`, and mark succeeded in one transaction. A unique diagnosis already present makes retry return the existing result without another BKT update.

- [ ] **Step 6: Refactor generation worker transaction boundary**

Keep existing job semantics, but split claim, Provider processing and result persistence so model latency no longer holds a transaction open.

- [ ] **Step 7: Add `diagnosis-worker` Compose service**

Reuse the backend image, secrets and primary database dependency. Use `command: ["python", "run_diagnosis_worker.py"]`; do not add Redis as a required dependency.

- [ ] **Step 8: Run worker and Compose contract tests**

Run: `cd backend; pytest tests/test_diagnosis_job_service.py tests/test_worker_transaction_boundaries.py -v`

Run: `cd frontend; npm test -- --test-name-pattern="docker"`

Expected: leases, idempotency and transaction boundary tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/diagnosis_job_service.py backend/app/services/mastery_service.py backend/run_diagnosis_worker.py backend/run_generation_worker.py docker-compose.yml backend/tests/test_diagnosis_job_service.py backend/tests/test_worker_transaction_boundaries.py frontend/tests/docker-proxy-config.test.mjs
git commit -m "feat(ai): add durable diagnosis worker"
```

---

### Task 6: 练习提交契约与幂等任务入队

**Files:**
- Modify: `backend/app/schemas/question.py`
- Modify: `backend/app/schemas/learning.py`
- Modify: `backend/app/models/ai_generated.py`
- Modify: `backend/app/models/learning.py`
- Create: `backend/migrations/primary/versions/lp_0012_answer_evidence.py`
- Modify: `backend/app/services/generated_practice_service.py`
- Modify: `backend/app/services/learning_service.py`
- Modify: `backend/app/services/behavior_service.py`
- Modify: `backend/app/api/v1/questions.py`
- Modify: `backend/app/api/v1/learning.py`
- Modify: `backend/tests/test_question_generation_api.py`
- Modify: `backend/tests/test_answer_submission_transaction.py`
- Modify: `backend/tests/test_behavior_service.py`

**Interfaces:**
- Extends: `GeneratedPracticeAnswerSubmit.solution_steps: list[str]` with maximum 12 items and 200 characters per item.
- Extends: `GeneratedPracticeAnswerSubmit.confidence: int | None` in `[1, 5]`.
- Extends: ordinary `AnswerSubmit` with the same optional evidence fields.
- Extends: each result with `diagnosis_job_id: UUID` and `diagnosis_status: Literal["pending", "succeeded"]`.
- Consumes: `enqueue_diagnosis_job()` from Task 5.

- [ ] **Step 1: Write backward-compatibility and validation tests**

Assert old generated-practice and ordinary-session payloads remain valid, 13 steps fail with 422, overlong steps fail, invalid confidence fails, and valid evidence is accepted.

- [ ] **Step 2: Extend payload fingerprint tests**

Assert changing only `solution_steps` or `confidence` while reusing a `submission_id` returns 409. Reordering unrelated JSON keys must not change the fingerprint.

- [ ] **Step 3: Write atomic enqueue tests**

Assert submission, answers, rewards and one job per answer commit together in both submission paths. Force job insert failure and verify the entire submit transaction rolls back. Replay returns original job IDs.

- [ ] **Step 4: Implement schema and persistence fields**

Persist bounded `solution_steps` and `student_confidence` on both `Answer` and `GeneratedPracticeAnswer` through `lp_0012_answer_evidence.py`. Do not edit the already committed `lp_0011` migration.

- [ ] **Step 5: Integrate enqueue in submission transaction**

Create jobs after each answer has a persistent ID. Do not call StepVerifier or Provider in either API request. Split `BehaviorService` so it continues updating daily study statistics and subject totals but no longer treats the legacy JSON `knowledge_mastery` map as the adaptive source of truth.

- [ ] **Step 6: Run submission regression tests**

Run: `cd backend; pytest tests/test_question_generation_api.py tests/test_answer_submission_transaction.py tests/test_behavior_service.py -v`

Expected: old contracts, new validation, fingerprint conflicts, rollback and replay all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/question.py backend/app/schemas/learning.py backend/app/models/ai_generated.py backend/app/models/learning.py backend/app/services/generated_practice_service.py backend/app/services/learning_service.py backend/app/services/behavior_service.py backend/app/api/v1/questions.py backend/app/api/v1/learning.py backend/migrations/primary/versions/lp_0012_answer_evidence.py backend/tests/test_question_generation_api.py backend/tests/test_answer_submission_transaction.py backend/tests/test_behavior_service.py
git commit -m "feat(practice): enqueue adaptive diagnosis"
```

---

### Task 7: 诊断查询与下一题接口

**Files:**
- Create: `backend/app/api/v1/adaptive.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/schemas/adaptive_learning.py`
- Create: `backend/app/services/adaptive_question_service.py`
- Modify: `backend/app/services/knowledge_graph_service.py`
- Modify: `backend/app/data/knowledge_graph.py`
- Test: `backend/tests/test_adaptive_api.py`
- Test: `backend/tests/test_adaptive_question_service.py`
- Modify: `backend/tests/test_knowledge_graph_service.py`
- Modify: `backend/tests/test_knowledge_graph_api.py`

**Interfaces:**
- Produces: `GET /api/v1/adaptive/diagnoses/jobs/{job_id}`.
- Produces: `GET /api/v1/adaptive/next?decision_id={uuid}`.
- Consumes: authenticated `user_id`; every query filters by task/decision owner.
- Produces public question DTO without `correct_answer` or `explanation`.
- Makes database `KnowledgeNode` and `KnowledgeMasteryState` the runtime source for adaptive knowledge and mastery data.

- [ ] **Step 1: Write authorization and state tests**

Cover missing job, another user's job, pending, succeeded, failed with safe message and soft-deleted user. Assert no internal failure reason, Prompt or answer is returned.

- [ ] **Step 2: Write next-question selection tests**

Order candidates by exact misconception match, target knowledge point, requested difficulty and least recent exposure. Exclude failed review questions and questions already answered in the current session.

- [ ] **Step 3: Run tests and confirm missing route/service failure**

Run: `cd backend; pytest tests/test_adaptive_api.py tests/test_adaptive_question_service.py -v`

- [ ] **Step 4: Implement owner-scoped diagnosis endpoint**

Pending returns HTTP 200 with a state DTO, not 404 or 202, so polling has one stable response contract. Failed returns a retryable boolean and safe user message.

- [ ] **Step 5: Implement deterministic next-question selection**

Return an existing question when possible. Only enqueue a GenerationJob when no approved candidate matches; return `pending_generation` and the existing job ID on repeated calls.

- [ ] **Step 6: Remove static mastery as a runtime source**

Keep `backend/app/data/knowledge_graph.py` only for subject/group presentation structure and legacy aliases. Resolve node title, prerequisites, difficulty and mastery from `KnowledgeNode` and `KnowledgeMasteryState`; do not average values from `behavior_profile.knowledge_mastery`.

- [ ] **Step 7: Run API tests**

Run: `cd backend; pytest tests/test_adaptive_api.py tests/test_adaptive_question_service.py tests/test_knowledge_graph_service.py tests/test_knowledge_graph_api.py -v`

Expected: state, authorization, redaction and deterministic selection tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/v1/adaptive.py backend/app/api/v1/router.py backend/app/schemas/adaptive_learning.py backend/app/services/adaptive_question_service.py backend/app/services/knowledge_graph_service.py backend/app/data/knowledge_graph.py backend/tests/test_adaptive_api.py backend/tests/test_adaptive_question_service.py backend/tests/test_knowledge_graph_service.py backend/tests/test_knowledge_graph_api.py
git commit -m "feat(api): expose adaptive learning decisions"
```

---

### Task 8: Tutor 与两层变式题流水线接入诊断证据

**Files:**
- Modify: `backend/app/ai/tutor/shared_state.py`
- Modify: `backend/app/ai/tutor/agents.py`
- Modify: `backend/app/ai/harness.py`
- Modify: `backend/app/ai/question_pipeline.py`
- Modify: `backend/app/ai/prompts/question_generation.py`
- Modify: `backend/app/ai/prompts/question_review.py`
- Modify: `backend/app/services/question_generation_service.py`
- Modify: `backend/tests/test_tutor_provider.py`
- Modify: `backend/tests/test_question_pipeline.py`

**Interfaces:**
- Consumes Tutor whitelist: diagnosis evidence, misconception display name, mastery band, next action and student message.
- Consumes generation constraint: target knowledge point, target misconception and parent question ID.
- Preserves: exactly Generator and Reviewer for question generation.

- [ ] **Step 1: Re-read and preserve existing uncommitted Tutor changes**

Confirm the current `student_message` behavior and its tests before editing. Do not reset or overwrite them.

- [ ] **Step 2: Write Tutor evidence tests**

Assert Tutor receives the verified first-invalid-step evidence and next action, but not `correct_answer`, full explanation, raw model output or internal Prompt. Assert missing diagnosis produces a neutral clarification strategy.

- [ ] **Step 3: Write constrained generation tests**

Assert the Generator Prompt includes target knowledge point and misconception, Reviewer rejects a question that does not exercise the target error pattern, and rejection feedback reaches the next generation attempt.

- [ ] **Step 4: Implement whitelist serialization**

Add typed fields to `SharedState`; do not pass the entire diagnosis ORM object or arbitrary context dictionary to Provider.

- [ ] **Step 5: Extend generation context without adding an Agent**

Use an internal `AdaptiveGenerationContext` rather than exposing misconception control on the general public generation request. Save target codes and policy version with the generated question.

- [ ] **Step 6: Run Tutor and pipeline tests**

Run: `cd backend; pytest tests/test_tutor_provider.py tests/test_question_pipeline.py -v`

Expected: current-question behavior, answer redaction, evidence use and two-layer constraints pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/ai/tutor/shared_state.py backend/app/ai/tutor/agents.py backend/app/ai/harness.py backend/app/ai/question_pipeline.py backend/app/ai/prompts/question_generation.py backend/app/ai/prompts/question_review.py backend/app/services/question_generation_service.py backend/tests/test_tutor_provider.py backend/tests/test_question_pipeline.py
git commit -m "feat(ai): ground tutoring in diagnosis evidence"
```

---

### Task 9: 解题步骤、诊断状态和自适应结果前端

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/app/(main)/ai-questions/practice-submission.mjs`
- Modify: `frontend/src/app/(main)/ai-questions/page.tsx`
- Create: `frontend/src/components/learning/solution-steps-input.tsx`
- Create: `frontend/src/components/learning/diagnosis-result.tsx`
- Create: `frontend/src/components/learning/mastery-change.tsx`
- Create: `frontend/src/components/learning/use-diagnosis-polling.ts`
- Modify: `frontend/tests/ai-question-generation.test.mjs`
- Create: `frontend/tests/adaptive-diagnosis.test.mjs`
- Modify: `frontend/e2e/delivery.spec.ts`

**Interfaces:**
- Consumes submission and adaptive APIs from Tasks 6 and 7.
- Produces optional ordered step strings and confidence 1–5.
- Polls every 1000 ms, stops after success, terminal failure, unmount or 10 attempts.

- [ ] **Step 1: Write request serialization tests**

Assert blank step rows are removed, nonblank order is preserved, confidence is omitted when unset, and a retry reuses the exact submission ID and payload.

- [ ] **Step 2: Write polling state tests**

Cover pending to success, 10-second timeout, navigation unmount, 401 refresh behavior, terminal safe failure and stale response from a previous question.

- [ ] **Step 3: Run frontend tests and confirm missing component failures**

Run: `cd frontend; npm test -- --test-name-pattern="adaptive|AI question"`

- [ ] **Step 4: Implement minimal step input**

Use an ordered list of text inputs with add/remove controls and a maximum of 12. Do not build a formula editor in MVP.

- [ ] **Step 5: Implement diagnosis presentation**

Render three explicit states: diagnosed, evidence insufficient and still processing. Display one-based error step, safe evidence, mastery before/after and whitelisted next-action reason.

- [ ] **Step 6: Implement polling with cancellation and stale-result protection**

Use `AbortController` and bind results to both `job_id` and current question ID before updating state.

- [ ] **Step 7: Add Playwright path**

Cover correct answer, diagnosed sign error and insufficient-evidence flows at desktop and mobile viewport. Assert browser console has no new error.

- [ ] **Step 8: Run frontend verification**

Run: `cd frontend; npm test`

Run: `cd frontend; npm run typecheck`

Run: `cd frontend; npm run build`

Expected: all tests, typecheck and production build pass.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/app/(main)/ai-questions/practice-submission.mjs frontend/src/app/(main)/ai-questions/page.tsx frontend/src/components/learning frontend/tests frontend/e2e/delivery.spec.ts
git commit -m "feat(ui): show evidence-based learning feedback"
```

---

### Task 10: 160 条离线评测集与 A/B/C 对照运行器

**Files:**
- Create: `backend/evals/__init__.py`
- Create: `backend/evals/equation_diagnosis/__init__.py`
- Create: `backend/evals/equation_diagnosis/schema.py`
- Create: `backend/evals/equation_diagnosis/cases.jsonl`
- Create: `backend/evals/equation_diagnosis/metrics.py`
- Create: `backend/evals/equation_diagnosis/runner.py`
- Create: `backend/tests/test_equation_eval_schema.py`
- Create: `backend/tests/test_equation_eval_metrics.py`
- Modify: `scripts/verify.py`
- Modify: `.github/workflows/verify.yml`

**Interfaces:**
- Produces CLI: `python -m evals.equation_diagnosis.runner --mode rules --output ../test/acceptance/adaptive-learning/rules.json`.
- Produces optional model modes: `direct-llm`, `structured-llm`, `hybrid`.
- Produces JSON report containing dataset version, git commit, model, Prompt version, Macro-F1, step accuracy, abstention recall, invalid-output rate, latency and Token distribution.

- [ ] **Step 1: Define and test strict evaluation-case Schema**

Each case includes ID, question, final answer, steps, correct flag, knowledge point, expected misconception, expected invalid transition, acceptable next actions, split and reviewer state. Reject duplicate IDs and unknown labels.

- [ ] **Step 2: Implement metric tests using a six-case hand-calculated fixture**

Test confusion matrix, per-class F1, Macro-F1, first-invalid-step accuracy, insufficient-evidence recall, hallucinated evidence rate and P50/P95 interpolation.

- [ ] **Step 3: Author exactly 160 versioned cases**

Distribution:

- 80 diagnostic errors across six concrete misconception classes.
- 30 valid alternative solution paths.
- 30 insufficient or ambiguous evidence cases.
- 20 malicious, overlong or unsupported syntax cases.

Reserve 40 cases as locked test split and mark them `reviewed_by_second_person=true` only after independent review; unreviewed cases remain in development split and do not contribute to final resume metrics.

- [ ] **Step 4: Implement four runner modes**

Rules mode is fully offline. Model modes require an explicit `--allow-provider` flag and fail closed when no key is configured. Never silently replace a requested model run with templates.

- [ ] **Step 5: Add deterministic CI gate**

CI validates all cases and runs rules mode. It does not call a paid Provider. Save output beneath the existing delivery-evidence artifact path.

- [ ] **Step 6: Run schema, metric and rules evaluation**

Run: `cd backend; pytest tests/test_equation_eval_schema.py tests/test_equation_eval_metrics.py -v`

Run: `cd backend; python -m evals.equation_diagnosis.runner --mode rules --output ../test/acceptance/adaptive-learning/rules.json`

Expected: 160 valid cases, deterministic report generated, no Provider call.

- [ ] **Step 7: Commit**

```bash
git add backend/evals/__init__.py backend/evals/equation_diagnosis backend/tests/test_equation_eval_schema.py backend/tests/test_equation_eval_metrics.py scripts/verify.py .github/workflows/verify.yml
git commit -m "test(ai): add equation diagnosis benchmark"
```

---

### Task 11: 全链路构建、Docker、浏览器验收与求职证据

**Files:**
- Modify only if verification exposes a defect: files owned by Tasks 1–10.
- Create via evaluation commands: `test/acceptance/adaptive-learning/*.json`
- Create via browser verification: `test/acceptance/adaptive-learning/screenshots/*.png`
- Create via delivery verification: existing report locations under `test/acceptance/`.

**Interfaces:**
- Consumes all prior tasks.
- Produces reproducible technical evidence; does not fabricate user growth or learning improvement.

- [ ] **Step 1: Run complete backend tests**

Run: `cd backend; pytest -v`

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend tests, typecheck and build**

Run: `cd frontend; npm test`

Run: `cd frontend; npm run typecheck`

Run: `cd frontend; npm run build`

Expected: all pass.

- [ ] **Step 3: Run migration drill**

Use the repository migration drill command documented in `docs/operations/schema-migrations.md` against an isolated disposable database. Verify upgrade to the new primary head, downgrade, re-upgrade and data preservation.

- [ ] **Step 4: Rebuild containers**

Run: `docker compose up -d --build`

Run: `docker compose ps`

Expected: frontend, backend, PostgreSQL, Redis, Nginx, generation worker and diagnosis worker are running or healthy as configured.

- [ ] **Step 5: Inspect relevant logs**

Run: `docker compose logs --since 10m backend generation-worker diagnosis-worker`

Expected: no migration mismatch, traceback, repeated lease crash, secret output or unbounded retry.

- [ ] **Step 6: Run real browser acceptance**

Using the internal browser, complete and screenshot:

1. Correct multi-step answer with mastery increase.
2. Sign-transfer error with first-invalid-step evidence and targeted next question.
3. Wrong final answer without steps, producing an explicit clarification request.
4. Mobile viewport for the diagnosis result and next-question action.

Check browser console and failed network requests after each state change.

- [ ] **Step 7: Run controlled model benchmark once**

Run A/B/C model modes against the locked reviewed split using the configured Provider. Record exact model name, Prompt version, dataset version, Token usage, P50/P95 and failure counts. Do not run if the locked split has not received the required independent review.

- [ ] **Step 8: Run the shared delivery gate**

Run: `python scripts/verify.py full`

Expected: delivery verification passes and evidence paths exist.

- [ ] **Step 9: Derive resume claims only from evidence**

Use the generated JSON report to write problem-design-evidence bullets. If Hybrid Macro-F1 is below `0.75`, step accuracy below `0.85`, abstention recall below `0.90`, or the safety set leaks an answer, report the actual result and continue improving before claiming the threshold.

- [ ] **Step 10: Close verification fixes in their owning task**

If verification exposes a defect, return to the task that owns that behavior, add the reproducing test, implement the minimal fix, rerun that task's focused checks and use its specified commit scope. Task 11 must not create a blanket commit or an empty commit.

## 5. 完成标准

The implementation is complete only when:

- All 11 tasks have their focused tests passing.
- No external model call occurs inside an open database transaction.
- Old submission clients remain compatible.
- Duplicate submissions cannot duplicate diagnosis, mastery or rewards.
- Unsafe equation strings are rejected without evaluation.
- Tutor receives verified evidence but no canonical answer.
- Generator remains exactly two layers.
- The 160-case dataset validates and the locked reviewed split is clearly separated.
- Docker, migrations, backend tests, frontend build and browser acceptance pass.
- Resume metrics are generated from stored evidence rather than manually invented.
