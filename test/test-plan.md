# AI 学堂智能学习平台 — 完整测试计划书

> 版本：v1.0
> 日期：2026-07-13
> 项目：AI-Learn 智能学习平台（FastAPI + Next.js + PostgreSQL + Redis + DeepSeek AI）

---

## 1 测试概述

### 1.1 项目背景

AI 学堂是一个面向青少年的智能学习平台，包含课程学习、AI 对话助手、AI 出题、成就系统、学习进度追踪等核心功能。技术栈采用前后端分离架构，后端使用 FastAPI 提供 49 个 API 端点，前端使用 Next.js 提供 8 个页面，通过 Docker Compose 编排部署。

### 1.2 测试目标

- 验证所有 49 个 API 端点的功能正确性
- 验证 8 个前端页面的交互逻辑和数据显示
- 验证用户认证与授权机制（JWT + Refresh Token）
- 验证 AI 对话 SSE 流式输出的实时性和完整性
- 验证学习进度统计的数据一致性
- 验证 Docker 部署环境的稳定性
- 验证异常场景下的错误处理和降级策略

### 1.3 测试范围

| 类别 | 范围 | 排除项 |
|------|------|--------|
| 后端 API | 全部 49 个端点 | 压力测试（仅验证基本并发） |
| 前端页面 | 全部 8 个页面 + 3 个 Store | 跨浏览器兼容性（仅 Chrome） |
| 数据库 | 23 张表的数据读写 | 数据迁移脚本 |
| AI 功能 | 对话流式输出、出题、解析 | AI 回答质量评估 |
| 基础设施 | Docker 4 服务 + Nginx | 生产环境部署 |
| 安全 | JWT、CORS、速率限制 | 渗透测试 |

---

## 2 测试环境

### 2.1 硬件环境

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 |
| 内存 | 16GB 以上 |
| 磁盘 | 20GB 可用空间 |
| Docker | Docker Desktop 最新版 |

### 2.2 软件环境

| 组件 | 版本 | 说明 |
|------|------|------|
| Docker Compose | v2+ | 容器编排 |
| PostgreSQL | 16-alpine | 主数据库 |
| Redis | 7-alpine | 缓存 & 速率限制 |
| Python | 3.12 | 后端运行时 |
| Node.js | 18-alpine | 前端运行时 |
| Nginx | latest | 反向代理 |
| 浏览器 | Chrome 最新版 | 前端测试 |

### 2.3 服务端口

| 服务 | 端口 | 访问地址 |
|------|------|----------|
| 前端 | 3000 | http://localhost:3000 |
| 后端 | 8000 | http://localhost:8000 |
| PostgreSQL | 5432 | localhost:5432 |
| Redis | 6379 | localhost:6379 |

### 2.4 测试数据准备

| 数据 | 说明 |
|------|------|
| 测试用户 A | 邮箱 `test-a@example.com`，密码 `123456`，昵称 `测试用户A`，年龄 10 岁 |
| 测试用户 B | 邮箱 `test-b@example.com`，密码 `123456`，昵称 `测试用户B`，年龄 15 岁 |
| 种子课程 | 执行 `seed_data.py` 生成的课程和课时数据 |
| DeepSeek API Key | 配置在 `backend/.env` 中 |

---

## 3 测试策略

### 3.1 测试分层

```
第一层：单元测试 → 后端 Service 层逻辑、前端 Store action
第二层：API 集成测试 → 49 个端点的请求/响应验证
第三层：前端 E2E 测试 → 8 个页面的用户交互流程
第四层：端到端测试 → 完整用户旅程（注册→学习→AI对话→查看成就）
第五层：基础设施测试 → Docker 部署、Nginx 代理、数据库持久化
```

### 3.2 测试用例编号规则

```
TC-{模块}-{序号}

模块编码：
  AUTH  = 认证模块
  USER  = 用户管理
  COURSE= 课程管理
  LEARN = 学习模块
  AI    = AI 功能
  ACHV  = 成就系统
  PROG  = 进度追踪
  CONTENT= 内容管理
  QUEST = AI 出题
  FE    = 前端页面
  INFRA = 基础设施
  SEC   = 安全测试
```

### 3.3 优先级定义

| 优先级 | 说明 | 覆盖范围 |
|--------|------|----------|
| P0 | 阻塞核心流程，必须通过 | 登录、注册、课程列表、学习完成 |
| P1 | 影响重要功能 | AI 对话、进度统计、成就、Token 刷新 |
| P2 | 影响辅助功能 | 筛选、排序、分页、个人资料 |
| P3 | 边界和异常场景 | 并发、超时、网络中断、空数据 |

---

## 4 认证模块测试（AUTH）

### 4.1 用户注册

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-AUTH-001 | 正常注册 | POST `/api/v1/auth/register`，body 含 username、password、email、nickname、age | 返回 200，data 含 access_token、refresh_token | P0 |
| TC-AUTH-002 | 邮箱已存在 | 使用已注册邮箱再次注册 | 返回 400，detail.message 为"该邮箱已被注册" | P0 |
| TC-AUTH-003 | 密码少于6位 | password = "123" | 返回 422 校验错误 | P1 |
| TC-AUTH-004 | 邮箱格式错误 | email = "not-an-email" | 返回 422 校验错误 | P1 |
| TC-AUTH-005 | 缺少必填字段 | 不传 nickname | 返回 422 校验错误 | P1 |
| TC-AUTH-006 | 年龄边界 | age = 6（最小）和 age = 18（最大） | 注册成功 | P2 |
| TC-AUTH-007 | 年龄超范围 | age = 5 或 age = 19 | 返回 422 校验错误 | P2 |

