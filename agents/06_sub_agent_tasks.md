# 子 Agent 任务分工 (06)

> **文件标识**: agents/06_sub_agent_tasks.md
> **关联文件**: 引用 00-05 所有文件；作为多 Agent 协作的工作协议。
> **权威说明**: 本文件是 Agent 角色定义、接口契约和协作协议的唯一权威来源。`agent.md` §3.2 做摘要引用，`04_architecture.md` §3.4 做职责边界映射。

---

## 1. 协作模式

多 Agent 采用 **闭环控制模式**，基于工程控制论原理设计。系统分为三层 Loop：内环（出题级闭环）、外环（系统级监控与进化）、学习环（Hermes 自进化）。

```
┌──────────────────────────────────────────────────────────────────┐
│                        主 Agent (Main Orchestrator)               │
│   职责:                                                          │
│   1. 解读用户需求，分发任务                                        │
│   2. 维护全局上下文和进度                                         │
│   3. 处理冲突和依赖                                               │
│   4. 最终审核和提交                                               │
│   5. 在Agent设计相关任务中，引用本文件的权威定义                    │
├──────────────────────────────────────────────────────────────────┤
│                     内环 — 出题级闭环                              │
│                                                                  │
│  CourseIntentAgent (L1) → QuestionPlannerAgent (L2)              │
│       ↓                                                          │
│  QuestionMemoryAgent (L3) → QuestionGeneratorAgent (L4)          │
│       ↓                                                          │
│  QualityCheckAgent (L5) → SafetyAuditAgent (L6)                 │
│       ↓                      QualityReviewAgent (L6)             │
│  FeedbackAggregator (L7) ←── 汇聚偏差信号                        │
│       └──→ 控制信号注入 L2/L3/L4 的下一次循环                     │
├──────────────────────────────────────────────────────────────────┤
│                     学习环 — 进化级                               │
│                                                                  │
│  SummaryAgent (L8)                                                │
│    → 记忆提炼 → Skill创建 → Skill自改进 → 用户建模               │
│    → 跨会话召回 → 进化触发                                       │
├──────────────────────────────────────────────────────────────────┤
│                     外环 — 系统级                                 │
│                                                                  │
│  ErrorLogger Middleware (贯穿所有层)                              │
│    → 实时捕获 → 四类分类 → 路由处理 → 持久化学习                  │
└──────────────────────────────────────────────────────────────────┘
```

**与旧版星型模式的区别**：
- 旧版：主Agent分发 → 子Agent独立执行 → 结果返回主Agent（无反馈）
- 新版：Agent间通过接口契约形成闭环，偏差信号通过 FeedbackAggregator 自动回流，无需主Agent介入反馈路径

---

## 2. 子 Agent 角色定义

### 2.1 前端 Agent

**职责范围**:
- Next.js 页面开发与组件实现
- Tailwind + shadcn/ui 主题定制
- 年龄分级 UI 适配
- 前端状态管理 (Zustand)
- API 客户端集成
- 动画与交互反馈

**关键约束**:
- 所有组件优先使用 shadcn/ui 基础组件二次封装
- 不使用第三方 UI 库替代 Tailwind 原生方案
- 每个页面必须覆盖 loading / empty / error 三种状态
- 响应式设计 Mobile First
- Desktop `1440x900` 页面必须严格符合 `design_imgs` 样例图的样式风格
- 样例图中的英文不得照搬为最终产品文案；页面导航、标题、按钮、卡片、弹窗、题目和 AI 文案必须使用自然简体中文
- 不得在样例图之外自行添加营销 Hero、深色主题、重渐变背景或额外解释性文案
- 页面开发顺序必须是先建立样例图风格基线，再接入真实 API 和状态
- 每轮 UI 实现后必须配合 QA / Codex 截图自检，根据截图中发现的风格偏差继续迭代

**典型任务示例**:
```
实现首页仪表盘组件
  引用: agents/02_ui_design.md + design_imgs/主页.png
  依赖: API GET /api/v1/progress/:userId
  验收: 1440x900 截图与 design_imgs/主页.png 在整体风格、卡片质感、配色、信息密度和导航表达上保持一致
```

