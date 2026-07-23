# P0 / P1 实施验收报告（基于代码与运行态）

> 验收日期：2026-07-22  
> 验收范围：`docs/prompts_4/P0`、`docs/prompts_4/P1` 对应的当前项目实现。  
> 验收方式：代码与迁移文件检查、后端/前端自动化测试、容器健康检查、内部浏览器实际访问及截图。  
> 本报告记录的是当前实现状态，不会因为提示词或文档标记而将未完成项目视为已完成。

## 一、结论摘要

P0/P1 尚未全部完成，不能按“全量验收通过”处理。

| 范围 | 通过 | 部分通过 | 未通过/未实现 | 结论 |
| --- | ---: | ---: | ---: | --- |
| P0 | 3 | 3 | 2 | 需先完成 P0-07、P0-08，补齐其余缺口 |
| P1 | 0 | 4 | 5 | 核心架构项尚未落地，不能宣称 P1 完成 |

已验证通过的 P0 项：P0-01 题目访问隔离、P0-02 管理端访问控制、P0-05 答题事务一致性。

最阻塞的事实是：`python scripts/verify.py full` 在第 8/11 步“多数据库 Schema 迁移演练”失败，因此全量交付门禁未通过；其后的 Docker 烟测和真实 Playwright 流程不会由该门禁继续执行。

## 二、全局验收证据

| 验收项 | 结果 | 证据 |
| --- | --- | --- |
| 快速质量门禁 | 通过 | `python scripts/verify.py fast`：前端 34 项测试、TypeScript 类型检查、Next 构建、交付脚本测试均通过。 |
| 后端测试 | 通过（有警告） | `python scripts/run_backend_tests.py -q`：175 passed，63 warnings。警告主要涉及 `datetime.utcnow` 弃用及异步取消调用。 |
| 备份恢复演练 | 通过（仅本地隔离环境） | `python scripts/run_backup_restore_drill.py`：源库/恢复库校验、错误校验和与不安全目标拒绝均通过。 |
| 全量质量门禁 | 未通过 | `python scripts/verify.py full`：第 8/11 步 Schema 迁移演练失败，错误为“约束破坏基线虽被拒绝，但诊断不清晰”。 |
| 容器健康 | 通过 | 最终 Compose 状态中 `backend`、`frontend`、`nginx-gateway`、`postgres`、`redis` 均为 Up/healthy；`/health` 返回 HTTP 200。 |
| 差异格式检查 | 通过 | `git diff --check` 无输出。 |

## 三、P0 验收明细

| 编号 | 状态 | 已落实到的实现 | 未满足项 / 判定依据 |
| --- | --- | --- | --- |
| P0-01 题目访问隔离 | 通过 | `backend/app/services/question_access.py` 提供公开题目、答后反馈、管理员完整题目三种视图；`backend/app/api/v1/content.py` 的公开接口使用受限 DTO；`backend/tests/test_question_access_api.py` 覆盖正确答案与解析不泄漏。实际访问 `/api/v1/content/questions` 未返回 `correct_answer` 或 `explanation`。 | 当前范围内通过。 |
| P0-02 管理端访问控制 | 通过（核心） | `backend/app/services/admin_auth.py`、`backend/app/middlewares/admin_access.py`；`backend/tests/test_admin_access_control.py` 覆盖签名会话、登出失效、写操作 CSRF、登录 CSRF。内部浏览器访问 `/admin` 会重定向至 `/admin/login`。 | 当前核心访问控制通过。 |
| P0-03 管理变更 | 部分通过 | `backend/app/services/admin_changes.py` 实现软删除、恢复及审计；`backend/tests/test_administrative_changes.py` 有对应验证。 | 仅允许 `soft_delete` 与 `restore`，缺少“授权、延迟、可审计”的物理清理（purge）路径。 |
| P0-04 备份与恢复 | 部分通过 | 本地隔离恢复演练通过。 | `test/acceptance/P0-04/drill-report.json` 中 `independent_device: false`、`production_offsite_verified: false`；尚不是异机/异故障域的可验证备份。 |
| P0-05 答题事务一致性 | 通过 | `backend/app/services/learning_service.py` 使用会话锁、事务顾问锁、用户行锁，并在同一事务写入错题本；`backend/tests/test_answer_submission_transaction.py` 覆盖并发和错题本写入失败回滚。 | 当前范围内通过。 |
| P0-06 学习维度与题库映射 | 部分通过 | `backend/app/domain/learning_dimensions.py` 有规范化映射；`backend/app/services/content_service.py` 通过 `_fetch_questions_from_ai_learn` 接入题库；`backend/app/core/database.py` 配置 `ai_learn_engine`。 | `backend/tests/test_learning_dimensions.py` 只覆盖少量函数，缺少多数据库真实夹具、适配器结果断言与前端语义回归。 |
| P0-07 Schema 迁移 | 未通过 | 已存在迁移与演练脚本。 | `test/acceptance/P0-07/drill-report.json` 仍记录旧版本 `lp_0003_admin_recovery`，而当前版本已为 `lp_0006_review_scheduler`；全量门禁中的迁移演练在 `scripts/run_schema_migration_drill.py` 的诊断清晰度断言处失败。 |
| P0-08 交付验证 | 未通过 | `frontend/e2e/delivery.spec.ts` 有登录键盘/可访问性、健康检查、PWA/离线三类用例。 | 全量门禁未通过；端到端用例尚未覆盖完整学习、AI 出题与管理端操作闭环。 |

## 四、P1 验收明细