### 4.2 用户登录

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-AUTH-008 | 邮箱登录 | POST `/api/v1/auth/login`，username = 邮箱地址 | 返回 200，含 access_token、refresh_token | P0 |
| TC-AUTH-009 | 昵称登录 | POST `/api/v1/auth/login`，username = 昵称 | 返回 200，含 access_token、refresh_token | P0 |
| TC-AUTH-010 | 密码错误 | password = "wrong" | 返回 401，message 为"用户名或密码错误" | P0 |
| TC-AUTH-011 | 不存在的用户 | username = "nobody@test.com" | 返回 401，message 为"用户名或密码错误" | P0 |
| TC-AUTH-012 | 登录后自动获取 profile | 登录成功后前端自动调用 `/users/me` | 前端显示用户昵称，右上角显示头像 | P0 |
| TC-AUTH-013 | 登录后自动获取 stats | 登录成功后前端自动调用 `/users/me/stats` | 首页显示真实统计数据（非硬编码） | P0 |
| TC-AUTH-014 | 错误登录不刷新页面 | 输入错误密码点击登录 | 页面保持不动，显示错误提示，不触发 401 跳转 | P0 |

### 4.3 Token 刷新

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-AUTH-015 | 正常刷新 | POST `/api/v1/auth/refresh`，body 含有效 refresh_token | 返回 200，含新的 access_token 和 refresh_token | P1 |
| TC-AUTH-016 | 无效 refresh_token | refresh_token = "invalid" | 返回 401 | P1 |
| TC-AUTH-017 | 过期 refresh_token | 使用超过 7 天的 refresh_token | 返回 401 | P1 |
| TC-AUTH-018 | 自动刷新触发 | access_token 过期后发起 API 请求 | 前端自动调用 refresh，重试原请求成功 | P1 |
| TC-AUTH-019 | 刷新失败跳转登录 | refresh_token 也过期时发起请求 | 前端清除 token，跳转到 `/login` | P1 |
| TC-AUTH-020 | 认证端点不触发刷新 | `/v1/auth/login` 返回 401 | 不触发自动刷新逻辑，直接返回错误 | P0 |

### 4.4 登出

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-AUTH-021 | 正常登出 | 已登录状态点击登出 | 清除 localStorage token、课程进度、聊天记录，跳转 `/home` | P0 |
| TC-AUTH-022 | 登出后数据隔离 | 登出后重新登录另一账号 | 不显示前一账号的学习进度和聊天记录 | P0 |

---

## 5 用户管理测试（USER）

### 5.1 获取用户信息

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-USER-001 | 获取个人信息 | GET `/api/v1/users/me`，带有效 token | 返回 200，含 id、nickname、email、total_score、streak_days 等 | P0 |
| TC-USER-002 | 无 token 请求 | GET `/api/v1/users/me`，不带 Authorization | 返回 401 | P0 |
| TC-USER-003 | token 无效 | GET `/api/v1/users/me`，Authorization = "Bearer invalid" | 返回 401 | P1 |
| TC-USER-004 | 获取行为档案 | GET `/api/v1/users/me/profile` | 返回 200，含 behavior_profile 数据 | P2 |

### 5.2 更新用户信息

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-USER-005 | 更新昵称 | PUT `/api/v1/users/me`，body 含新昵称 | 返回 200，nickname 已更新 | P2 |
| TC-USER-006 | 更新头像 | PUT `/api/v1/users/me`，body 含新 avatar_url | 返回 200，avatar_url 已更新 | P2 |

### 5.3 学习统计

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-USER-007 | 新用户统计 | 新注册用户调用 GET `/api/v1/users/me/stats` | total_score=0, streak_days=0, today_study_minutes=0, completed_courses=0 | P0 |
| TC-USER-008 | 完成课时后统计更新 | 完成一课时后调用 stats | total_completed_lessons 增加 1 | P0 |
| TC-USER-009 | 今日学习时间统计 | 完成课时（含 time_spent_seconds）后查看 stats | today_study_minutes 为各课时用时之和/60 | P1 |
| TC-USER-010 | 本周学习时间统计 | 本周内完成多个课时 | week_study_hours 为本周所有课时用时之和/3600 | P1 |
| TC-USER-011 | 进行中课程数 | 报名课程但未完成全部课时 | in_progress_courses 正确计数 | P1 |
| TC-USER-012 | 已完成课程数 | 某课程下所有课时都已完成 | completed_courses 正确计数 | P1 |
| TC-USER-013 | 总体进度百分比 | 有进行中和已完成课程 | overall_progress = completed / (in_progress + completed) * 100 | P1 |

---

## 6 课程管理测试（COURSE）

### 6.1 课程列表

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-COURSE-001 | 获取课程列表 | GET `/api/v1/courses` | 返回 200，含课程数组（id、title、subject、difficulty、duration、rating、enrollment_count） | P0 |
| TC-COURSE-002 | 按学科筛选 | GET `/api/v1/courses?subject=MATH` | 返回的课程 subject 均为 MATH | P1 |
| TC-COURSE-003 | 按难度筛选 | GET `/api/v1/courses?difficulty=beginner` | 返回的课程 difficulty 均为 beginner | P1 |
| TC-COURSE-004 | 按年龄筛选 | GET `/api/v1/courses?age_group=AGE_06_09` | 返回的课程适合该年龄段 | P2 |
| TC-COURSE-005 | 关键词搜索 | GET `/api/v1/courses?keyword=数学` | 返回标题或描述含"数学"的课程 | P1 |
| TC-COURSE-006 | 分页 | GET `/api/v1/courses?page=1&page_size=5` | 返回最多 5 条课程，含分页信息 | P2 |
| TC-COURSE-007 | 无需认证 | 未登录状态调用 | 正常返回课程列表 | P0 |