---

### 2.2 后端 Agent

**职责范围**:
- FastAPI 路由与业务逻辑
- SQLAlchemy 数据模型与关系
- Alembic 数据库迁移
- API 认证与安全
- 数据校验 (Pydantic)
- 性能优化与缓存

**关键约束**:
- 所有 API 必须带有 Pydantic 请求/响应模型
- 数据库操作必须使用 ORM (禁止裸 SQL)
- 敏感操作记录审计日志
- API 响应统一格式 { code, message, data, meta }

**典型任务示例**:
```
实现学习记录 API
  引用: agents/04_architecture.md (API 契约)
  依赖: 用户模型 + 内容模型已创建
  验收: POST /api/v1/learning/answer 正确记录答题结果
```

---

### 2.3 AI Agent

**职责范围**:
- OpenAI API 集成与封装
- Prompt 模板设计与管理
- 年龄分级 + 难度适配 Prompt 策略
- 流式输出实现 (SSE)
- Token 用量优化与限流
- 回退策略 (API 失败时的降级方案)
- AI 动态出题 Prompt：题目、答案、解析、质量检查
- 小模型 CourseIntentAgent：课程选择理解和 query/参数扩写

**关键约束**:
- 所有 Prompt 模板必须版本化管理
- AI 回复必须经过安全过滤 (内容安全策略)
- 流式输出中断后能恢复
- Token 用量有监控和预警
- v0.1 不实现联网搜索，不调用搜索 API，不爬取网页
- AI Agent 不直接写数据库，所有持久化必须通过 Harness 工具或 Service

**典型任务示例**:
```
设计并实现数学分数加法出题 Prompt 模板
  引用: agents/01_feature_design.md (AI 动态出题)
  依赖: CourseIntentAgent 参数结构已确定
  验收: 同一主题可按年龄、难度、题型生成结构化题目、答案和解析
```

---

### 2.4 Harness Agent

**职责范围**:
- 设计和实现 AI Harness 编排层
- 编排 CourseIntentAgent、QuestionPlannerAgent、QuestionMemoryAgent、QuestionGeneratorAgent、QualityCheckAgent
- **内嵌 FeedbackAggregator 子组件**：汇聚偏差信号、计算 PID 三分量、生成控制信号、维护状态观测器
- 编排 SafetyAuditAgent 和 QualityReviewAgent
- 管理 Tool Middleware：生成题目知识库检索、题目保存、工具调用日志、质量检查日志
- 定义每一步输入/输出 schema
- 处理 AI 步骤失败、重试、降级和审计

**关键约束**:
- Harness 只负责编排和审计，不直接承担业务判题、学习进度或 UI 渲染职责
- 每个 Agent 必须单一职责，禁止把规划、生成、保存、质量检查写成一个不可拆的大 Prompt
- 所有工具调用必须记录 tool_name、input、output_summary、latency_ms、status、error
- v0.1 的生成题目知识库是"历史生成题 + 用户答题记录 + 题目标签 + 题目指纹"的长期沉淀，不是预置教材库或外部资料库
- 联网搜索是 v0.2 可选能力，Harness 中可预留 SearchTool 接口，但不得在 v0.1 调用

**FeedbackAggregator 子组件设计**:

FeedbackAggregator 是 Harness 内嵌的逻辑组件（非独立 Agent，无 LLM 推理能力），负责：

1. **偏差信号汇聚**：接收来自 Layer5（QualityCheckAgent）、Layer6（SafetyAuditAgent、QualityReviewAgent）的所有偏差信号
2. **PID 三分量计算**：
   - **P（比例）**：当前批次的质量通过率偏差 → 即时纠正力度。偏差越大，纠正力度越大
   - **I（积分）**：过去 N 次生成的累计质量偏差方向 → 系统性修正触发。长期小偏差累积后触发大调整
   - **D（微分）**：质量变化斜率 → 趋势干预策略。趋势恶化则紧急干预，趋势向好则减少干预
