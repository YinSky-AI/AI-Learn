# 数据模型设计 (09)

> **文件标识**: agents/09_data_model.md
> **关联文件**: 引用 00_project_overview.md、01_feature_design.md、04_architecture.md。

---

## 1. 核心实体关系图

```
User 1---N LearningSession 1---N Answer
  |                                  |
  |                                  |
  +---N Achievement                   +---N Question
  |                                  |
  +---1 AgeGroup                      |
  |   1                               |
  |   +---N KnowledgeNode 1---N Question
  |           |                       
  |           N                       
  |           |                       
  |      Subject ---- Type
  |
  +---N GeneratedQuestionBatch 1---N GeneratedQuestion
  |                                     |
  |                                     +---N QuestionQualityCheck
  |
  +---N HarnessRun 1---N ToolCallLog
  +---N SessionMemory
  +---1 UserProfile (behavior_profile)
  
  Skill (独立存储)
  SessionMemory 1---N User
  ErrorLog N---1 HarnessRun
  EvolutionRecord (独立存储)
  FeedbackSignal (中间表)
```

---

## 2. 实体定义

### 2.1 User (用户)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| nickname | VARCHAR(50) | NOT NULL | 昵称 |
| email | VARCHAR(255) | UNIQUE, NOT NULL | 邮箱 (登录凭证) |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt 哈希 |
| birth_date | DATE | NOT NULL | 出生日期，用于计算年龄分级 |
| age_group | VARCHAR(10) | NOT NULL | 当前年龄分级编码 |
| avatar_url | VARCHAR(500) | NULLABLE | 头像 URL |
| total_score | INTEGER | DEFAULT 0 | 总积分 |
| streak_days | INTEGER | DEFAULT 0 | 连续学习天数 |
| behavior_profile | JSONB | NULLABLE | 用户行为模型（能力估计、行为模式、偏好冲突、置信度） |
| last_login_date | DATE | NULLABLE | 上次登录日期 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL | 更新时间 |
| deleted_at | TIMESTAMP | NULLABLE | 软删除 |

**索引**: idx_user_email (email), idx_user_age_group (age_group)

### 2.2 AgeGroup (年龄分级)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | VARCHAR(10) | PK | AGE_06_09 / AGE_10_12 / AGE_13_15 / AGE_16_18 |
| name | VARCHAR(50) | NOT NULL | 显示名称 |
| min_age | INTEGER | NOT NULL | 最小年龄 |
| max_age | INTEGER | NOT NULL | 最大年龄 |
| theme_config | JSONB | NOT NULL | 主题配置 (颜色/字号/间距等) |

### 2.3 Subject (学科)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | VARCHAR(20) | PK | SUBJ_MATH / SUBJ_CHINESE / ... |
| name | VARCHAR(50) | NOT NULL | 学科名称 |
| icon | VARCHAR(100) | NULLABLE | 图标路径 |
| sort_order | INTEGER | DEFAULT 0 | 排序权重 |

### 2.4 KnowledgeNode (知识点)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| title | VARCHAR(200) | NOT NULL | 标题 |
| description | TEXT | NULLABLE | 简介 |
| subject_code | VARCHAR(20) | FK -> Subject | 所属学科 |
| age_group_code | VARCHAR(10) | FK -> AgeGroup | 适用年龄段 |
| difficulty_level | VARCHAR(10) | NOT NULL | DIFF_EASY / DIFF_MEDIUM / DIFF_HARD |
| content_type | VARCHAR(20) | NOT NULL | TYPE_READ / TYPE_QUIZ / TYPE_GAME |
| content_body | TEXT | NOT NULL | 知识内容主体 (Markdown) |
| estimated_minutes | INTEGER | DEFAULT 5 | 预计完成时长 |
| prerequisites | UUID[] | NULLABLE | 前置知识点 ID 列表 |
| sort_order | INTEGER | DEFAULT 0 | 在同一学科内的排序 |
| is_active | BOOLEAN | DEFAULT true | 是否启用 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL | 更新时间 |

**索引**: idx_node_subject (subject_code), idx_node_age (age_group_code), idx_node_diff (difficulty_level), idx_node_type (content_type)