### 6.2 课程详情

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-COURSE-008 | 按 ID 获取详情 | GET `/api/v1/courses/{course_id}` | 返回 200，含完整课程信息和课时列表 | P0 |
| TC-COURSE-009 | 按 slug 获取详情 | GET `/api/v1/courses/{slug}` | 返回 200，同上 | P2 |
| TC-COURSE-010 | 不存在的课程 | GET `/api/v1/courses/non-existent-id` | 返回 404 | P1 |
| TC-COURSE-011 | 获取课时列表 | GET `/api/v1/courses/{course_id}/lessons` | 返回 200，按 order 排序的课时数组 | P0 |

### 6.3 用户课程操作

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-COURSE-012 | 报名课程 | POST `/api/v1/user/courses/{course_id}/enroll` | 返回 200，user_courses 表新增记录 | P0 |
| TC-COURSE-013 | 重复报名 | 已报名课程再次 enroll | 不报错或返回已报名提示 | P2 |
| TC-COURSE-014 | 获取我的课程 | GET `/api/v1/user/courses` | 返回已报名课程列表，含进度 | P0 |
| TC-COURSE-015 | 未登录获取我的课程 | GET `/api/v1/user/courses` 无 token | 返回空列表或提示登录 | P1 |

---

## 7 学习模块测试（LEARN）

### 7.1 课时完成

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-LEARN-001 | 完成单个课时 | POST `/api/v1/user/lessons/{lesson_id}/complete`，body 含 time_spent_seconds | 返回 200，user_lessons 表新增 completed=true 记录 | P0 |
| TC-LEARN-002 | 重复完成同一课时 | 同一 lesson_id 再次 complete | 不重复创建记录，更新 time_spent_seconds | P1 |
| TC-LEARN-003 | 完成全部课时 | 依次完成课程下所有课时 | 课程状态变为 completed，进度 100% | P0 |
| TC-LEARN-004 | 完成后自动切换下一课时 | 前端 startLearning 中完成后 | currentLesson 切换到下一个未完成课时 | P0 |
| TC-LEARN-005 | 完成后刷新首页统计 | 完成课时后查看首页 | 统计数据实时更新（不刷新页面） | P0 |
| TC-LEARN-006 | 学习用时记录 | complete 请求中 time_spent_seconds = 300 | stats 中 today_study_minutes 增加 5 | P1 |

### 7.2 学习进度

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-LEARN-007 | 首页进度环 | 登录后查看首页学习进度 | 显示真实的进行中/已完成课程数和百分比 | P0 |
| TC-LEARN-008 | 课程详情页进度条 | 进入课程详情页 | 显示已完成课时数/总课时数和进度百分比 | P0 |
| TC-LEARN-009 | 学习页统计卡片 | 进入 /learning 页面 | 显示总课程、学习中、已完成、总进度 | P1 |
| TC-LEARN-010 | 进度持久化 | 刷新页面后查看进度 | 进度数据不丢失（来自后端 + localStorage） | P0 |
| TC-LEARN-011 | 进度总览 API | GET `/api/v1/progress/overview` | 返回总会话数、完成数、正确率等 | P1 |
| TC-LEARN-012 | 最近学习活动 | GET `/api/v1/progress/recent` | 返回最近的学习记录列表 | P2 |

### 7.3 学习会话（AI 答题）

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-LEARN-013 | 创建学习会话 | POST `/api/v1/learning/sessions` | 返回 200，含 session_id | P1 |
| TC-LEARN-014 | 提交答案 | POST `/api/v1/learning/sessions/{id}/answer` | 返回 200，含是否正确 | P1 |
| TC-LEARN-015 | 完成会话 | POST `/api/v1/learning/sessions/{id}/complete` | 返回 200，含统计（正确数/总题数） | P1 |
| TC-LEARN-016 | 获取会话列表 | GET `/api/v1/learning/sessions` | 返回分页的学习会话列表 | P2 |

---

## 8 AI 功能测试（AI）