3. **控制信号生成**：将 PID 计算结果转换为可注入 Layer2/3/4 的 ControlSignal
4. **状态观测器维护**：每个循环中更新质量基线、用户能力估计、知识覆盖度、重复风险、系统健康度

**ControlSignal 输出格式**（注入 Layer2/3/4）:
```json
{
  "pid": {
    "p_error": "当前批次通过率偏差值",
    "i_drift": "累计偏差方向 (improving/stable/declining)",
    "d_slope": "质量变化斜率 (positive/negative/zero)"
  },
  "adjustments": {
    "difficulty_delta": "难度调整建议 (-1/0/+1)",
    "count_delta": "题目数量调整建议",
    "topic_scope": "知识点覆盖范围建议"
  },
  "state_estimate": {
    "quality_baseline": "最近50题平均质量分",
    "ability": "用户能力估计",
    "coverage": "知识点覆盖度",
    "duplicate_risk": "题目重复风险"
  }
}
```

**典型任务示例**:
```
实现 QuestionGenerationHarness
  引用: agents/04_architecture.md (AI 动态出题流程)
  依赖: QuestionGenerationService、QuestionMemoryService
  验收: generate 请求完整经过 intent -> plan -> memory -> generate -> quality -> safety_audit -> save，并产生审计日志
  验收: FeedbackAggregator 在每个循环后输出 ControlSignal，偏差信号可追踪
```

---

### 2.5 Design Agent

**职责范围**:
- 视觉设计规范维护
- 组件库扩展设计
- 动效设计
- 可访问性审查
- 设计稿输出 (Figma / SVG mockup)

**关键约束**:
- 遵循 agents/02_ui_design.md 的设计规范
- 所有设计必须考虑 4 个年龄分级
- 图标统一使用 lucide-react
- 符合 WCAG 2.1 AA 标准
- `design_imgs/*.png` 是风格事实源，Design Agent 不得改写整体风格方向
- 若发现文档描述与样例图风格冲突，以样例图风格为准，并更新文档说明冲突处理

**典型任务示例**:
```
设计成就徽章样式
  引用: agents/01_feature_design.md (激励体系)
  依赖: 无
  验收: 提供 6 个徽章的 SVG 设计
```

---

### 2.6 QA Agent

**职责范围**:
- 编写和执行测试用例
- E2E 测试 (Playwright)
- 性能测试 (Lighthouse)
- Bug 报告与追踪
- 验收标准检查
- **闭环反馈验证**：验证 ControlSignal 从 FeedbackAggregator 正确注入到前序 Agent

**关键约束**:
- 每个 PR 必须附带对应测试
- 核心逻辑单元测试覆盖率 >= 85%
- E2E 测试覆盖 3 条核心用户旅程 + 1 条闭环反馈旅程
- 所有 Bug 按严重级别分类
- UI 验收必须包含 Codex 自主生成的 `design_imgs` 风格对照截图、自检日志和迭代记录，缺少证据不得通过
- 若页面整体风格、色彩、间距、卡片质感、信息密度明显偏离样例图，按 P1 阻断问题处理
- QA Agent 必须要求 Codex 读取截图内容进行自我检查，记录发现的问题、修复动作和复查结论
- AI 出题验收必须覆盖题目结构、答案正确性、适龄性、难度匹配、重复度、审计日志
- QA Agent 必须验证 v0.1 不发生联网搜索调用
- QA Agent 必须验证安全审计否决的题目不进入知识库

**典型任务示例**:
```
编写 AI 出题核心流程 E2E 测试
  引用: agents/07_acceptance_criteria.md
  依赖: Phase 4 完成
  验收: 课程选择->生成题目->答题->错题变式->历史查询全流程通过
```

---

### 2.7 安全审计Agent (SafetyAuditAgent) [新增]

