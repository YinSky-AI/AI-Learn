# AI 应用工程求职版学习系统改进设计

## 1. 文档目的

本文定义 AI-Learn 从“功能较全的通用 AI 学习平台”收敛为“面向初中数学错因诊断的自适应练习与辅导系统”的改进方向。目标不是继续增加页面、角色或热门框架，而是形成一条能被演示、测试、量化和解释的 AI 应用工程闭环。

目标投递岗位为：

- AI 应用工程师
- 大模型应用开发工程师
- Python AI 后端工程师
- 偏工程落地的 Agent / LLM 应用岗位

本设计不是大模型训练、微调或 AI Infra 项目，不把普通 Prompt 调用包装成模型算法创新。

## 2. 一句话定位

> 面向初中数学一元一次方程学习场景，依据学生的最终答案与可选解题步骤定位第一处可验证错误，更新知识点掌握度，选择针对性变式题或辅导策略，并通过离线评测集量化诊断质量、答案泄露、生成题质量、延迟和 Token 成本。

## 3. 为什么选择这个方向

### 3.1 当前项目的问题

当前项目已经覆盖课程、知识图谱、练习、错题、积分、AI 出题、AI 辅导和管理后台，但从招聘者视角仍存在以下问题：

1. 功能覆盖较宽，无法在短时间内说清最难、最独特的问题。
2. Generator、Reviewer 和四类 Tutor 主要体现工作流与 Prompt 编排，单独看不足以构成技术壁垒。
3. 现有掌握度采用固定比例更新，缺少教育测量模型和版本化参数。
4. 缺少人工标注评测集，无法证明 Reviewer、上下文辅导和答案防泄露是否有效。
5. 缺少业务效果、调用成本、延迟和稳定性等可复现数据。

### 3.2 选择“一元一次方程”的理由

一元一次方程适合作为第一个垂直切片：

- 解题步骤具有明确的等价变形规则，能够使用确定性程序验证。
- 常见错因可以形成有限、可解释的分类体系。
- 容易制作包含正确过程、典型错误过程和边界情况的评测集。
- 既能体现 LLM 的语义归类与教学表达，也能体现传统程序校验、数据建模和工程可靠性。
- 改造可以复用现有题目、知识节点、练习提交、Provider、Tutor、错题本和 CI，不需要推倒重做。

### 3.3 不选择的方向

- 不继续扩展语文、英语及更多学科。MVP 只支持初中数学一元一次方程。
- 不增加更多“Agent 角色”。诊断、教学和调度是明确职责的模块，不以角色数量作为卖点。
- 不为了简历关键词强行引入向量数据库。MVP 领域资料规模较小，按知识点和错因代码确定性检索更可靠。
- 不进行没有数据基础的模型微调。
- 不把 LLM-as-a-Judge 当作唯一正确答案。人工标注与确定性规则优先。

## 4. 当前代码事实与复用边界

### 4.1 已存在并保留的能力

| 能力 | 当前代码 | 改进中的作用 |
| --- | --- | --- |
| 统一模型调用 | `backend/app/ai/provider.py` 的 `AIProvider` | 继续负责并发、Token 预算、超时、重试和指标采集 |
| 生成—审核流水线 | `backend/app/ai/question_pipeline.py` 的 `QuestionPipeline` | 增加领域约束和评测，不增加第三层出题 Agent |
| 批次生成与保存 | `backend/app/services/question_generation_service.py` | 保存针对错因生成的变式题和来源关系 |
| 可恢复生成任务 | `backend/app/services/question_generation_service.py` 的租约、领取和重试逻辑 | 复用同一模式实现诊断任务，不在数据库事务中等待外部模型 |
| 原子练习提交 | `backend/app/services/generated_practice_service.py` | 在同一事务内保存作答、积分结果和唯一诊断任务；掌握度在任务结果事务中更新 |
| 辅导编排 | `backend/app/ai/harness.py` 与 `backend/app/ai/tutor/` | 消费诊断证据和下一步策略，不自行猜测错因 |
| 知识点 | `backend/app/models/content.py` 的 `KnowledgeNode` | 作为正式知识点主数据及前置依赖来源 |
| 学习行为 | `backend/app/services/behavior_service.py` | 从固定比例更新迁移到版本化掌握度服务 |
| 错题复习 | `backend/app/models/wrong_book.py` | 展示错因、复习目标和后续掌握情况 |
| 自动化交付 | `.github/workflows/verify.yml`、pytest、Playwright | 加入离线评测和垂直闭环验收 |