### 8.1 AI 对话流式输出

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-AI-001 | 正常对话 | POST `/api/v1/ai/chat`，body 含 message 和 conversationHistory | 返回 SSE 流，Content-Type: text/event-stream | P0 |
| TC-AI-002 | 流式内容逐块接收 | 解析 SSE 流 | 每个 `data: {"content": "..."}` 包含文本片段 | P0 |
| TC-AI-003 | 流结束事件 | 等待流结束 | 收到 `data: {"done": true, "reply": "完整内容", "suggestions": [...]}` | P0 |
| TC-AI-004 | 前端逐字显示 | 在课程详情页发送消息 | AI 回复实时逐字更新，而非等待完整回复 | P0 |
| TC-AI-005 | 正在思考状态 | 发送消息后等待期间 | 显示"正在思考中..."动画 | P1 |
| TC-AI-006 | 多轮对话上下文 | 连续发送多条消息 | AI 回复考虑之前的对话历史（最近 10 条） | P1 |
| TC-AI-007 | 课程上下文 | 在某课程页面发起对话 | AI 回复包含该课程的上下文信息 | P1 |
| TC-AI-008 | 年龄段适配 | 6-8 岁用户对话 | AI 回复使用适合该年龄段的语气和内容 | P2 |
| TC-AI-009 | 快捷问题 | 点击"解释这个知识点"等快捷按钮 | 自动发送对应消息，AI 正常回复 | P1 |
| TC-AI-010 | Markdown 渲染 | AI 回复包含 Markdown 格式 | 前端正确渲染标题、列表、代码块等 | P1 |
| TC-AI-011 | 对话历史保存 | 发送消息后刷新页面 | 聊天记录从 localStorage 恢复 | P1 |
| TC-AI-012 | 清空对话 | 点击清空聊天 | localStorage 和内存中的聊天记录均清空 | P2 |
| TC-AI-013 | AI 服务不可用 | DeepSeek API Key 无效或网络中断 | 返回 fallback 错误回复，不崩溃 | P0 |
| TC-AI-014 | 未登录使用 AI | 未登录状态在课程页发消息 | 输入框 disabled，显示"登录后即可使用AI助手" | P0 |
| TC-AI-015 | 流式错误处理 | AI 返回错误 | 前端收到 `{"error": true, "content": "..."}`，显示错误提示 | P1 |

### 8.2 AI 出题

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-AI-016 | 生成题目 | POST `/api/v1/questions/generate`，含学科、主题、难度 | 返回 200，含生成的题目列表 | P1 |
| TC-AI-017 | 查询批次列表 | GET `/api/v1/questions/batches` | 返回生成批次列表 | P2 |
| TC-AI-018 | 获取批次详情 | GET `/api/v1/questions/batches/{batch_id}` | 返回批次详情和题目列表 | P2 |
| TC-AI-019 | 生成变式题 | POST `/api/v1/questions/variant`，含源题目 ID | 返回难度相近的新题目 | P2 |
| TC-AI-020 | 题目历史 | GET `/api/v1/questions/history` | 返回生成历史列表 | P2 |

### 8.3 AI 解析和错题分析

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-AI-021 | 题目解析 | GET `/api/v1/ai/explain/{question_id}` | 返回 200，含详细解析和知识点讲解 | P1 |
| TC-AI-022 | 错题分析 | POST `/api/v1/ai/error-analysis`，含错误答题记录 | 返回 200，含错误模式分析 | P1 |

### 8.4 AI 进化系统

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-AI-023 | 获取技能列表 | GET `/api/v1/ai/skills` | 返回技能列表（分页） | P3 |
| TC-AI-024 | 获取技能详情 | GET `/api/v1/ai/skills/{skill_id}` | 返回技能内容和触发条件 | P3 |
| TC-AI-025 | 获取进化记录 | GET `/api/v1/ai/evolution-log` | 返回进化记录列表 | P3 |
| TC-AI-026 | 获取错误日志 | GET `/api/v1/ai/error-log` | 返回错误日志列表 | P3 |
| TC-AI-027 | 获取会话记忆 | GET `/api/v1/ai/memories`，带 token | 返回用户记忆列表 | P3 |

---

## 9 成就系统测试（ACHV）

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-ACHV-001 | 获取所有成就 | GET `/api/v1/achievements` | 返回成就列表（含编码、名称、描述、图标、条件） | P1 |
| TC-ACHV-002 | 获取我的成就 | GET `/api/v1/achievements/me`，带 token | 返回已解锁和未解锁的成就及解锁时间 | P1 |
| TC-ACHV-003 | 检查成就 | POST `/api/v1/achievements/check`，带 token | 自动检查条件并发放新成就 | P1 |
| TC-ACHV-004 | 首页成就显示-未登录 | 未登录查看首页 | 成就区域隐藏，推荐课程占满宽度 | P0 |
| TC-ACHV-005 | 首页成就显示-新用户 | 新注册用户查看首页 | 成就显示灰色锁定状态，提示还需多少 | P0 |
| TC-ACHV-006 | 首页成就-连续学习7天 | streak_days >= 7 | "连续学习7天"成就彩色显示 | P1 |
| TC-ACHV-007 | 首页成就-完成首门课程 | completed_courses >= 1 | "完成首门课程"成就彩色显示 | P1 |
| TC-ACHV-008 | 首页成就-获得100经验 | total_score >= 100 | "获得100经验"成就彩色显示 | P1 |

---

## 10 内容管理测试（CONTENT）

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-CONTENT-001 | 获取年龄分级 | GET `/api/v1/content/age-groups` | 返回 AGE_06_09、AGE_09_12、AGE_12_15、AGE_15_18 等 | P2 |
| TC-CONTENT-002 | 获取学科列表 | GET `/api/v1/content/subjects` | 返回 MATH、SCIENCE、ENGLISH、PROGRAMMING、ART 等 | P2 |
| TC-CONTENT-003 | 知识点列表 | GET `/api/v1/content/knowledge-nodes` | 返回分页的知识点列表 | P2 |
| TC-CONTENT-004 | 知识点筛选 | GET `/api/v1/content/knowledge-nodes?subject=MATH&difficulty=easy` | 返回筛选后的知识点 | P2 |
| TC-CONTENT-005 | 知识点详情 | GET `/api/v1/content/knowledge-nodes/{node_id}` | 返回知识点完整信息 | P2 |
| TC-CONTENT-006 | 知识点题目 | GET `/api/v1/content/knowledge-nodes/{node_id}/questions` | 返回该知识点下的题目列表 | P2 |
| TC-CONTENT-007 | 无需认证 | 未登录调用内容接口 | 正常返回数据 | P1 |