**职责范围**:
- 对所有 AI 生成内容进行实时安全四维审查
- 独立于生成流水线，具有一票否决权
- 审查不通过的题目不进入生成题目知识库
- 否决原因反馈给 ErrorLogger 和 FeedbackAggregator

**层级位置**: Layer 6（深审层），与 QualityCheckAgent 串联但独立运行

**四维审查体系**:

| 维度 | 审查内容 | 阈值 |
|------|---------|------|
| 内容适龄性 | 是否包含超出目标年龄段理解能力的内容；是否含有暴力、恐怖、歧视、认知超纲内容；示例场景是否积极健康 | ≥ 6 分（满分10），低于则否决 |
| 信息准确性 | 知识点表述是否准确（无科学错误）；数学计算是否正确；历史事实是否准确；概念定义是否符合教材标准 | ≥ 6 分 |
| 公平性与包容性 | 是否存在性别、种族、地域歧视；是否包含刻板印象；题目场景是否对所有用户群体友好；是否可能引发不适或争议 | ≥ 6 分 |
| 隐私安全 | 是否包含真实的个人信息（姓名、地址、电话）；是否可能诱导用户泄露个人信息；是否包含可被逆向推断的身份信息 | ≥ 6 分 |

**关键约束**:
- 任一维度低于 6 分，整道题目一票否决
- 否决的题目必须记录否决原因到 ErrorLog（错误类型: SAFE_AUDIT）
- 否决原因通过 FeedbackAggregator 回流到 QuestionGeneratorAgent，作为下次生成的避免项
- SafetyAuditAgent 不得修改被审查的题目，只做 PASS/REJECT 判定
- 安全审查在 QualityCheckAgent 之后执行（快检通过后再做安全深审）

**输出 Schema**（SafetyAuditResult）:
```json
{
  "question_id": "UUID",
  "verdict": "PASS | REJECT",
  "scores": {
    "age_appropriate": 8,
    "accuracy": 9,
    "fairness": 10,
    "privacy": 10
  },
  "issues": [
    {"dimension": "age_appropriate", "detail": "描述涉及战争场景，对6-9岁用户不合适", "severity": "blocking"}
  ],
  "blocking_issue": null | "具体否决原因"
}
```

**典型任务示例**:
```
对一批生成的数学题执行安全审查
  引用: 本文件 §2.7
  依赖: QuestionGeneratorAgent 已生成题目
  验收: 每道题返回四维评分，不合格题目被标记为 REJECT 且不进入知识库
```

---

### 2.8 质量审查Agent (QualityReviewAgent) [新增]

**职责范围**:
- 独立于 QualityCheckAgent 的深度质量评估
- 抽样审查 + 趋势分析 + 系统性反馈
- 为 FeedbackAggregator 提供质量偏差信号
- 识别系统性质量问题并预警

**层级位置**: Layer 6（深审层），与 SafetyAuditAgent 并行，与 QualityCheckAgent 互补

**与 QualityCheckAgent 的区别**:

| 维度 | QualityCheckAgent (QC) | QualityReviewAgent (QR) |
|------|----------------------|------------------------|
| 位置 | Layer 5（流水线内部） | Layer 6（独立于流水线） |
| 检查范围 | 每道题必检 | 抽样 + 边缘全检 |
| 检查深度 | 快速检查（4项） | 深度评估（6项） |
| 时间要求 | 同步阻塞生成流程 | 可异步执行 |
| 趋势分析 | 不做 | 做趋势分析 |
| 反馈输出 | 偏差信号（单题级别） | 趋势报告 + 推荐调整参数 |
| 权威文件 | 本文件 §2.4 (Harness Agent) | 本文件 §2.8 |

**抽样策略**:
- 每批次随机抽取 20% 的题目进行深度审查
- QualityCheckAgent 打分在 60-70 分边缘区间的题目 100% 审查
- 过去 7 天质量分数持续下降时，抽样率提升到 50%

**六维评估体系**:

| 维度 | 评估内容 |
|------|---------|
| 知识点准确性 | 题目所涉知识是否正确 |
| 难度匹配度 | 实际难度是否与标注难度一致 |
| 选项区分度 | 错误选项是否有合理的干扰性 |
| 解析质量 | 解析是否清晰、准确、有教育价值 |
| 语言规范性 | 语言是否流畅、无歧义、符合中文表达习惯 |
| 适龄性复核 | 对 SafetyAuditAgent 的适龄性判断进行二次复核 |

**关键约束**:
- QualityReviewAgent 不得直接修改题目，只做评估和建议
- 趋势报告必须包含推荐调整参数（difficulty_delta, quality_threshold_adjustment）
- QR 的评估结果用于更新 FeedbackAggregator 的 I（积分）分量
- QR 不得替代 QC，QC 仍是每道题的必检环节

**输出 Schema**（QualityTrendReport）:
```json
{
  "batch_id": "UUID",
  "trend": "improving | stable | declining",
  "system_quality_score": 75,
  "top_issues": [
    {"type": "difficulty_mismatch", "frequency": "23%", "suggestion": "增加难度校准Prompt权重"}
  ],
  "agent_feedback": {
    "QuestionGeneratorAgent": {"strength": "数学题质量稳定", "weakness": "语文题选项区分度不足"},
    "QualityCheckAgent": {"missed_issues": "部分适龄性问题未被快检捕获"}
  },
  "recommended_adjustments": {
    "difficulty_delta": -0.3,
    "quality_threshold_adjustment": 5
  }
}
```

**典型任务示例**:
```
对最近10个批次进行质量趋势分析
  引用: 本文件 §2.8
  依赖: QualityCheckAgent 已产生足够的质量检查数据
  验收: 输出趋势报告，包含质量漂移方向、Top 问题类型和推荐调整参数
```

---

### 2.9 总结Agent (SummaryAgent) [新增]

**职责范围**:
- 在每个学习会话结束时，从会话数据中提炼可复用的知识和技能
- 实现 Hermes 风格的五环自进化机制
- 维护用户模型和 Skill 库
- 触发系统自我更新

**层级位置**: Layer 8（学习进化层），在出题闭环之外独立运行

**Hermes 五环机制**:

| 环 | 名称 | 触发时机 | 核心动作 | 输出 |
|----|------|---------|---------|------|
| 1 | 记忆策划 | 每轮会话结束 | 从会话数据中筛选≤5条高价值信息，设置TTL和置信度 | MemoryItem → SessionMemory |
| 2 | Skill创建 | 成功模式识别 | 将高质量出题模式蒸馏为可复用Skill文件 | SkillFile → Skill存储 |
| 3 | Skill自改进 | Skill效果下降 | 更新Skill本身的步骤、偏好、陷阱 | 更新后的SkillFile |
| 4 | 跨会话召回 | 新会话开始 | 按学科+主题+难度FTS检索最相关3-5条记忆 | 记忆上下文注入Agent |
| 5 | 用户建模 | 每次会话结束 | 更新能力估计、行为模式、偏好、置信度 | UserProfileUpdate → User表 |

**关键约束**:
- 每次提炼的记忆不超过 5 条，优先存储高置信度、高价值的信息
- Skill 文件大小不超过 15KB，增长幅度不超过原版的 20%
- 记忆设置 TTL（默认 90 天，高价值记忆 180 天），过期自动淘汰
- 反馈一致性 < 70% 时不更新策略（防止噪声污染）
- Skill 创建前必须验证：触发条件明确可匹配、执行步骤足够具体、包含用户偏好和已知陷阱
- v0.1 仅实现 Skill 内容优化（Hermes Phase 1），不实现 Prompt 模板自修改

**输出 Schema**:

**MemoryItem**（写入 SessionMemory 表）:
```json
{
  "type": "error_pattern | preference | quality_insight | behavior_pattern",
  "content": "结构化记忆内容",
  "confidence": 0.85,
  "ttl_days": 90,
  "related_topic": "数学/分数加法"
}
```