### 2.5 Question (题目)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| knowledge_node_id | UUID | FK -> KnowledgeNode | 所属知识点 |
| difficulty_level | VARCHAR(10) | NOT NULL | 难度 |
| question_type | VARCHAR(20) | NOT NULL | CHOICE / MULTIPLE_CHOICE / FILL_BLANK |
| question_body | TEXT | NOT NULL | 题目内容 (Markdown) |
| options | JSONB | NULLABLE | 选择题选项: [{key, value}] |
| correct_answer | TEXT | NOT NULL | 正确答案 |
| explanation | TEXT | NULLABLE | 解析 |
| standard_time_seconds | INTEGER | DEFAULT 30 | 标准答题用时 |
| sort_order | INTEGER | DEFAULT 0 | 排序 |

**索引**: idx_question_node (knowledge_node_id), idx_question_diff (difficulty_level)

### 2.5.1 GeneratedQuestionBatch (AI 生成题目批次)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| user_id | UUID | FK -> User | 发起生成的用户 |
| age_group_code | VARCHAR(10) | NOT NULL | 生成时使用的年龄分级 |
| subject_code | VARCHAR(20) | NOT NULL | 学科 |
| course_topic | VARCHAR(200) | NOT NULL | 课程主题，如分数加法 |
| difficulty_level | VARCHAR(10) | NOT NULL | 难度 |
| question_types | JSONB | NOT NULL | 题型列表 |
| question_count | INTEGER | NOT NULL | 请求生成数量 |
| learning_goal | VARCHAR(200) | NULLABLE | 学习目标 |
| status | VARCHAR(20) | DEFAULT "pending" | pending / passed / failed / partial |
| prompt_version | VARCHAR(50) | NOT NULL | Prompt 模板版本 |
| harness_run_id | UUID | FK -> HarnessRun | 对应 Harness 执行记录 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |

**索引**: idx_gqb_user (user_id), idx_gqb_topic (subject_code, course_topic), idx_gqb_created (created_at)

### 2.5.2 GeneratedQuestion (AI 生成题目知识库)

> 这是 v0.1 的“生成题目知识库”：它不是预置教材库，也不承担联网搜索资料存储职责，而是在用户使用过程中逐步沉淀历史生成题、知识点标签、答题行为、题目指纹和错题关联，用于去重、复习、错题变式和后续个性化练习。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| batch_id | UUID | FK -> GeneratedQuestionBatch | 生成批次 |
| user_id | UUID | FK -> User | 用户 |
| knowledge_node_id | UUID | FK -> KnowledgeNode, NULLABLE | 可选关联知识点 |
| subject_code | VARCHAR(20) | NOT NULL | 学科 |
| course_topic | VARCHAR(200) | NOT NULL | 课程主题 |
| difficulty_level | VARCHAR(10) | NOT NULL | 难度 |
| question_type | VARCHAR(20) | NOT NULL | 题型 |
| question_body | TEXT | NOT NULL | 题干 |
| options | JSONB | NULLABLE | 选项 |
| correct_answer | TEXT | NOT NULL | 正确答案 |
| explanation | TEXT | NOT NULL | 解析 |
| knowledge_tags | JSONB | NOT NULL | 知识点标签 |
| source_prompt | TEXT | NOT NULL | 生成 Prompt 或 Prompt 摘要 |
| similarity_hash | VARCHAR(128) | NULLABLE | 去重用指纹 |
| quality_status | VARCHAR(20) | DEFAULT "unchecked" | unchecked / passed / failed |
| parent_question_id | UUID | FK -> GeneratedQuestion, NULLABLE | 变式题来源 |
| language | VARCHAR(10) | DEFAULT "zh-CN" | 题目语言，v0.1 默认简体中文 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |

**索引**: idx_gq_user_topic (user_id, subject_code, course_topic), idx_gq_diff (difficulty_level), idx_gq_type (question_type), idx_gq_language (language), idx_gq_created (created_at)

**检索策略**:
- v0.1 使用 PostgreSQL `tsvector` + `pg_trgm` 对 `question_body`、`course_topic`、`knowledge_tags` 做相似题检索。
- 生成题目知识库按用户维度沉淀，优先服务该用户的去重、复习和错题变式；平台级聚合能力属于后续增强，必须先处理隐私与脱敏。
- 后续如题量增大，可扩展 embedding 字段和向量数据库，但不是 v0.1 必需项。