---

## 11 前端页面测试（FE）

### 11.1 登录页 `/login`

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-FE-001 | 页面加载 | 访问 `/login` | 显示登录表单（用户名、密码、登录按钮、注册链接） | P0 |
| TC-FE-002 | 空字段校验 | 不填任何内容点击登录 | 显示"请输入用户名"等提示 | P0 |
| TC-FE-003 | 密码显隐切换 | 点击密码框右侧眼睛图标 | 密码在明文和密文间切换 | P2 |
| TC-FE-004 | 登录成功跳转 | 输入正确账密点击登录 | 跳转到 `/home`，右上角显示用户信息 | P0 |
| TC-FE-005 | 登录失败不刷新 | 输入错误密码点击登录 | 显示错误提示，页面不刷新不跳转 | P0 |
| TC-FE-006 | 跳转注册 | 点击"立即注册" | 跳转到 `/register` | P1 |

### 11.2 注册页 `/register`

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-FE-007 | 页面加载 | 访问 `/register` | 显示注册表单（用户名、昵称、邮箱、密码、确认密码、年龄、性别） | P0 |
| TC-FE-008 | 密码不匹配 | 密码和确认密码不一致 | 显示"两次输入的密码不一致" | P0 |
| TC-FE-009 | 密码过短 | 密码少于 6 位 | 显示"密码至少6位" | P1 |
| TC-FE-010 | 注册成功自动登录 | 填写完整信息点击注册 | 注册成功后自动登录并跳转 `/home` | P0 |
| TC-FE-011 | 邮箱已存在 | 使用已注册邮箱 | 显示"该邮箱已被注册" | P0 |
| TC-FE-012 | 年龄选择 | 点击年龄下拉框 | 显示 6-18 岁选项 | P2 |
| TC-FE-013 | 性别选择 | 点击性别下拉框 | 显示男/女选项 | P2 |

### 11.3 首页 `/home`

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-FE-014 | 未登录首页 | 未登录访问 `/home` | 显示欢迎横幅、统计为"--"、成就区域隐藏、推荐课程正常显示 | P0 |
| TC-FE-015 | 已登录首页 | 登录后访问 `/home` | 显示用户昵称、真实统计数据、成就区域（根据状态显示） | P0 |
| TC-FE-016 | 继续学习-未登录 | 未登录查看"继续学习" | 显示为空或提示登录 | P0 |
| TC-FE-017 | 继续学习-已登录 | 有进度课程时 | 显示进行中课程卡片 | P0 |
| TC-FE-018 | 推荐课程 | 查看推荐课程区域 | 显示 4 个课程卡片 | P1 |
| TC-FE-019 | 统计卡片 | 已登录查看统计 | 今日学习、本周学习、连续打卡、获得经验显示真实数据 | P0 |
| TC-FE-020 | 学习进度环 | 已登录查看进度环 | 显示进行中/已完成课程数和百分比 | P0 |
| TC-FE-021 | 右上角未登录跳转 | 未登录点击右上角 | 跳转到 `/login` | P0 |
| TC-FE-022 | 左下角未登录跳转 | 未登录点击左下角用户区 | 跳转到 `/login` | P0 |

### 11.4 探索页 `/explore`

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-FE-023 | 课程列表加载 | 访问 `/explore` | 显示课程卡片网格 | P0 |
| TC-FE-024 | 学科筛选 | 点击学科筛选标签 | 列表更新为对应学科课程 | P1 |
| TC-FE-025 | 难度筛选 | 点击难度筛选标签 | 列表更新为对应难度课程 | P1 |
| TC-FE-026 | 关键词搜索 | 在搜索框输入关键词 | 列表过滤包含关键词的课程 | P1 |
| TC-FE-027 | 重置筛选 | 点击重置按钮 | 筛选条件清空，显示全部课程 | P2 |
| TC-FE-028 | 空状态 | 筛选结果为空 | 显示空状态提示 | P2 |
| TC-FE-029 | 点击课程卡片 | 点击课程卡片 | 跳转到 `/learning/{course_id}` | P0 |

### 11.5 我的学习页 `/learning`

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-FE-030 | 统计卡片 | 访问 `/learning` | 显示总课程、学习中、已完成、总进度 | P1 |
| TC-FE-031 | 继续学习列表 | 有进行中课程 | 显示横向课程卡片+进度条 | P1 |
| TC-FE-032 | 已完成课程 | 有已完成课程 | 显示已完成课程分区 | P2 |
| TC-FE-033 | 空状态 | 无任何课程 | 显示推荐课程或空状态提示 | P2 |

### 11.6 课程详情页 `/learning/[id]`

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-FE-034 | 页面加载 | 访问 `/learning/{id}` | 左侧显示课程信息+当前课时，右侧显示大纲+AI助手 | P0 |
| TC-FE-035 | 课时切换 | 点击大纲中的其他课时 | 左侧内容切换到对应课时 | P0 |
| TC-FE-036 | 开始学习 | 点击"开始学习"按钮 | 标记当前课时完成，切换到下一课时 | P0 |
| TC-FE-037 | 完成全部课时 | 完成最后一个课时 | 显示"已完成全部课时"提示 | P0 |
| TC-FE-038 | AI 对话面板 | 在右侧输入框输入消息 | AI 流式回复，逐字显示 | P0 |
| TC-AI-039 | 聊天记录恢复 | 发送消息后刷新页面 | 聊天记录从 localStorage 恢复 | P1 |
| TC-FE-040 | 进度条更新 | 完成一个课时 | 课程进度条更新（如 1/5 -> 2/5） | P0 |
| TC-FE-041 | 首页统计联动 | 完成课时后返回首页 | 首页统计数据自动更新 | P0 |