**SkillFile**（写入 Skill 存储）:
```markdown
---
name: math-fraction-addition-age10-medium
trigger: subject=数学 AND topic=分数加法 AND age_group=10-12 AND difficulty=medium
created: 2026-07-08
version: 1
success_count: 15
---

## 执行步骤
1. 题型分布：选择题40% + 填空题30% + 应用题30%
2. 难度递进：先3道基础运算，再2道应用场景
3. 语言风格：每题不超过40字，选项不超过15字

## 用户偏好记录
- 该年龄段用户对"分苹果/分披萨"场景的接受度最高
- 抽象符号题的正确率比场景题低15%

## 常见陷阱
- 分数未化简
- 分母为0
- 运算顺序错误
```

**UserProfileUpdate**（写入 User 表 behavior_profile 字段）:
```json
{
  "ability_updates": {"数学/分数": {"level": "中级", "accuracy": 0.72, "trend": "improving"}},
  "behavior_patterns": {"avg_session_minutes": 12, "preferred_types": ["选择题", "填空题"], "active_hours": [19, 20, 21]},
  "preference_conflicts": [{"claimed": "喜欢挑战题", "actual": "挑战题完成率30%", "resolution": "以实际行为为准"}],
  "confidence_updates": {"数学/分数": 0.8, "语文/阅读": 0.5}
}
```

**典型任务示例**:
```
会话结束后执行总结
  引用: 本文件 §2.9
  依赖: 用户完成一轮练习，答题记录和质量检查数据可用
  验收: 产出≤5条MemoryItem，可能产出SkillFile，更新UserProfile
```

---

### 2.10 ErrorLogger Middleware [新增]

**职责范围**:
- 作为 AI Harness 中间件，实时捕获所有 Agent 执行过程中的错误和异常
- 对错误进行分类、结构化并路由到对应的处理 Agent
- 记录错误日志到 ErrorLog 表，供后续分析和学习

**层级位置**: 贯穿所有 Layer，作为 Harness 的基础设施组件

**四类错误分类体系**:

| 错误类型 | 编码 | 说明 | 路由目标 | 紧急度 |
|---------|------|------|---------|--------|
| SAFE_AUDIT | E001-E099 | 内容安全违规（不适龄内容、敏感信息、偏见歧视） | SafetyAuditAgent | P0（立即阻断） |
| QUALITY_FAIL | E100-E199 | 质量检查失败（答案错误、难度不匹配、重复题） | QualityReviewAgent | P1（本轮内处理） |
| PERF_DEGRADE | E200-E299 | 性能退化（响应超时、Token消耗异常） | Harness | P2（记录并监控） |
| LOGIC_ERROR | E300-E399 | 逻辑错误（参数不一致、流程异常、状态冲突） | Harness + SummaryAgent | P1（本轮内处理） |

**关键约束**:
- ErrorLogger 必须捕获所有 Agent 步骤的异常，包括 LLM 调用失败、Prompt 格式错误、工具调用超时
- 每条错误日志必须包含完整的上下文信息（Agent名称、步骤、输入摘要、错误详情）
- SAFE_AUDIT 类型错误必须立即阻断当前题目进入知识库
- ErrorLogger 不得自行修复错误，只负责分类、记录和路由
- 错误日志作为 SummaryAgent 的输入之一，用于识别系统性问题和触发进化

**ErrorEvent 输出 Schema**（写入 ErrorLog 表 + 路由到对应 Agent）:
```json
{
  "timestamp": "2026-07-08T10:30:00Z",
  "agent_name": "QuestionGeneratorAgent",
  "step": "generate",
  "error_type": "SAFE_AUDIT",
  "error_code": "E001",
  "severity": "P0",
  "raw_error": "生成的题目包含暴力场景描述",
  "context": "subject=数学, topic=分数, age_group=6-9, difficulty=easy",
  "affected_output": "question_id=xxx",
  "auto_fix_attempted": false
}
```

---

### 2.11 Agent 间接口契约表 [新增]

