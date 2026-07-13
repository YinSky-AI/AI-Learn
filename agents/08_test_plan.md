# 测试计划 (08)

> **文件标识**: agents/08_test_plan.md
> **关联文件**: 引用 00-02, 07；定义测试策略、分类、用例大纲和自动化方案。

---

## 1. 测试策略

### 1.1 测试金字塔

```
           /\
          /  \          E2E 测试 (Playwright)
         /    \         3 条核心用户旅程
        /------\
       /        \       集成测试 (pytest + Jest)
      /          \       API 层 + 组件交互
     /------------\
    /              \    单元测试 (pytest + Jest)
   /                \   Services / Hooks / Utils
  /------------------\
  /   手动探索测试    \   人工 QA 补充
 /____________________\
```

### 1.2 覆盖目标

| 层级 | 工具 | 目标覆盖率 | 运行频率 |
|------|------|-----------|---------|
| 单元测试 (后端) | pytest | >= 85% | 每次 commit |
| 单元测试 (前端) | Jest | >= 80% | 每次 commit |
| 集成测试 | pytest + pytest-asyncio | 核心 API 全覆盖 | 每次 commit |
| E2E 测试 | Playwright | 3 条核心旅程 | 每次 PR |
| 性能测试 | Lighthouse CI | 基线检查 | 每次 PR |

### 1.3 视觉回归测试基准

`design_imgs` 目录中的图片是 UI 视觉回归测试的基准输入：

| 基准图 | 页面 / 状态 | 测试方式 |
|--------|-------------|----------|
| `design_imgs/主页.png` | 首页 Dashboard | Playwright 打开首页，设置视口 `1440x900` 截图，由 Codex 读取截图并检查风格一致性 |
| `design_imgs/附页1.png` | 知识探索页 | 设置筛选状态，截图，由 Codex 检查筛选页风格是否符合样例 |
| `design_imgs/附页2.png` | Learning + AI Assistant | 打开分数学习页并展开 AI 面板，截图，由 Codex 检查学习页风格是否符合样例 |
| `design_imgs/附页3.png` | Profile | 打开个人中心，截图，由 Codex 检查个人中心风格是否符合样例 |
| `design_imgs/ui组件设计参考.png` | AI 浮窗、难度弹窗、学科多选 Popover | 分别触发组件状态，截图，由 Codex 检查浮层风格是否符合样例 |

**视觉测试口径**:
- 所有截图固定使用 `1440x900` 视口。
- 测试数据可以接近样例图的信息密度，但最终可见文案必须中文化，例如用户“小明”、五年级、课程“分数加法基础”、探索页“24 个结果”、连胜“5 天”；不得照搬样例图英文文案。
- 若使用动态数据，必须通过 mock / fixture 固定，避免截图抖动。
- 视觉差异评估重点是整体样式风格、色彩、间距、圆角、卡片质感、信息密度、导航表达、组件状态；不要求像素级复刻。
- 布局结构评估是硬性要求：左侧导航、顶部栏、主内容区、卡片区块、课程网格、学习页右侧 AI 面板、个人中心左右列、浮层组件位置关系必须保持样例图结构。
- 中文文案评估是硬性要求：导航、标题、按钮、课程卡、弹窗、题目、解析和 AI Assistant 可见内容必须为自然简体中文。
- Codex 必须保存截图、保存日志、读取截图内容、自我检查并迭代；只生成截图但不做自检不算通过。

---

## 2. 后端测试

### 2.1 测试结构

```
backend/tests/
  conftest.py             # 全局 fixtures
  test_services/
    test_user_service.py
    test_learning_service.py
    test_achievement_service.py
  test_api/
    test_auth.py
    test_content.py
    test_learning.py
    test_ai.py
    test_progress.py
  test_ai/
    test_prompts.py       # Prompt 模板测试
    test_assistant.py     # AI Service 测试 (mock)
    test_question_harness.py
    test_question_generation.py
    test_question_memory.py
  fixtures/
    sample_content.py     # 测试用种子数据
    mock_ai.py            # AI API mock
    mock_question_generation.py
```

### 2.2 单元测试核心用例

#### UserService