### 11.7 个人资料页 `/profile`

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-FE-042 | 未登录引导 | 未登录访问 `/profile` | 显示登录引导 | P1 |
| TC-FE-043 | 个人信息卡片 | 已登录访问 `/profile` | 显示头像、昵称、等级、经验值进度条 | P1 |
| TC-FE-044 | 统计数据 | 查看统计区域 | 显示连续学习、周目标、累计经验 | P1 |
| TC-FE-045 | 技能面板 Tab | 点击"技能"Tab | 显示技能列表和进度环 | P2 |
| TC-FE-046 | 徽章面板 Tab | 点击"徽章"Tab | 显示成就徽章和解锁状态 | P2 |
| TC-FE-047 | 设置面板 Tab | 点击"设置"Tab | 显示隐私、通知、显示、学习提醒入口 | P2 |

### 11.8 布局组件

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-FE-048 | 侧边栏导航 | 点击侧边栏各链接 | 跳转到对应页面（首页/探索/学习/我的） | P0 |
| TC-FE-049 | 顶栏搜索 | 在顶栏搜索框输入关键词 | 跳转到探索页并显示搜索结果 | P1 |
| TC-FE-050 | 移动端导航 | 缩小窗口宽度 | 显示底部导航栏 | P2 |
| TC-FE-051 | 主题适配 | 不同年龄段用户登录 | 主题颜色根据年龄组自动切换 | P2 |

---

## 12 安全测试（SEC）

### 12.1 JWT 认证安全

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-SEC-001 | 无 Token 访问受保护端点 | GET `/api/v1/users/me` 无 Authorization | 返回 401，code: AUTH_001 | P0 |
| TC-SEC-002 | 无效 Token | GET `/api/v1/users/me`，Bearer "invalid" | 返回 401，code: AUTH_002 | P0 |
| TC-SEC-003 | 过期 Access Token | 使用超过 30 分钟的 access token | 返回 401，前端自动刷新 | P1 |
| TC-SEC-004 | Token 类型错误 | 使用 refresh token 作为 access token | 返回 401 | P1 |
| TC-SEC-005 | 密码加密存储 | 查看数据库 users 表 | password_hash 为 bcrypt 哈希，非明文 | P0 |
| TC-SEC-006 | SQL 注入 | 登录时 username 输入 `' OR 1=1 --` | 返回 401，不泄露数据 | P0 |

### 12.2 CORS 安全

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-SEC-007 | 允许的源 | 从 localhost:3000 发起请求 | 正常返回，含 CORS 头 | P1 |
| TC-SEC-008 | 不允许的源 | 从 example.com 发起请求 | 浏览器拦截响应 | P1 |

### 12.3 速率限制

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-SEC-009 | 正常请求频率 | 1 分钟内发送 50 个请求 | 全部正常返回 | P1 |
| TC-SEC-010 | 超限请求 | 1 分钟内发送超过 60 个请求 | 超出部分返回 429 | P1 |
| TC-SEC-011 | 健康检查不限速 | 频繁请求 `/health` | 不触发速率限制 | P2 |
| TC-SEC-012 | Redis 不可用降级 | 停止 Redis 后发请求 | 速率限制降级跳过，请求正常处理 | P2 |

### 12.4 其他安全

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-SEC-013 | .env 不提交 | 检查 .gitignore | .env 文件被排除 | P0 |
| TC-SEC-014 | 非根用户运行 | 检查 Dockerfile | 后端和前端均使用非 root 用户 | P1 |
| TC-SEC-015 | XSS 防护 | 在聊天消息中输入 `<script>alert(1)</script>` | 脚本不执行，内容正常显示为文本 | P0 |

---

## 13 基础设施测试（INFRA）

### 13.1 Docker 部署

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-INFRA-001 | 全量构建启动 | `docker-compose up -d --build` | 4 个服务全部 Running | P0 |
| TC-INFRA-002 | 健康检查 | 访问 `http://localhost:8000/health` | 返回 200，含 app_name、version、status | P0 |
| TC-INFRA-003 | 前端访问 | 访问 `http://localhost:3000` | 显示首页 | P0 |
| TC-INFRA-004 | 后端文档 | 访问 `http://localhost:8000/docs` | 显示 Swagger UI | P1 |
| TC-INFRA-005 | 数据库初始化 | 检查 PostgreSQL | learning_platform 库和 23 张表已创建 | P0 |
| TC-INFRA-006 | Redis 连接 | 后端日志无 Redis 连接错误 | Redis 正常用于速率限制 | P1 |

### 13.2 服务依赖

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-INFRA-007 | 数据库健康检查 | docker-compose 中 postgres healthcheck | pg_isready 返回成功 | P1 |
| TC-INFRA-008 | Redis 健康检查 | docker-compose 中 redis healthcheck | redis-cli ping 返回 PONG | P1 |
| TC-INFRA-009 | 后端等待数据库 | 启动顺序 | 后端在 postgres 和 redis 健康后启动 | P1 |
| TC-INFRA-010 | 前端等待后端 | 启动顺序 | 前端在后端后启动 | P1 |