> 本表定义所有 Agent 间的数据接口，是系统对接的唯一权威参考。
> 生产者负责生成符合 Schema 的数据，消费者负责解析并处理。
> 详细的 Schema 字段定义见 `agents/09_data_model.md`。

| 接口名称 | 生产者 (Layer) | 消费者 (Layer) | 数据 Schema | 触发时机 | 错误协议 |
|---------|---------------|---------------|------------|---------|---------|
| IntentParams | CourseIntentAgent (L1) | QuestionPlannerAgent (L2) | `{age_group, subject, course_topic, difficulty, question_types, question_count, learning_goal}` | 每次生成请求 | 参数不完整时返回 clarification_required |
| PlanResult | QuestionPlannerAgent (L2) | QuestionGeneratorAgent (L4) | `{plan_id, question_plan: [{type, count, difficulty, weight}], adjusted_params, deviation_declaration}` | 收到 IntentParams + ControlSignal 后 | 无 |
| MemoryContext | QuestionMemoryAgent (L3) | QuestionGeneratorAgent (L4) | `{avoid_list: [{id, similarity_hash}], recent_feedback: [], user_preferences: {}, skill_hints: []}` | 收到 PlanResult 后 | 无 |
| GeneratedQuestions | QuestionGeneratorAgent (L4) | QualityCheckAgent (L5) | `{questions: [{id, body, options, answer, explanation, tags}], generation_meta, deviation_declaration}` | 收到 MemoryContext + ControlSignal 后 | 生成失败时通过 ErrorLogger 报告 |
| QuickCheckResult | QualityCheckAgent (L5) | FeedbackAggregator (L7) | `{question_id, passed, score, issues[], deviation: {type, value}}` | 每道题检查后 | 无 |
| SafetyAuditResult | SafetyAuditAgent (L6) | FeedbackAggregator (L7) + ErrorLogger | `{verdict, scores: {age_appropriate, accuracy, fairness, privacy}, issues[], blocking_issue}` | 每道题 QC 通过后 | REJECT 时写入 ErrorLog (SAFE_AUDIT) |
| QualityTrendReport | QualityReviewAgent (L6) | FeedbackAggregator (L7) | `{trend, system_score, top_issues[], agent_feedback{}, recommended_adjustments}` | 抽样审查后 | 无 |
| **ControlSignal** | **FeedbackAggregator (L7)** | **QuestionPlannerAgent (L2) + QuestionMemoryAgent (L3) + QuestionGeneratorAgent (L4)** | `{pid: {p_error, i_drift, d_slope}, adjustments: {difficulty_delta, count_delta, topic_scope}, state_estimate: {quality_baseline, ability, coverage, duplicate_risk}}` | **每次偏差信号汇聚后** | **PID计算异常时通过 ErrorLogger 报告 (LOGIC_ERROR)** |
| MemoryItem | SummaryAgent (L8) | SessionMemory 表 (DB) | `{type, content, confidence, ttl_days, related_topic}` | 会话结束时 | 写入失败时通过 ErrorLogger 报告 |
| SkillFile | SummaryAgent (L8) | Skill 存储 | `{name, trigger, version, steps, preferences, pitfalls, success_count}` | 模式提炼成功时 | 创建失败时通过 ErrorLogger 报告 |
| UserProfileUpdate | SummaryAgent (L8) | User 表 (DB) | `{ability_updates, behavior_patterns, preference_conflicts, confidence_updates}` | 会话结束时 | 更新失败时通过 ErrorLogger 报告 |
| ErrorEvent | ErrorLogger (中间件) | ErrorLog 表 (DB) + 路由 Agent | `{timestamp, agent_name, step, error_type, error_code, severity, raw_error, context, affected_output}` | 任何 Agent 执行出错时 | 无（自身是错误处理的起点） |

---

## 3. 协作协议

### 3.1 任务分配规则

1. 主 Agent 根据任务类型分配给对应的子 Agent
2. 跨领域任务分配给主 Agent，由其拆解后分派
3. 每个子 Agent 一次只处理一个任务
4. 任务必须有明确的验收标准