### 4.2 需要纠正的现有边界

1. `backend/app/data/knowledge_graph.py` 当前维护静态知识图谱，而数据库也存在 `KnowledgeNode`。改进后以数据库知识节点为运行时唯一事实来源，静态文件只用于种子数据和别名映射，避免两套知识图谱漂移。
2. `BehaviorService` 当前把知识掌握度保存在用户画像 JSON 中，并按答对增加、答错减少的固定比例更新。改进后掌握度进入独立关系表，使用版本化 BKT 参数更新；用户画像只保留展示统计，不再作为掌握度事实来源。
3. Tutor 当前能够获取题目、学生答案和用户问题，但尚无经过验证的“第一处错误证据”。改进后 Tutor 只能引用诊断记录中的证据或明确表示证据不足。
4. 现有 Reviewer 判断整批题目是否通过，但缺少稳定的离线基准。改进后所有 Prompt 或模型变更必须运行同一版本评测集。

## 5. 目标用户与核心任务

### 5.1 目标用户

- 初中阶段正在学习一元一次方程的学生。
- 学生可能只能提交最终答案，也可能愿意填写逐步解题过程。
- 系统不假定学生提交的自由文本一定可信或完整。

### 5.2 核心任务

学生完成一道方程题后，系统必须回答四个问题：

1. 这道题是否答对？
2. 如果答错，哪一步首先不再与上一步等价？
3. 有足够证据时，它属于哪类错因；证据不足时还需要问什么？
4. 下一步最合适的是复习前置知识、做一道针对性变式题，还是提高难度？

### 5.3 MVP 演示脚本

演示只需要三名虚拟学生状态，不依赖伪造大规模真实用户：

1. 学生 A 在移项时符号错误。系统标出第一处无效变形，归类为 `sign_transfer_error`，推送一道只考查移项符号的变式题。
2. 学生 B 只提交错误最终答案，没有步骤。系统返回 `insufficient_evidence`，先追问一个诊断问题，不凭空断言错因。
3. 学生 C 连续正确完成同一技能题。BKT 掌握度上升，系统选择混合步骤或更高难度题，并展示选择理由。

## 6. 领域模型

### 6.1 MVP 知识点

初始版本只维护以下可观察技能：

| 代码 | 名称 | 前置技能 |
| --- | --- | --- |
| `equation_equivalence` | 等式与等价变形 | 无 |
| `distributive_expansion` | 去括号与分配律 | `equation_equivalence` |
| `combine_like_terms` | 合并同类项 | `distributive_expansion` |
| `move_terms_sign` | 移项与符号变化 | `equation_equivalence` |
| `normalize_coefficient` | 系数化为 1 | `equation_equivalence` |
| `equation_word_modeling` | 应用题列方程 | 上述技能 |

MVP 的自动步骤校验先覆盖前五项；应用题列方程作为扩展评测，不阻塞首个闭环。

### 6.2 错因分类

| 代码 | 含义 | 最低证据要求 |
| --- | --- | --- |
| `balance_violation` | 只对等式一侧执行运算 | 相邻两步方程不等价，且只改变一侧 |
| `sign_transfer_error` | 移项后符号未改变或错误改变 | 相邻步骤包含跨等号移动项并出现符号错误 |
| `distribution_error` | 去括号时漏乘或符号展开错误 | 上一步包含括号，下一步展开不等价 |
| `combine_like_terms_error` | 错误合并不同类项或系数 | 相邻步骤结构表明在执行合并同类项 |
| `coefficient_normalization_error` | 最后除以系数时运算错误 | 已形成 `ax=b`，下一步求解错误 |
| `arithmetic_slip` | 可定位的基础计算错误 | 变形策略正确但数值计算不正确 |
| `multiple_possible_causes` | 证据支持多种错因，无法唯一归类 | 至少两个类别置信度接近 |
| `insufficient_evidence` | 只有最终答案或步骤不足 | 无法定位第一处无效变形 |

分类器必须允许拒答。把证据不足当作正式结果，是本项目区别于普通 LLM 猜测式诊断的重要设计。

## 7. 目标架构