| 用例 | 描述 | 预期 |
|------|------|------|
| test_create_user_success | 创建用户成功 | 返回用户对象，密码已 hash |
| test_create_user_duplicate | 重复注册 | 抛出 DuplicateError |
| test_authenticate_valid | 有效密码登录 | 返回 JWT Token |
| test_authenticate_invalid | 无效密码 | 返回 None |
| test_get_user_by_age | 按年龄分级查询用户 | 返回正确年龄段用户 |

#### LearningService

| 用例 | 描述 | 预期 |
|------|------|------|
| test_start_session | 开始学习会话 | 创建 Session 记录 |
| test_submit_answer_correct | 提交正确答案 | 返回 correct=true, 积分增加 |
| test_submit_answer_wrong | 提交错误答案 | 返回 correct=false, 展示正确答案 |
| test_consecutive_wrong_trigger | 连续 3 题错误 | 触发降级推荐 flag |
| test_consecutive_correct_trigger | 连续 5 题正确 | 触发升级推荐 flag |
| test_difficulty_level_content | 不同难度返回不同内容 | 内容 ID 不同 |
| test_progress_tracking | 进度追踪 | 完成率正确计算 |

#### AIService

| 用例 | 描述 | 预期 |
|------|------|------|
| test_explain_endpoint | 知识点讲解 | 返回讲解文本 |
| test_error_analysis | 错题解析 | 包含错因分析 |
| test_prompt_age_adaptation | Prompt 按年龄调整 | 6 岁 vs 16 岁 Prompt 不同 |
| test_stream_output | 流式输出 | 返回 AsyncGenerator |
| test_rate_limiting | 速率限制 | 超限返回 429 |

#### QuestionGenerationHarness

| 用例 | 描述 | 预期 |
|------|------|------|
| test_course_intent_complete | 输入完整课程选择 | 返回结构化出题参数 |
| test_course_intent_missing_required | 缺少不可推断参数 | 返回 clarification_required |
| test_question_plan_distribution | 生成 10 道中级题计划 | 包含基础/应用/挑战比例 |
| test_question_memory_dedup | 历史题库已有相似题 | 新生成计划携带 avoid 列表 |
| test_question_memory_accumulates | 连续生成并答题 | 生成题目知识库持续沉淀题目、标签、答题行为和题目指纹 |
| test_question_generation_schema | mock AI 生成题目 | 每题包含题干/答案/解析/标签 |
| test_question_generation_chinese_output | mock AI 生成题目 | 题干、答案、解析和提示均为简体中文 |
| test_quality_check_invalid_answer | mock 错误答案 | 质量检查 FAIL |
| test_quality_check_duplicate | mock 重复题 | 重复度检查 FAIL |
| test_harness_run_audit_log | 完整运行 Harness | 记录 intent/plan/memory/generate/quality/save |
| test_no_web_search_v01 | 完整出题流程 | 工具日志中不出现 search/web/crawl 工具 |

#### SafetyAuditAgent

| 用例 | 描述 | 预期 |
|------|------|------|
| test_safety_pass_all_dimensions | 四维均≥6分的题目 | 返回 PASS |
| test_safety_reject_age_inappropriate | 含暴力内容的6-9岁题目 | 返回 REJECT，blocking_issue 非空 |
| test_safety_reject_inaccurate | 含数学计算错误的题目 | 返回 REJECT |
| test_safety_reject_privacy | 含真实个人信息的题目 | 返回 REJECT |
| test_safety_reject_fairness | 含性别歧视的题目 | 返回 REJECT |

#### QualityReviewAgent

| 用例 | 描述 | 预期 |
|------|------|------|
| test_trend_analysis_improving | 质量上升趋势 | trend=improving |
| test_trend_analysis_declining | 质量下降趋势 | trend=declining, recommended_adjustments 非空 |
| test_sampling_edge_cases | 边缘分数题目100%审查 | 审查覆盖所有边缘题 |
| test_sampling_rate_increase | 质量下降时抽样率提升 | 抽样率≥50% |

#### SummaryAgent

| 用例 | 描述 | 预期 |
|------|------|------|
| test_memory_extraction | 会话结束后提炼记忆 | 产出≤5条 MemoryItem |
| test_skill_creation | 成功模式触发Skill创建 | 产出 SkillFile |
| test_skill_self_improvement | Skill效果下降触发更新 | SkillFile version+1 |
| test_user_profile_update | 会话结束后更新用户模型 | UserProfileUpdate 包含 ability_updates |
| test_memory_ttl | 过期记忆被清理 | is_expired=true |