### 13.3 数据持久化

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-INFRA-011 | 数据库持久化 | 重启 postgres 容器 | 数据不丢失 | P0 |
| TC-INFRA-012 | Redis 持久化 | 重启 redis 容器 | AOF 持久化数据恢复 | P1 |
| TC-INFRA-013 | 容器重建数据保留 | `docker-compose down && docker-compose up` | postgres_data 和 redis_data 卷保留 | P0 |

### 13.4 Nginx 反向代理

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-INFRA-014 | API 代理 | 通过 Nginx 访问 `/api/v1/courses` | 正常返回数据 | P1 |
| TC-INFRA-015 | SSE 代理 | 通过 Nginx 访问 `/api/v1/ai/chat` | SSE 流正常传输，proxy_buffering off 生效 | P0 |
| TC-INFRA-016 | 静态资源缓存 | 访问 `/_next/static/` | 返回 304 或 Cache-Control: max-age=31536000 | P2 |
| TC-INFRA-017 | Gzip 压缩 | 检查响应头 | Content-Encoding: gzip | P2 |
| TC-INFRA-018 | 安全头 | 检查响应头 | 含 X-Frame-Options、X-Content-Type-Options 等 | P2 |

### 13.5 日志和监控

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-INFRA-019 | 后端访问日志 | docker logs ai-learn-backend | 记录请求路径、状态码、耗时 | P2 |
| TC-INFRA-020 | Request ID | 检查响应头 | 含 X-Request-ID | P2 |
| TC-INFRA-021 | 错误日志 | 触发 500 错误 | 日志记录 request_id 和异常堆栈 | P2 |

---

## 14 异常和边界测试

### 14.1 网络异常

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-EX-001 | AI 对话中途断开 | SSE 流传输中断开连接 | 前端显示部分内容 + 错误提示 | P1 |
| TC-EX-002 | 后端不可用时前端降级 | 停止后端，访问课程列表 | 前端回退到 mock 数据，显示课程 | P0 |
| TC-EX-003 | 数据库连接失败 | 停止 postgres 后发 API 请求 | 返回 500 结构化错误，不崩溃 | P1 |
| TC-EX-004 | Redis 连接失败 | 停止 redis 后发 API 请求 | 速率限制降级，API 正常工作 | P1 |

### 14.2 数据边界

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-EX-005 | 空课程列表 | 数据库无课程数据 | 前端显示空状态提示 | P1 |
| TC-EX-006 | 超长消息 | AI 对话发送 10000 字符消息 | 不崩溃，正常处理或截断 | P2 |
| TC-EX-007 | 分页越界 | GET `/api/v1/courses?page=999` | 返回空数组，不报错 | P2 |
| TC-EX-008 | 特殊字符 | 注册时昵称含 emoji 和特殊字符 | 正常注册或给出明确错误 | P2 |

### 14.3 并发场景

| 用例编号 | 场景 | 操作步骤 | 预期结果 | 优先级 |
|----------|------|----------|----------|--------|
| TC-EX-009 | 并发完成同一课时 | 两个请求同时 complete 同一 lesson | 不产生重复记录 | P2 |
| TC-EX-010 | 并发报名同一课程 | 两个请求同时 enroll | 不产生重复报名记录 | P2 |
| TC-EX-011 | Token 并发刷新 | 多个请求同时触发 refresh | 只刷新一次，其他请求等待 | P1 |

---

## 15 端到端测试流程

### 15.1 新用户完整旅程

| 用例编号 | 步骤 | 预期结果 | 优先级 |
|----------|------|----------|--------|
| TC-E2E-001 | 1. 访问首页（未登录） | 显示欢迎页面，统计为"--"，成就隐藏 | P0 |
| TC-E2E-001 | 2. 点击右上角跳转登录 | 跳转到登录页 | P0 |
| TC-E2E-001 | 3. 点击"立即注册"跳转注册 | 跳转到注册页 | P0 |
| TC-E2E-001 | 4. 填写注册信息并提交 | 注册成功，自动登录，跳转首页 | P0 |
| TC-E2E-001 | 5. 首页显示用户信息 | 右上角显示昵称，统计为 0，成就显示锁定 | P0 |
| TC-E2E-001 | 6. 进入探索页选择课程 | 显示课程列表，点击进入课程详情 | P0 |
| TC-E2E-001 | 7. 开始学习第一课时 | 课时标记完成，切换到下一课时 | P0 |
| TC-E2E-001 | 8. 使用 AI 助手提问 | AI 流式回复，逐字显示 | P0 |
| TC-E2E-001 | 9. 返回首页查看统计 | 统计数据更新（课时数+1，学习时间增加） | P0 |
| TC-E2E-001 | 10. 查看成就 | 成就显示部分解锁或进度更新 | P1 |

### 15.2 老用户登录旅程

| 用例编号 | 步骤 | 预期结果 | 优先级 |
|----------|------|----------|--------|
| TC-E2E-002 | 1. 访问登录页 | 显示登录表单 | P0 |
| TC-E2E-002 | 2. 输入账密登录 | 登录成功，跳转首页 | P0 |
| TC-E2E-002 | 3. 首页显示历史数据 | 统计、进度、成就显示上次学习的真实数据 | P0 |
| TC-E2E-002 | 4. 继续学习未完成课程 | 从上次进度继续 | P0 |
| TC-E2E-002 | 5. 查看聊天记录 | 显示之前的 AI 对话历史 | P1 |