```text
练习页面
  │  最终答案 + 可选解题步骤 + 自评置信度
  ▼
练习提交短事务
  ├─ 服务端判题与幂等保存
  └─ 写入唯一诊断任务后立即提交，不等待外部模型
         │
         ▼
可恢复 DiagnosisWorker
  ├─ StepVerifier：寻找第一处不等价步骤
  ├─ DiagnosisService：规则优先，LLM 结构化归类，证据不足则拒答
  └─ 结果短事务
       ├─ 保存诊断
       ├─ MasteryService：按技能更新 BKT 状态
       └─ AdaptivePolicy：选择追问、补救题、同级变式或进阶题
              │
              ├─ 复用现有题库
              └─ 必要时调用 Generator—Reviewer 生成受约束变式题
  ▼
结果页轮询诊断状态 / 错题本 / Tutor
  ├─ 展示第一处错误证据
  ├─ 展示掌握度变化和原因
  └─ 基于同一诊断证据进行辅导，不泄露标准答案
```

### 7.1 组件职责

#### StepVerifier

- 输入：规范化方程、学生步骤列表。
- 输出：每相邻两步是否等价、第一处无效步骤、可观察运算特征。
- 实现原则：使用受限数学表达式解析器；拒绝函数调用、属性访问和非允许字符，禁止直接 `eval`。
- 不负责生成教学文案，也不推断学生心理状态。

#### DiagnosisService

- 优先使用 StepVerifier 的确定性特征匹配错因。
- 规则无法唯一归类但证据充分时，调用 Provider 获得结构化分类。
- 校验 LLM 返回的枚举、证据引用和置信度。
- LLM 引用了输入中不存在的步骤时，结果降级为 `insufficient_evidence`。

#### DiagnosisWorker

- 复用现有生成任务的 `queued → running → succeeded / failed`、租约和 `FOR UPDATE SKIP LOCKED` 模式。
- 领取任务的事务只负责设置租约，随后立即提交；StepVerifier 和外部 Provider 调用不持有数据库事务或行锁。
- 得到诊断后开启新的短事务，以答案事件为幂等键保存诊断、更新掌握度并创建自适应决策。
- Worker 崩溃或租约到期后任务可以被其他 Worker 重新领取，重复执行不得产生重复状态更新。

#### MasteryService

- 以用户和知识点为粒度维护掌握概率。
- 使用版本化 BKT 参数，保证同一模型版本可复现。
- 同一个持久化答案事件只能更新一次。
- 不因 LLM 的高置信度直接修改掌握度；掌握度主要由已判定作答结果更新。

#### AdaptivePolicy

- 输入：当前掌握度、错因、诊断置信度、最近作答和知识前置关系。
- 输出：下一动作及机器可读理由。
- 第一版使用确定性规则，不让 LLM 自由决定业务动作。
- 只有确定需要新题且题库无合适题目时，才调用生成流水线。

#### TutorAdapter

- 把诊断证据、掌握度和下一动作加入现有 `SharedState`。
- Tutor 负责教学表达，不重新判断答案和错因。
- 对学生展示的回复不得包含标准答案、完整解析或内部 Prompt。

#### EvaluationRunner

- 从版本化 JSONL 数据集运行诊断、生成和安全评测。
- 输出 JSON 与 Markdown 摘要，记录代码版本、数据集版本、Prompt 版本和模型配置。
- 人工标签是主标准；LLM 评分只能作为辅助维度。

## 8. 关键数据契约

### 8.1 学生解题证据

```python
class SolutionEvidence(BaseModel):
    final_answer: str
    solution_steps: list[str] = Field(default_factory=list, max_length=12)
    confidence: int | None = Field(default=None, ge=1, le=5)
```

边界：

- 每一步最多 200 个字符。
- 最多 12 步。
- 前后端都保留原始文本，数学校验使用独立规范化结果。
- 没有步骤时允许正常提交，但诊断通常返回 `insufficient_evidence`。

### 8.2 诊断结果

```python
class ErrorDiagnosisResult(BaseModel):
    status: Literal["diagnosed", "insufficient_evidence", "not_required"]
    misconception_code: str | None
    knowledge_point_code: str
    first_invalid_step: int | None
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["rule", "hybrid", "fallback"]
    prompt_version: str | None
    model_name: str | None
```

强约束：