#### FeedbackAggregator

| 用例 | 描述 | 预期 |
|------|------|------|
| test_pid_p_component | 当前批次偏差→即时纠正 | p_error 非零，adjustments 非空 |
| test_pid_i_component | 累计偏差→系统性修正 | i_drift=declining 时调整力度大 |
| test_pid_d_component | 趋势恶化→紧急干预 | d_slope=negative 时 intervention_strategy 触发 |
| test_control_signal_injection | ControlSignal 正确注入前序Agent | 前序Agent下次执行时参数变化 |

#### ErrorLogger

| 用例 | 描述 | 预期 |
|------|------|------|
| test_safe_audit_routing | SAFE_AUDIT错误路由到SafetyAuditAgent | routing_target=SafetyAuditAgent |
| test_quality_fail_routing | QUALITY_FAIL错误路由到QualityReviewAgent | routing_target=QualityReviewAgent |
| test_perf_degrade_routing | PERF_DEGRADE错误路由到Harness | routing_target=Harness |
| test_logic_error_routing | LOGIC_ERROR错误路由到Harness+SummaryAgent | routing_target 包含两个Agent |
| test_error_persistence | 所有错误持久化到ErrorLog | ErrorLog 表中有对应记录 |

### 2.3 API 集成测试

| 用例 | 描述 |
|------|------|
| test_register_login_flow | 注册 -> 登录 -> 获取 Token |
| test_content_filter_by_age | 按年龄筛选内容 API |
| test_content_filter_multi | 多维度联合筛选 |
| test_learning_full_flow | 开始 -> 答题 x3 -> 完成会话 |
| test_ai_explain_rate_limit | AI 接口限流测试 |
| test_question_generate_flow | 课程选择 -> 生成题目批次 -> 查询批次 |
| test_question_variant_flow | 答错题 -> 生成变式题 |
| test_question_history | 查询用户历史生成题 |
| test_skills_list | 查询 Skill 列表 API |
| test_user_profile | 查询用户行为模型 API |
| test_evolution_log | 查询进化记录 API |
| test_error_log_filter | 按类型/严重度筛选错误日志 API |

---

## 3. 前端测试

### 3.1 测试结构

```
frontend/tests/
  unit/
    hooks/
      test_useContentFilter.ts
      test_useLearningProgress.ts
    utils/
      test_ageClassifier.ts
      test_difficultyUtils.ts
    stores/
      test_learningStore.ts
      test_userStore.ts
  integration/
    components/
      test_DifficultySelector.tsx
      test_ContentCard.tsx
      test_AIAssistant.tsx
    pages/
      test_HomePage.tsx
      test_LearningPage.tsx
  e2e/
    test_core_learning_flow.spec.ts
    test_filter_navigation.spec.ts
    test_age_switch_flow.spec.ts
```

### 3.2 单元测试核心用例

| 用例 | 描述 | 预期 |
|------|------|------|
| ageClassifier 计算年龄分级 | 输入出生日期返回正确分级 | 6-9 / 10-12 / 13-15 / 16-18 |
| ageClassifier 边界值 | 恰好 10 岁生日 -> 15 岁生日 | 返回正确分级 |
| difficultyUtils 难度匹配 | 输入难度编码返回显示名 | EASY -> "初级" |
| learningStore 答题状态 | 提交答案后状态更新 | correctCount 累加 |
| userStore 分级切换 | 切换分级后主题状态更新 | theme 上下文变化 |

### 3.3 组件测试

| 用例 | 描述 |
|------|------|
| DifficultySelector 渲染三级选项 | 检查 DOM 渲染 |
| DifficultySelector 选中高亮 | 点击后对应项高亮 |
| ContentCard 渲染所有信息 | 标题/进度/难度/形式图标 |
| ContentCard 点击跳转 | 点击后路由到学习页 |
| AIAssistant 展开折叠 | 点击图标展开/关闭浮窗 |
| AIAssistant 流式展示 | mock 数据模拟打字机效果 |

### 3.4 视觉组件测试