### 15.3 登出切换账号旅程

| 用例编号 | 步骤 | 预期结果 | 优先级 |
|----------|------|----------|--------|
| TC-E2E-003 | 1. 已登录状态点击登出 | 清除数据，跳转首页 | P0 |
| TC-E2E-003 | 2. 首页显示未登录状态 | 统计为"--"，成就隐藏 | P0 |
| TC-E2E-003 | 3. 登录另一账号 | 显示新账号数据，不显示旧账号数据 | P0 |
| TC-E2E-003 | 4. 查看课程进度 | 新账号进度独立，不受旧账号影响 | P0 |

---

## 16 测试执行检查清单

### 16.1 冒烟测试（每次部署后执行）

| 检查项 | 通过条件 |
|--------|----------|
| Docker 服务全部启动 | `docker ps` 显示 4 个容器 Running |
| 健康检查通过 | `GET /health` 返回 200 |
| 前端页面可访问 | `http://localhost:3000` 显示首页 |
| 注册功能正常 | 新用户注册返回 200 + token |
| 登录功能正常 | 已有用户登录返回 200 + token |
| 课程列表正常 | `GET /courses` 返回课程数据 |
| AI 对话正常 | `POST /ai/chat` 返回 SSE 流 |

### 16.2 回归测试（每次代码修改后执行）

| 模块 | 检查项 | 关联用例 |
|------|--------|----------|
| 认证 | 登录/注册/Token 刷新/登出 | TC-AUTH-001 ~ TC-AUTH-022 |
| 首页 | 未登录显示 / 已登录统计 / 成就显示 | TC-FE-014 ~ TC-FE-022 |
| 课程 | 列表/详情/报名/完成课时 | TC-COURSE-001 ~ TC-LEARN-006 |
| AI 对话 | 流式输出/逐字显示/错误处理 | TC-AI-001 ~ TC-AI-015 |
| 进度 | 首页统计联动/进度持久化 | TC-LEARN-007 ~ TC-LEARN-010 |

### 16.3 测试结果记录模板

| 用例编号 | 执行日期 | 执行人 | 结果 | 备注 |
|----------|----------|--------|------|------|
| TC-XXX-NNN | YYYY-MM-DD | XXX | Pass/Fail/Blocked | 问题描述 |

---

## 17 风险和注意事项

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| DeepSeek API 不稳定 | AI 对话和出题功能不可用 | 测试 fallback 降级逻辑，使用 mock 数据 |
| Docker 资源不足 | 构建失败或服务启动慢 | 确保至少 16GB 内存，清理无用镜像 |
| 测试数据污染 | 测试间相互影响 | 每轮测试前重置数据库或使用独立测试用户 |
| SSE 流式测试复杂 | 难以验证流式内容完整性 | 使用 curl 或 PowerShell 逐行解析 SSE 输出 |
| Redis 不可用 | 速率限制失效 | 验证降级逻辑，不影响核心功能 |

---

## 附录 A：API 端点快速验证命令

### 注册
```powershell
$body = '{"username":"testuser","password":"123456","email":"test@example.com","nickname":"测试","age":10}'
Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/auth/register' -Method POST -ContentType 'application/json' -Body $body
```

### 登录
```powershell
$body = '{"username":"test@example.com","password":"123456"}'
Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/auth/login' -Method POST -ContentType 'application/json' -Body $body
```

### 获取用户信息（替换 TOKEN）
```powershell
$h = @{'Authorization'='Bearer TOKEN'}
Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/users/me' -Headers $h
```

### 获取学习统计
```powershell
$h = @{'Authorization'='Bearer TOKEN'}
Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/users/me/stats' -Headers $h
```

### 课程列表
```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/courses?page=1&page_size=5'
```

### AI 对话（SSE 流式）
```powershell
$body = '{"message":"你好","conversationHistory":[]}'
Invoke-WebRequest -Uri 'http://localhost:8000/api/v1/ai/chat' -Method POST -ContentType 'application/json' -Body $body -Headers @{'Authorization'='Bearer TOKEN'}
```

### 健康检查
```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/health'
```

---

## 附录 B：数据库验证查询

### 查看所有用户
```sql
SELECT id, email, nickname, total_score, streak_days, created_at FROM users WHERE deleted_at IS NULL;
```

### 查看用户课程进度
```sql
SELECT uc.user_id, u.nickname, c.title, uc.progress, uc.completed_lessons, uc.status
FROM user_courses uc
JOIN users u ON uc.user_id = u.id
JOIN courses c ON uc.course_id = c.id;
```

### 查看课时完成记录
```sql
SELECT ul.user_id, u.nickname, l.title, c.title as course_title, ul.completed, ul.time_spent_seconds
FROM user_lessons ul
JOIN users u ON ul.user_id = u.id
JOIN lessons l ON ul.lesson_id = l.id
JOIN courses c ON ul.course_id = c.id;
```

### 查看聊天记录
```sql
SELECT cm.user_id, u.nickname, cm.role, LEFT(cm.content, 50) as content_preview, cm.created_at
FROM chat_messages cm
LEFT JOIN users u ON cm.user_id = u.id
ORDER BY cm.created_at DESC LIMIT 20;
```

### 查看成就解锁
```sql
SELECT ua.user_id, u.nickname, a.name, a.code, ua.achieved_at
FROM user_achievements ua
JOIN users u ON ua.user_id = u.id
JOIN achievements a ON ua.achievement_id = a.id;
```