- 正确作答返回 `not_required`。
- `diagnosed` 必须包含错因代码、知识点、证据和第一处错误步骤。
- `insufficient_evidence` 不得伪造第一处错误步骤。
- `evidence` 必须是对输入步骤的短引用或确定性校验摘要。

### 8.3 自适应决策

```python
class AdaptationDecision(BaseModel):
    action: Literal[
        "ask_diagnostic_question",
        "review_prerequisite",
        "practice_misconception",
        "practice_same_skill",
        "increase_difficulty",
    ]
    target_knowledge_point_code: str
    target_misconception_code: str | None
    reason_codes: list[str]
    policy_version: str
```

API 只向前端返回可展示理由，不暴露内部 Prompt、标准答案或模型原始响应。

## 9. 掌握度算法

### 9.1 使用 BKT 而不是固定加减比例

每个知识点保存：

- `p_known`：当前掌握概率
- `p_learn`：一次练习后学会的概率
- `p_slip`：已掌握但答错的概率
- `p_guess`：未掌握但答对的概率
- `model_version`：参数版本
- `last_answer_id`：最近处理事件，用于追踪

初始 MVP 参数固定并版本化：

```text
p_initial = 0.35
p_learn   = 0.15
p_slip    = 0.10
p_guess   = 0.20
model_version = bkt-equation-v1
```

正确时：

```text
posterior = p_known * (1 - p_slip)
            / (p_known * (1 - p_slip) + (1 - p_known) * p_guess)
```

错误时：

```text
posterior = p_known * p_slip
            / (p_known * p_slip + (1 - p_known) * (1 - p_guess))
```

完成观测后：

```text
p_known_next = posterior + (1 - posterior) * p_learn
```

这些参数不是声称经过训练的最优值，而是可复现的 MVP 初始值。后续只能依据评测或真实使用数据发布新版本，不能在代码中静默修改。

### 9.2 自适应规则 v1

| 条件 | 动作 |
| --- | --- |
| 错误且证据不足 | 追问一个诊断问题 |
| 错误且错因明确 | 生成或选择一道只覆盖该错因的补救题 |
| `p_known < 0.40` | 回到前置知识点 |
| `0.40 <= p_known < 0.75` | 同知识点、同级难度变式题 |
| `p_known >= 0.75` 且最近两次正确 | 提升难度或加入多步骤混合题 |
| 最近两次出现相同错因 | 保持难度并切换讲解策略，不立即升级 |

决策必须保存 `reason_codes`，使页面和面试演示都能解释“为什么推荐这道题”。

## 10. 数据库设计

### 10.1 新增表

#### `answer_diagnoses`

- `id`
- `user_id`
- `standard_answer_id`：可空，关联普通题作答
- `generated_answer_id`：可空，关联 AI 生成题作答
- `status`
- `knowledge_point_code`
- `misconception_code`
- `first_invalid_step`
- `evidence`
- `confidence`
- `source`
- `input_snapshot`：脱敏后的题目与步骤快照
- `prompt_version`
- `model_name`
- `latency_ms`
- `token_usage`
- `created_at`

数据库约束要求两个答案外键恰好一个非空，并分别建立唯一约束，保证一次答案事件只产生一个最终诊断。

#### `diagnosis_jobs`

- `id`
- `standard_answer_id`：可空
- `generated_answer_id`：可空
- `status`：`queued / running / succeeded / failed`
- `attempts`
- `max_attempts`
- `lease_owner`
- `lease_expires_at`
- `failure_reason`：只保存安全错误分类
- `created_at`
- `updated_at`

两个答案外键恰好一个非空，并分别唯一。任务领取使用跳过锁行和有限租约；外部模型调用不在领取事务中执行。

#### `knowledge_mastery_states`

- `user_id`
- `knowledge_node_id`
- `p_known`
- `model_version`
- `observation_count`
- `last_answer_ref`
- `updated_at`

`(user_id, knowledge_node_id, model_version)` 唯一。

#### `adaptation_decisions`

- `id`
- `user_id`
- `diagnosis_id`
- `action`
- `target_knowledge_node_id`
- `target_misconception_code`
- `reason_codes`
- `policy_version`
- `selected_question_id` 或 `generated_question_id`
- `created_at`

### 10.2 代码配置而非数据库表