| 用例 | 描述 | 基准 |
|------|------|------|
| HomePage visual baseline | 首页整体风格与样例图一致 | `design_imgs/主页.png` |
| ExplorePage visual baseline | 探索页筛选栏与课程卡风格一致 | `design_imgs/附页1.png` |
| LearningPage visual baseline | 学习页顶部、进度、AI 面板风格一致 | `design_imgs/附页2.png` |
| ProfilePage visual baseline | 个人中心卡片布局气质与样例图一致 | `design_imgs/附页3.png` |
| FloatingComponents visual baseline | AI 助手、难度选择、多选 Popover 风格一致 | `design_imgs/ui组件设计参考.png` |

---

## 4. E2E 测试

### 4.1 核心用户旅程 #1: 新用户完成学习

```
1. 访问首页 -> 看到注册/登录入口
2. 点击注册 -> 填写信息 (年龄: 10 岁) -> 提交
3. 登录 -> 进入首页仪表盘
4. 看到年龄适配的 UI (字号 18-24px，卡通风格)
5. 点击"知识探索" -> 筛选: 数学 + 互动问答
6. 看到筛选结果
7. 点击第一个内容卡片 -> 进入学习页
8. 阅读知识内容 -> 翻页
9. 进入问答: 选择答案 -> 提交
10. 看到正误判定和反馈动画
11. 点击"下一项"继续
12. 点击 AI 助手 -> 提问 -> 看到流式回复
13. 退出 -> 个人中心查看进度
```

### 4.2 核心用户旅程 #2: 难度自适应

```
1. 已有账号登录 -> 进入学习页 (中级)
2. 连续答错 3 题 -> 看到降级弹窗
3. 点击"切换难度" -> 降为初级
4. 内容刷新为初级
5. 连续答对 5 题 (快速) -> 看到升级推荐
6. 切换回中级
```

### 4.3 核心用户旅程 #3: 年龄分级切换

```
1. 登录 (16-18 岁) -> 看极简风格 UI
2. 进入知识探索 -> 看到所有维度筛选 -> 浏览内容
3. 个人中心 -> 调整年龄分级为 10-12
4. 返回首页 -> UI 变为活泼风格
5. 知识探索 -> 内容列表已变化
```

### 4.3.1 核心用户旅程 #3b: AI 动态出题

```
1. 登录测试账号“小明”（五年级）
2. 进入知识探索或学习入口
3. 选择: 数学 / 分数加法 / 中级 / 选择题+应用题 / 10 道
4. 点击生成练习
5. 等待生成完成，看到题目列表
6. 回答至少 3 道题，其中故意答错 1 道
7. 查看答案解析
8. 对错题点击"生成变式题"
9. 查看新题与原题同知识点但不重复
10. 打开历史记录，确认生成批次和题目已保存
11. 检查 Harness 日志中包含 intent、plan、memory、generate、quality、save
12. 检查工具调用日志中没有联网搜索工具
13. 检查生成题目知识库已保存题目、标签、质量检查和答题行为
```

### 4.5 核心用户旅程 #5: 闭环反馈验证

```
1. 登录测试账号
2. 选择: 数学 / 分数加法 / 中级 / 选择题 / 5 道
3. 触发生成练习
4. 检查 Harness 日志中包含完整的 intent->plan->memory->generate->quality->safety_audit->save 步骤
5. 故意构造一个质量偏差场景（如部分题目难度不匹配）
6. 验证 FeedbackAggregator 输出 ControlSignal
7. 再次生成同主题题目
8. 验证新生成题目的参数受到 ControlSignal 影响（难度调整）
9. 检查偏差信号追踪日志完整
```

### 4.6 核心用户旅程 #6: 自进化验证

```
1. 完成多次高质量出题会话（≥5次，成功率>80%）
2. 检查 SummaryAgent 产出 MemoryItem（≤5条）
3. 检查是否自动创建 SkillFile
4. 验证 Skill 包含触发条件、执行步骤、用户偏好和常见陷阱
5. 模拟 Skill 效果下降场景
6. 验证 Skill 触发自改进
7. 检查 EvolutionRecord 记录完整
8. 验证用户行为模型已更新
```

### 4.4 核心用户旅程 #4: Codex 自主视觉风格验收