### 2.5.3 QuestionQualityCheck (题目质量检查)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| generated_question_id | UUID | FK -> GeneratedQuestion | 被检查题目 |
| check_type | VARCHAR(50) | NOT NULL | answer / age / difficulty / duplicate / safety |
| status | VARCHAR(20) | NOT NULL | passed / failed / warning |
| score | FLOAT | NULLABLE | 检查得分 |
| message | TEXT | NULLABLE | 检查说明 |
| checker_version | VARCHAR(50) | NOT NULL | 检查器版本 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |

**索引**: idx_quality_question (generated_question_id), idx_quality_status (status)

### 2.6 LearningSession (学习会话)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| user_id | UUID | FK -> User | 用户 |
| knowledge_node_id | UUID | FK -> KnowledgeNode | 知识点 |
| difficulty_level | VARCHAR(10) | NOT NULL | 学习时的难度 |
| status | VARCHAR(20) | DEFAULT "in_progress" | in_progress / completed / abandoned |
| started_at | TIMESTAMP | NOT NULL | 开始时间 |
| completed_at | TIMESTAMP | NULLABLE | 完成时间 |
| correct_count | INTEGER | DEFAULT 0 | 正确数 |
| total_questions | INTEGER | DEFAULT 0 | 总题数 |

**索引**: idx_session_user (user_id), idx_session_node (knowledge_node_id)

### 2.7 Answer (答题记录)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| session_id | UUID | FK -> LearningSession | 会话 |
| question_id | UUID | FK -> Question | 题目 |
| user_answer | TEXT | NOT NULL | 用户答案 |
| is_correct | BOOLEAN | NOT NULL | 是否正确 |
| time_spent_seconds | INTEGER | NOT NULL | 用时 |
| answered_at | TIMESTAMP | NOT NULL | 答题时间 |

**索引**: idx_answer_session (session_id), idx_answer_question (question_id)

### 2.8 Achievement (成就)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| code | VARCHAR(50) | UNIQUE | 成就编码 (FIRST_LEARN / STREAK_7 / ...) |
| name | VARCHAR(100) | NOT NULL | 成就名称 |
| description | TEXT | NULLABLE | 达成条件描述 |
| icon_url | VARCHAR(500) | NULLABLE | 徽章图标 |
| criteria | JSONB | NOT NULL | 达成条件配置 |

### 2.9 UserAchievement (用户成就关联)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| user_id | UUID | FK -> User | 用户 |
| achievement_id | UUID | FK -> Achievement | 成就 |
| achieved_at | TIMESTAMP | NOT NULL | 达成时间 |

### 2.10 HarnessRun (AI Harness 执行记录)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| user_id | UUID | FK -> User | 用户 |
| run_type | VARCHAR(50) | NOT NULL | question_generation / variant_generation / ai_explain |
| status | VARCHAR(20) | NOT NULL | running / succeeded / failed |
| input_payload | JSONB | NOT NULL | Harness 输入 |
| output_summary | JSONB | NULLABLE | 输出摘要 |
| model_usage | JSONB | NULLABLE | Token、模型、耗时 |
| error_message | TEXT | NULLABLE | 错误信息 |
| started_at | TIMESTAMP | NOT NULL | 开始时间 |
| completed_at | TIMESTAMP | NULLABLE | 结束时间 |

**索引**: idx_harness_user (user_id), idx_harness_type (run_type), idx_harness_started (started_at)

### 2.11 ToolCallLog (工具调用日志)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| harness_run_id | UUID | FK -> HarnessRun | 所属 Harness run |
| step_name | VARCHAR(50) | NOT NULL | intent / plan / memory / generate / quality / save |
| tool_name | VARCHAR(100) | NOT NULL | 工具名 |
| input_summary | JSONB | NOT NULL | 输入摘要 |
| output_summary | JSONB | NULLABLE | 输出摘要 |
| latency_ms | INTEGER | NULLABLE | 耗时 |
| status | VARCHAR(20) | NOT NULL | succeeded / failed |
| error_message | TEXT | NULLABLE | 错误信息 |
| error_type | VARCHAR(50) | NULLABLE | 错误类型 (SAFE_AUDIT/QUALITY_FAIL/PERF_DEGRADE/LOGIC_ERROR) |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |

**索引**: idx_tool_run (harness_run_id), idx_tool_name (tool_name), idx_tool_status (status)

### 2.12 Skill（技能文件）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| name | VARCHAR(200) | UNIQUE, NOT NULL | Skill名称 |
| trigger_conditions | JSONB | NOT NULL | 触发条件（学科、主题、年龄、难度等） |
| version | INTEGER | NOT NULL, DEFAULT 1 | 版本号 |
| content | TEXT | NOT NULL | Skill内容（执行步骤+偏好+陷阱，Markdown） |
| success_count | INTEGER | DEFAULT 0 | 使用成功次数 |
| failure_count | INTEGER | DEFAULT 0 | 使用失败次数 |
| last_used_at | TIMESTAMP | NULLABLE | 最后使用时间 |
| quality_score_avg | FLOAT | NULLABLE | 平均质量得分 |
| is_active | BOOLEAN | DEFAULT true | 是否启用 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL | 更新时间 |

**索引**: idx_skill_trigger (trigger_conditions), idx_skill_name (name)

### 2.13 SessionMemory（会话记忆）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| user_id | UUID | FK -> User | 用户 |
| memory_type | VARCHAR(50) | NOT NULL | error_pattern / preference / quality_insight / behavior_pattern |
| content | TEXT | NOT NULL | 结构化记忆内容 |
| confidence | FLOAT | NOT NULL | 置信度 (0-1) |
| ttl_days | INTEGER | NOT NULL, DEFAULT 90 | 生存天数 |
| related_topic | VARCHAR(200) | NULLABLE | 关联主题 |
| expires_at | TIMESTAMP | NOT NULL | 过期时间 |
| is_expired | BOOLEAN | DEFAULT false | 是否已过期 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |

**索引**: idx_memory_user (user_id), idx_memory_topic (related_topic), idx_memory_expires (expires_at)
**检索策略**: PostgreSQL tsvector 对 content + related_topic 建全文检索索引

### 2.14 ErrorLog（错误日志）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| harness_run_id | UUID | FK -> HarnessRun, NULLABLE | 关联的 Harness 执行 |
| agent_name | VARCHAR(100) | NOT NULL | 出错 Agent 名称 |
| step_name | VARCHAR(50) | NOT NULL | 步骤名称 |
| error_type | VARCHAR(50) | NOT NULL | SAFE_AUDIT / QUALITY_FAIL / PERF_DEGRADE / LOGIC_ERROR |
| error_code | VARCHAR(10) | NOT NULL | 错误编码 (E001-E399) |
| severity | VARCHAR(10) | NOT NULL | P0 / P1 / P2 |
| raw_error | TEXT | NOT NULL | 原始错误信息 |
| context | JSONB | NULLABLE | 错误上下文 |
| affected_output | JSONB | NULLABLE | 受影响的输出 |
| routing_target | VARCHAR(100) | NULLABLE | 路由目标 Agent |
| auto_fix_attempted | BOOLEAN | DEFAULT false | 是否尝试自动修复 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |

**索引**: idx_error_type (error_type), idx_error_severity (severity), idx_error_agent (agent_name), idx_error_created (created_at)

### 2.15 EvolutionRecord（进化记录）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| evolution_type | VARCHAR(50) | NOT NULL | skill_created / skill_updated / memory_cleaned / strategy_changed |
| trigger_reason | TEXT | NOT NULL | 触发原因 |
| target_name | VARCHAR(200) | NOT NULL | 目标名称（Skill名/用户ID等） |
| change_content | JSONB | NOT NULL | 变更内容 |
| before_snapshot | JSONB | NULLABLE | 变更前快照 |
| after_snapshot | JSONB | NULLABLE | 变更后快照 |
| quality_before | FLOAT | NULLABLE | 变更前质量分 |
| quality_after | FLOAT | NULLABLE | 变更后质量分 |
| rolled_back | BOOLEAN | DEFAULT false | 是否已回滚 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |

**索引**: idx_evo_type (evolution_type), idx_evo_target (target_name), idx_evo_created (created_at)

---

## 3. 枚举常量