错因目录和 BKT 参数首版使用版本化 Python/YAML 配置，不建设管理后台。原因是分类数量有限、需要代码评审和测试，不应允许后台静默修改核心算法。

### 10.3 迁移策略

1. 创建新表和约束，不删除现有字段。
2. 从 `behavior_profile.knowledge_mastery` 为已知知识点生成初始 `knowledge_mastery_states`，无法映射的旧标签只保留在历史报告中。
3. 新作答统一写入新掌握度表。
4. 学习报告改为从新表读取知识点掌握度，旧 JSON 继续提供学习时长和每日统计。
5. 完成一轮迁移与回滚演练后，停止更新 JSON 中的 `knowledge_mastery`，但暂不删除历史数据。

## 11. API 与页面行为

### 11.1 练习提交

复用现有提交接口，在单题答案中增加：

```json
{
  "question_id": "uuid",
  "user_answer": "x=4",
  "solution_steps": ["2(x+1)=10", "2x+2=10", "2x=8", "x=4"],
  "confidence": 4,
  "time_spent_seconds": 52
}
```

提交响应中的每题结果先增加可恢复状态：

```json
{
  "diagnosis_status": "pending",
  "diagnosis_job_id": "uuid"
}
```

前端通过 `GET /api/v1/adaptive/diagnoses/jobs/{diagnosis_job_id}` 轮询。诊断完成后的响应为：

```json
{
  "diagnosis": {
    "status": "diagnosed",
    "misconception_code": "sign_transfer_error",
    "first_invalid_step": 2,
    "evidence": "从第 1 步到第 2 步移项后常数项符号未改变",
    "confidence": 0.93
  },
  "mastery": {
    "before": 0.46,
    "after": 0.31,
    "model_version": "bkt-equation-v1"
  },
  "next_action": {
    "action": "practice_misconception",
    "reason_codes": ["repeated_sign_transfer_error"]
  }
}
```

现有 `submission_id`、请求指纹和事务锁语义保持不变。相同提交重放返回同一个诊断任务，不得重复创建任务、重复更新掌握度或重复发放积分。前端最多主动轮询 10 秒，未完成时保留“诊断中”状态，用户稍后重新进入错题详情仍能读取最终结果。

### 11.2 下一题

新增 `GET /api/v1/adaptive/next`，根据最近一次自适应决策返回：

- 已有题库中的题目；或
- 已完成 Reviewer 审核的生成题；或
- `pending_generation`，由前端显示可恢复等待状态。

接口不得同步等待无限时长的生成任务。生成超时后保留决策记录，用户可以重试获取，不重复创建任务。

### 11.3 错题详情

错题详情新增三个区域：

1. “从哪一步开始出错”：显示学生步骤和第一处错误证据。
2. “当前需要巩固”：显示错因与知识点，不展示模型置信度术语给低龄用户。
3. “为什么推荐下一题”：展示经过白名单映射的决策理由。

### 11.4 AI 辅导

Tutor 接收以下白名单字段：

- 当前题干
- 学生提交步骤
- 第一处无效步骤及证据
- 错因名称
- 当前掌握度区间
- 下一动作
- 学生当前问题
- 最近十轮对话

标准答案和完整解析继续排除在 Tutor Prompt 之外。若教学策略确实需要答案校验，由服务端预先产生布尔或枚举结果，不直接把机密字段交给 Tutor。

## 12. 受控领域资料

MVP 不使用通用网页检索，也不引入向量数据库。建立版本化本地资料：

- 每个知识点的定义、前置知识和允许的变形规则。
- 每类错因的正例、反例和最小证据要求。
- 每种自适应动作对应的教学策略。
- 禁止直接泄露答案的表达规则。

检索方式为：

```text
knowledge_point_code + misconception_code + action
→ 精确定位领域资料片段
→ 组装 Tutor 或 Generator 上下文
```

当资料规模超过 200 个独立片段，且同一问题需要跨多个章节语义检索时，再评估 PostgreSQL `pgvector`；此前不为简历关键词增加无必要基础设施。

## 13. 评测设计

### 13.1 数据集

建立 `equation-diagnosis-v1`，共 160 个固定样本：

- 80 个典型错误步骤：六类可诊断错因。
- 30 个正确但写法不同的等价步骤，防止误报。
- 30 个证据不足或多种可能原因样本，评估拒答能力。
- 20 个安全与鲁棒性样本，包括 Prompt 注入、超长步骤和非法表达式。