```
1. 启动前端并注入固定 mock 数据
2. 设置视口为 1440x900
3. 访问首页 -> 截图保存为 test-evidence/screenshots/AC-VIS-01_home.png
4. 访问知识探索页 -> 设置筛选为 10-12 yrs + Math -> 截图保存为 AC-VIS-02_explore.png
5. 访问学习页 -> 展开 AI Assistant -> 截图保存为 AC-VIS-03_learning.png
6. 访问个人中心 -> 截图保存为 AC-VIS-04_profile.png
7. 依次触发 AI 浮窗、难度选择、学科多选 Popover -> 截图保存为 AC-VIS-05_*.png
8. Codex 读取每张截图内容，与 design_imgs 样式风格和布局结构对照
9. Codex 将自检结果写入 test-evidence/logs/AC-VIS_codex_visual_review.md
10. 若发现风格偏差，Codex 记录问题、修改实现、重新截图复查
11. 每轮迭代写入 test-evidence/review/AC-VIS_iteration.md
12. 直到 Codex 自检结论为 PASS，或明确记录阻塞原因和剩余差异
```

### 4.5 Codex 视觉自检日志格式

```md
# AC-VIS Codex Visual Review

## Run Info
- Date:
- Viewport: 1440x900
- App URL:
- Screenshot directory:

## Reference Style Summary
- Background:
- Card style:
- Primary color:
- Subject color blocks:
- Navigation style:
- Floating component style:
- Chinese copywriting:

## Reference Layout Structure
- Sidebar:
- Top bar:
- Main content region:
- Card grid:
- Learning page right AI panel:
- Profile two-column layout:
- Floating component placement:

## Screenshot Findings
| Screenshot | PASS/FAIL | Style Observations | Layout Observations | Required Iteration |
|------------|-----------|--------------------|---------------------|--------------------|
| AC-VIS-01_home.png |  |  |  |
| AC-VIS-02_explore.png |  |  |  |
| AC-VIS-03_learning.png |  |  |  |
| AC-VIS-04_profile.png |  |  |  |
| AC-VIS-05_components.png |  |  |  |

## Iteration Decisions
- Change 1:
- Change 2:
- Re-screenshot result:

## Final Verdict
- PASS / FAIL:
- Remaining risks:
```

---

## 5. 性能测试

| 场景 | 工具 | 目标 |
|------|------|------|
| 首页首屏加载 | Lighthouse | < 2s，评分 >= 85 |
| 学习页内容加载 | Lighthouse | < 1.5s |
| API 列表查询 (100 并发) | k6 | p95 < 500ms |
| AI 流式首 token | 自写脚本 | < 1.5s |
| 连续学习操作 (10 分钟) | Playwright + trace | 无内存泄漏 |

---

## 6. 测试数据管理

- 种子数据: PostgreSQL 初始化脚本，包含 10 个知识点 + 每个知识点 3 题 x 3 难度
- 测试账号: 预置 4 个不同年龄段账号 (age_6, age_10, age_13, age_16)
- AI Mock: 测试环境下所有 AI 调用返回预设响应 (fixtures/mock_ai.py)
- 数据库隔离: 测试使用独立测试数据库，每次运行前重置

---

## 7. 缺陷管理

| 严重级别 | 定义 | 响应时间 |
|---------|------|---------|
| S0-Critical | 核心功能不可用，数据丢失 | 立即修复 |
| S1-Major | 功能严重受限，无绕行方案 | 24h 内修复 |
| S2-Minor | 功能轻微受限，有绕行方案 | 下个迭代 |
| S3-Trivial | 样式/文案小问题 | 积压修复 |

---

## 8. 测试执行流程

```
每次 commit (CI):
  -> 后端: ruff check + mypy + pytest (unit + integration)
  -> 前端: ESLint + prettier + jest (unit)
  -> 合并前要求全部通过

每次 PR (CI):
  -> 上述所有
  -> Playwright E2E (3 条旅程)
  -> Lighthouse CI (性能基线)
  -> 覆盖率检查 (>= 85%)

发布前 (Manual Gate):
  -> 全量手工验收清单 (agents/07_acceptance_criteria.md)
  -> Codex 自主截图 + design_imgs 风格自检 + 迭代日志
  -> 人工探索测试 (30 min)
  -> 性能压测报告
  -> 安全审计报告
```