```
年龄分级: AGE_06_09, AGE_10_12, AGE_13_15, AGE_16_18
难度: DIFF_EASY, DIFF_MEDIUM, DIFF_HARD
学科: SUBJ_MATH, SUBJ_CHINESE, SUBJ_ENGLISH, SUBJ_SCIENCE, SUBJ_HISTORY, SUBJ_CODE, SUBJ_ART
学习形式: TYPE_READ, TYPE_QUIZ, TYPE_GAME, TYPE_VIDEO, TYPE_PROJECT, TYPE_CHAT
题目类型: CHOICE, MULTIPLE_CHOICE, FILL_BLANK
会话状态: in_progress, completed, abandoned
成就编码: FIRST_LOGIN, FIRST_LEARN, CORRECT_10, STREAK_3, STREAK_7, PERFECT_SCORE
生成批次状态: pending, passed, failed, partial
质量检查状态: unchecked, passed, failed, warning
Harness Run 类型: question_generation, variant_generation, ai_explain
记忆类型: error_pattern, preference, quality_insight, behavior_pattern
错误类型: SAFE_AUDIT, QUALITY_FAIL, PERF_DEGRADE, LOGIC_ERROR
错误严重度: P0, P1, P2
进化类型: skill_created, skill_updated, memory_cleaned, strategy_changed
```

---

## 4. 数据量预估 (v0.1)

| 表 | 预估行数 | 增长速率 |
|---|---------|---------|
| User | 100-200 (内测) | 慢 |
| KnowledgeNode | 50-100 (种子数据) | 手动导入 |
| Question | 150-300 (种子数据) | 手动导入 |
| GeneratedQuestionBatch | 500-2000/月 | 与 AI 出题次数相关 |
| GeneratedQuestion | 5000-20000/月 | 每批生成多题 |
| QuestionQualityCheck | 25000-100000/月 | 每题多项检查 |
| HarnessRun | 1000-5000/月 | AI 出题/解析/变式 |
| ToolCallLog | 5000-30000/月 | 每次 Harness 多步骤 |
| LearningSession | 500-2000/月 | 与用户活跃度相关 |
| Answer | 2000-8000/月 | 与学习会话相关 |

---

## 5. 数据库索引策略

- 所有主键: UUID 自建索引
- 所有外键: 自动索引 (SQLAlchemy 配置)
- 查询高频字段组合: idx_user_age_group, idx_node_subject, idx_node_age
- 全文检索: KnowledgeNode.title + description 建 tsvector 索引
- 生成题目知识库检索: GeneratedQuestion.question_body + course_topic + knowledge_tags 建 tsvector 与 pg_trgm 索引
- 时间序列: LearningSession.started_at, Answer.answered_at 建降序索引
- Skill触发条件: Skill.trigger_conditions 建 GIN 索引
- 会话记忆全文检索: SessionMemory.content + related_topic 建 tsvector 索引
- 错误日志分类查询: ErrorLog.error_type + severity 建联合索引
- 进化记录: EvolutionRecord.target_name + evolution_type 建联合索引

---

## 6. Redis 缓存设计

| Key 模式 | Value | TTL | 用途 |
|---------|-------|-----|------|
| user:{id}:session | JSON | 1h | 当前学习会话缓存 |
| content:{id}:{diff} | JSON | 1h | 内容缓存 |
| ai:rate:{user_id} | Counter | 1min | AI 限流计数 |
| ai:conversation:{session_id} | List | 30min | AI 对话历史临时存储 |
| ai:generation:{batch_id} | JSON | 30min | 题目生成过程状态 |
| question:dedup:{user_id}:{topic} | JSON | 1h | 近期生成题去重缓存 |
| user:{id}:streak | JSON | 24h | 连胜状态 |
| skill:cache:{name} | JSON | 1h | Skill 文件缓存 |
| user:{id}:behavior | JSON | 30min | 用户行为模型缓存 |
| evolution:lock | String | 10s | 进化操作分布式锁 |

---

## 7. PostgreSQL 初始化 SQL 示例

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nickname VARCHAR(50) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    birth_date DATE NOT NULL,
    age_group VARCHAR(10) NOT NULL,
    avatar_url VARCHAR(500),
    total_score INTEGER DEFAULT 0,
    streak_days INTEGER DEFAULT 0,
    last_login_date DATE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX idx_user_email ON users(email);
CREATE INDEX idx_user_age_group ON users(age_group);
```