每条记录包含：

- 题目和标准方程
- 学生最终答案与步骤
- 知识点标签
- 人工错因标签
- 第一处错误步骤
- 证据摘要
- 期望的下一动作集合
- 标注者和数据集版本

至少 40 条测试样本需要由第二名具备初中数学能力的人独立复核；存在分歧的样本不进入锁定测试集。

### 13.2 基线实验

必须保留三组可复现实验：

| 组别 | 方法 | 目的 |
| --- | --- | --- |
| A | 仅 LLM，根据题目和答案直接诊断 | 测量普通 Prompt 方案 |
| B | LLM + 结构化输出 + 错因目录 | 测量约束输出价值 |
| C | StepVerifier + 规则 + LLM 归类 + 拒答 | 测量推荐方案价值 |

### 13.3 指标与通过标准

| 维度 | 指标 | 首版通过标准 |
| --- | --- | --- |
| 诊断 | 错因 Macro-F1 | C 组不低于 0.75，且高于 A 组 |
| 定位 | 第一处错误步骤准确率 | 不低于 0.85 |
| 拒答 | 证据不足识别召回率 | 不低于 0.90 |
| 可靠性 | 结构化结果合法率 | 不低于 0.99 |
| 安全 | 虚构步骤证据率 | 不高于 0.02 |
| 安全 | Tutor 标准答案泄露 | 锁定安全集为 0 |
| 出题 | 人工审核通过率 | 不低于 0.85，并报告相对单次生成的差异 |
| 成本 | 每次诊断 Token | 输出均值、P50、P95，不伪设优化结论 |
| 延迟 | 端到端诊断延迟 | 输出 P50、P95，并拆分规则与模型耗时 |
| 幂等 | 同一提交并发重放 | 只产生一次诊断和一次掌握度更新 |

未达到阈值时不得在简历中写“提升准确率”或“显著降低泄露”；只能如实描述已实现的机制和当前测量结果。

## 14. 可观测性与故障处理

每次诊断记录：

- `request_id`、`run_id`
- 数据集或在线请求来源
- 规则版本、Prompt 版本、模型名称
- 是否调用 LLM
- Provider 延迟和 Token
- 诊断状态与降级原因

日志不得记录：

- API 密钥
- 完整系统 Prompt
- 用户身份信息
- 完整学生历史数据
- 标准答案和完整解析

故障策略：

| 故障 | 行为 |
| --- | --- |
| 数学表达式无法解析 | 保存作答，诊断返回证据不足 |
| Provider 超时或限流耗尽 | 保存作答，使用规则结果；无规则结果则返回证据不足 |
| LLM 返回未知错因 | 丢弃模型分类，不写入未知业务状态 |
| Worker 在 Provider 调用期间退出 | 租约到期后重新领取，不影响已提交作答 |
| 诊断结果或掌握度更新失败 | 诊断结果短事务回滚，任务进入有限重试，作答记录不回滚 |
| 变式题生成失败 | 保留下一动作，优先返回已有补救题或可恢复等待状态 |

## 15. 实施阶段

### 阶段 0：冻结基线，2 天

交付：

- 固定当前 Generator—Reviewer、Tutor 和掌握度行为。
- 建立 160 条评测数据的数据格式与首批锁定测试集。
- 跑出 A 组基线的质量、延迟和 Token 数据。

验收：

- 数据集可通过 Schema 校验。
- 同一版本连续运行结果可追踪。
- 基线报告明确记录模型与 Prompt 版本。

### 阶段 1：证据采集与确定性步骤校验，3～4 天

交付：

- 练习输入支持可选解题步骤和自评置信度。
- 安全表达式解析与相邻步骤等价性检查。
- 正确、错误、无法解析、恶意表达式的单元测试。

验收：

- 不使用 Python `eval`。
- 非法输入不会执行代码或暴露堆栈。
- 正确等价变形不被误判，典型错误能定位第一处步骤。

### 阶段 2：错因诊断与掌握度，4～5 天

交付：

- 错因目录、DiagnosisService 和结构化 Provider 调用。
- `diagnosis_jobs`、`answer_diagnoses` 与 `knowledge_mastery_states` 迁移。
- 可恢复 DiagnosisWorker，外部模型调用与数据库事务分离。
- BKT 更新、事件幂等和历史画像迁移。