### 3.2 信息传递格式

```
任务卡片格式:
  任务ID: <FE|BE|AI|DS|QA|SA|QR|SUM>-<序号>
  描述: <一句话说明>
  引用文件: <关联的 prompt 文件>
  依赖: <前置任务 IDs>
  产出: <预期交付物>
  验收: <验收标准>
  接口契约: <引用 §2.11 的接口名称>
```

### 3.3 冲突解决

- API 契约冲突：后端 Agent 有最终决定权
- UI 实现分歧：Design Agent 提供参考，前端 Agent 决定可行性
- 数据模型变更：必须通知所有相关 Agent
- 优先级冲突：主 Agent 裁决
- Agent 接口契约冲突：以本文件 §2.11 为唯一权威

### 3.4 质量门禁

每个子 Agent 提交产出前必须自检：
- [ ] 代码符合项目规范 (lint pass)
- [ ] 新增代码有对应测试
- [ ] API 变更已更新文档
- [ ] 没有引入新的依赖未经审核
- [ ] 无安全漏洞 (输入校验、权限检查)
- [ ] **新增：Agent 输出符合 §2.11 定义的接口 Schema**
- [ ] **新增：偏差信号已通过 FeedbackAggregator 正确路由**
- [ ] **新增：错误事件已通过 ErrorLogger 正确分类和记录**

### 3.5 闭环反馈协议 [新增]

**反馈信号的生命周期**：

```
1. Agent 产出结果 → 2. 检查Agent评估 → 3. 偏差信号生成
   → 4. FeedbackAggregator 汇聚 → 5. PID计算 → 6. ControlSignal 生成
   → 7. 注入前序Agent的下一次循环 → 8. Agent调整行为
   → 9. 新一轮产出 → 10. 回到步骤2
```

**反馈注入时机**：
- **即时注入**：SafetyAuditAgent 的 REJECT 结果在当前循环内立即生效（阻断该题目）
- **下次循环注入**：FeedbackAggregator 的 ControlSignal 在下一次生成请求时注入到 Layer2/3/4
- **趋势注入**：QualityReviewAgent 的趋势分析结果影响后续 N 次生成的 PID I 分量

**偏差声明规则**：
- QuestionPlannerAgent：如果调整后的参数偏离 CourseIntentAgent 的原始设定值，必须在 PlanResult 中声明 deviation_declaration
- QuestionGeneratorAgent：如果生成题目的实际难度与规划难度不一致，必须在 GeneratedQuestions 中声明 deviation_declaration
- 声明格式：`{"type": "difficulty_mismatch", "expected": "medium", "actual": "hard", "reason": "..."}`

---

## 4. 统一闭环控制接口模板 [新增]

> 每个 Agent 的提示词中将包含由 Harness 自动注入的标准化闭环段落。
> Agent 不应修改此段内容。

```markdown
## [闭环控制接口] — Harness 自动注入，Agent 不应修改

### 我的闭环角色
- 层级位置：{layer_name}
- 上游依赖：{upstream_agents}
- 下游服务：{downstream_agents}
- 输入信号：{input_signals}（引用 §2.11 的接口名称）
- 输出信号：{output_signals}（引用 §2.11 的接口名称）

### 当前循环状态
- 循环编号：{loop_iteration_id}
- 本轮设定值（setpoint）：{setpoint_from_intent_params}
- 上次偏差（last_error）：{last_error_from_control_signal}
- PID 控制信号：{current_control_signal}

### 闭环协作规则
1. 必须生成符合 §2.11 定义的结构化输出，供下游 Agent 和 FeedbackAggregator 使用
2. 如果输出偏离设定值，必须在输出中显式声明 deviation_declaration
3. 必须检查上游传递的 ControlSignal 和反馈信号，并据此调整行为
4. 检测到异常时通过 ErrorLogger 错误通道上报，不得静默忽略
5. 不得自行计算 PID 参数或生成控制信号，这是 FeedbackAggregator 的唯一职责
```