| 编号 | 状态 | 已落实到的实现 | 未满足项 / 判定依据 |
| --- | --- | --- | --- |
| P1-09 账户主体 | 部分通过 | `backend/app/models/user.py` 已有 `credential_version`；`backend/app/core/deps.py` 校验版本；`backend/app/services/auth_service.py` 使用行锁轮换 Refresh Token；`backend/tests/test_auth.py` 覆盖凭据版本与单次刷新。 | 缺少明确账户状态模型与校验、账号安全审计、刷新令牌并发专项测试。 |
| P1-10 流量与 AI 预算 | 部分通过 | `backend/app/main.py` 有可信客户端识别、Redis 原子限流与突发保护；`backend/app/ai/provider.py` 有信号量、输入/输出上限。 | 缺少可持久化的按用户成本预算预占/结算、历史预算、多进程一致性和集成测试。 |
| P1-11 运行就绪性 | 部分通过 | `backend/app/main.py` 的 `/ready` 检查数据库与 Redis；`docker-compose.yml` 配置健康检查与服务依赖。 | 缺少数据库/Redis/Nginx 上游故障矩阵及完整验证。 |
| P1-12 运行诊断 | 部分通过 | `backend/app/core/observability.py` 与 `backend/app/main.py` 已传递 correlation/request/run ID；AI Provider 有关联日志。 | `HarnessRun`、`ToolCallLog` 虽有模型定义但未见实际写入链路；缺少失败矩阵、敏感信息扫描及持久化关联验证。 |
| P1-13 生成任务 | 未实现 | `generated_questions` 增加了部分任务相关字段，`question_generation_service.py` 有失败占位处理。 | 没有独立 `generation_jobs`、worker、租约、幂等、重试/恢复、终态保护；不满足生成任务架构要求。 |
| P1-14 练习会话 | 未实现 | `frontend/src/components/quiz/quiz-practice.tsx` 有组件内 `PracticeSessionState`。 | 错题练习页面独立实现，未形成统一会话状态机、适配器及测试。 |
| P1-15 导师对话 | 未实现 | `frontend/src/stores/learning-store.ts` 支持 JSON 和基础 SSE 读取，并保存本地聊天历史。 | 通过 `text.split` 处理 SSE，无法可靠处理跨 chunk 数据；无 `AbortController`、服务端持久化、统一协议及测试。 |
| P1-16 学习契约与旅程 | 未实现 | 前端存在 `journeyStatus` 与 API 映射函数。 | 映射仍大量使用 `any`，没有运行时 DTO 校验、契约边界或旅程状态的可靠分层。 |
| P1-17 复习调度器 | 未实现 | `backend/app/services/wrong_book_service.py` 有固定间隔 `(1,3,7,14,30)`，并有 `review_count`、`next_review_at` 字段和初始测试。 | 缺少可演进的调度模型、掌握度/版本/时区/并发处理；统计的 `need_review_today` 依据 `last_wrong_at`，与到期查询的 `next_review_at` 逻辑不一致。 |

## 五、浏览器与界面验收

已用内部浏览器进行实际访问，未发现新增浏览器控制台错误；操作结束后已解除桌面控制。

| 页面/流程 | 结果 | 备注 |
| --- | --- | --- |
| 首页与课程详情 | 可访问 | 课程详情页可打开，但发现“第 0 课时”的展示问题，建议修复数据或展示兜底。 |
| 管理端入口 | 可访问 | 未授权访问 `/admin` 正确进入 `/admin/login`。 |
| 管理端错误反馈 | 可访问 | 错误登录显示“用户名或密码错误”，未泄漏技术异常。 |
| 错题本访客态 | 可访问 | 显示“登录后查看错题本”。 |
| AI 出题页面 | 可访问 | 页面能展示双 Agent（出题 Agent + 审题 Agent）相关文案。 |

截图证据位于：`test/acceptance/current-p0-p1-audit/`

- `01-home-desktop.png`
- `02-course-desktop.png`
- `03-admin-login.png`
- `04-wrong-book-guest.png`
- `05-ai-questions.png`
- `06-login-error.png`

另发现管理端模板使用 `cdn.tailwindcss.com`，浏览器产生生产环境警告。建议将 Tailwind 改为项目内构建产物，避免生产依赖 CDN。

## 六、建议的修复与复验顺序

1. **先修复 P0-07、P0-08（最高优先级）**：让 `python scripts/verify.py full` 全部通过；修复迁移演练的诊断断言，更新演练基线，并补全真实关键业务 E2E。
2. **实现 P1-13 生成任务架构**：独立任务表、状态机、worker、租约、幂等、重试和恢复。
3. **统一 P1-14、P1-15、P1-16 前端状态与契约**：练习会话、导师对话、学习旅程共用明确的 DTO、状态机和错误处理边界。
4. **重做 P1-17 调度器**：以 `next_review_at` 作为单一到期真相，补充掌握度、时区、版本与并发测试。
5. **补强 P1-10、P1-12**：持久化成本预算、跨进程限额、诊断链路落库、敏感信息审查。
6. **补齐部分通过项**：P0-03 的延迟物理清理、P0-04 的异机备份、P0-06 的跨库契约测试，以及 P1-09/P1-11 的安全与故障矩阵。

## 七、复验标准

以下条件全部满足后，才可将 P0/P1 标记为整体通过：

1. `python scripts/verify.py full` 完整通过，不能跳过失败步骤。
2. 各 P0/P1 条目均有对应代码、迁移/配置（如适用）、自动化测试和验收证据。
3. Docker Compose 全部核心服务健康，`/health` 与 `/ready` 返回符合预期。
4. 内部浏览器完成关键用户路径，界面变更保留截图证据，控制台无新增错误。
5. 备份恢复达到实际定义的异机/异故障域目标，而不止本地隔离演练。

## 八、说明

- 本报告仅新增验收记录，不修改任何业务代码、配置、容器或数据库。
- 工作区如存在其他未提交变更，应视为独立变更；本报告不对其进行覆盖、删除或重置。