验收：

- 同一个答案事件只能更新一次。
- 慢速 Provider 不会延长练习提交事务和数据库行锁持有时间。
- Provider 不可用时仍能保存作答并安全降级。
- 数据库迁移升级、回滚和旧数据映射演练通过。

### 阶段 3：自适应策略与 Tutor 接入，3～4 天

交付：

- 确定性 AdaptivePolicy。
- 下一题接口和针对错因的变式题约束。
- 错题详情证据展示与 Tutor 诊断上下文。

验收：

- 每个决策都包含可追踪理由。
- Tutor 不自行重判错因。
- 重复请求不重复生成任务。
- 内部浏览器完成三种 MVP 演示状态并保存截图。

### 阶段 4：评测、性能与求职材料，3 天

交付：

- A/B/C 三组离线评测。
- 并发重放、外部模型超时和成本统计。
- 三分钟演示脚本、架构图和基于实测结果的简历条目。

验收：

- 评测命令可以在新环境重复运行。
- CI 对锁定数据集运行无外部依赖的规则测试；真实模型评测通过手动任务执行，避免每次提交消耗额度。
- 简历中的每个数字都能定位到评测产物或测试报告。

预计总工期为 15～18 个有效开发日。若秋招时间更紧，阶段 0～2 构成最小可投递版本；阶段 3 完成后形成完整演示闭环。

## 16. 预计代码落点

### 新增

- `backend/app/domain/equation_taxonomy.py`：知识点与错因枚举、证据要求。
- `backend/app/domain/equation_verifier.py`：安全解析和步骤等价性验证。
- `backend/app/services/diagnosis_service.py`：规则与 LLM 混合诊断。
- `backend/app/services/diagnosis_job_service.py`：任务领取、租约、重试和结果提交。
- `backend/app/services/mastery_service.py`：版本化 BKT 更新。
- `backend/app/services/adaptive_policy.py`：下一动作规则。
- `backend/app/models/adaptive_learning.py`：诊断、掌握度和决策模型。
- `backend/app/schemas/adaptive_learning.py`：输入输出 DTO。
- `backend/app/api/v1/adaptive.py`：下一动作与下一题查询。
- `backend/app/ai/prompts/error_diagnosis.py`：受约束诊断 Prompt。
- `backend/app/data/equation_misconceptions.py`：版本化错因资料。
- `backend/evals/equation_diagnosis/`：锁定数据集、运行器和结果 Schema。
- `backend/tests/test_equation_verifier.py`
- `backend/tests/test_diagnosis_service.py`
- `backend/tests/test_mastery_service.py`
- `backend/tests/test_adaptive_policy.py`
- `backend/tests/test_adaptive_integration.py`

### 修改

- `backend/app/services/generated_practice_service.py`：在幂等事务中接入诊断、掌握度和决策。
- `backend/app/services/behavior_service.py`：掌握度读取切换到关系表。
- `backend/app/ai/tutor/shared_state.py`：加入白名单诊断证据和下一动作。
- `backend/app/ai/tutor/agents.py`：根据确定的教学策略组织回复。
- `backend/app/ai/question_pipeline.py`：接收目标知识点和错因约束，不改变两层 Agent 数量。
- `backend/app/models/ai_generated.py`：补充变式题的目标错因与策略版本。
- `backend/app/schemas/question.py`：增加解题步骤、置信度和诊断响应。
- `backend/app/api/v1/questions.py`：扩展提交响应并保持兼容。
- `backend/app/api/v1/router.py`：注册自适应接口。
- `frontend/src/types/api.ts`：同步接口契约。
- `frontend/src/components/learning/answer-feedback.tsx`：展示错误证据和下一动作。
- `frontend/src/components/ai/tutor-chat.tsx`：展示基于证据的辅导状态。
- `.github/workflows/verify.yml`：加入锁定评测数据的确定性门禁。

文件名在实施前应再次以仓库最新状态核验；不为追求目录整齐重构与本闭环无关的模块。

## 17. 测试策略

### 单元测试

- 数学表达式允许列表和恶意输入拒绝。
- 每类典型错因的第一处步骤定位。
- BKT 正确、错误和边界概率计算。
- AdaptivePolicy 每条规则与优先级。
- LLM 结构不合法、证据虚构和未知枚举降级。

### 集成测试

- 普通题与生成题均能产生诊断。
- 相同 `submission_id` 并发请求只更新一次。
- 作答与积分在提交事务内保持一致；诊断、掌握度和决策在任务结果事务内保持一致。
- Worker 崩溃、租约过期和重复领取不会产生重复诊断或重复掌握度更新。
- Provider 超时后作答可保存且响应不暴露内部错误。
- 旧客户端不传 `solution_steps` 时保持兼容。

### UI 验收

- 正确答案：不显示虚假错因。
- 可诊断错误：标出第一处错误步骤和推荐原因。
- 证据不足：展示追问，不宣称已识别错因。
- 手机与桌面布局均可完成下一题流程。
- AI 辅导窗口不显示标准答案和内部字段。

### 性能与故障测试

- 20 个并发用户重复提交同一请求。
- 受控上游模拟 429、超时和 5xx。
- 记录规则路径与模型路径的 P50/P95。
- 验证 Provider 并发限制是单进程语义，不宣传为分布式限流。

## 18. 求职呈现方式

### 18.1 项目名称

使用：

> 初中数学错因诊断与自适应练习系统

副标题可以是：

> 基于确定性步骤校验、LLM 结构化诊断与 BKT 学习状态建模

不再以“智慧学习平台”“多 Agent 教育平台”作为主标题。

### 18.2 简历内容生成规则

每条简历描述必须满足“问题—设计—证据”结构：

```text
问题：普通 LLM 会根据错误最终答案猜测错因。
设计：先校验相邻方程步骤，再让 LLM 在固定错因目录中归类，证据不足时拒答。
证据：引用锁定评测集中的 Macro-F1、错误步骤准确率和拒答召回率。
```

在阶段 4 完成前，只描述机制，不填写尚未测量的提升百分比。

### 18.3 面试必须能够回答的问题

1. 为什么 Provider 不能负责选择教学策略？
2. 为什么不让 LLM 直接判断所有错因？
3. 如何验证两步方程是否等价，如何防止表达式注入？
4. 为什么只有最终答案时应该拒绝诊断？
5. BKT 相比正确率有什么优势，参数从哪里来？
6. 为什么 MVP 不使用向量数据库？
7. Reviewer 带来了多少质量收益，又增加了多少成本和延迟？
8. 并发重复提交为什么不会重复更新掌握度？
9. 如何区分模型输出校验、业务规则和数据库一致性？
10. 哪些指标来自人工标注，哪些只是模型辅助评分？

若这些问题无法结合代码、测试和数据回答，项目仍然容易被判断为 AI 辅助拼装。

## 19. 明确停止扩展的内容

在本改进完成前，不新增：

- 新学科和新年级。
- 第五种 Tutor 角色或第三层出题 Agent。
- 社区、直播、支付、商城和社交功能。
- 通用联网搜索和网页爬取。
- 没有数据支持的模型微调。
- 独立微服务拆分、Kubernetes 和分布式限流。
- 仅为了展示技术名词而增加的向量数据库或 Agent 框架。

现有非核心功能可以继续运行，但不进入主演示路径和简历核心描述。

## 20. 最终完成定义

只有同时满足以下条件，项目才可以对外表述为“面向 AI 应用工程岗位完成垂直化”：

1. 一元一次方程错因目录、步骤校验、诊断、BKT 和自适应决策全部进入真实作答链路。
2. 旧客户端和原有练习流程保持兼容，重复提交与事务一致性验证通过。
3. 160 条版本化评测集能够重复运行，A/B/C 三组结果完整。
4. 诊断与安全指标达到本文阈值，未达到的指标在报告和简历中如实披露。
5. 内部浏览器完成正确、可诊断错误、证据不足三类真实操作验收。
6. Docker Compose 服务健康，相关测试、前端构建和 CI 门禁通过。
7. 三分钟演示能清楚展示“证据—诊断—掌握度—下一题”闭环。
8. 简历中的每个技术结论和数字都能指向代码、测试或评测产物。

达到以上标准后，这个项目的核心竞争力不再是“做了一个带 AI 的学习网站”，而是：

> 能够把不稳定的大模型能力约束在可验证的领域流程中，并同时处理数据契约、评测、成本、失败降级、事务一致性和用户体验。
