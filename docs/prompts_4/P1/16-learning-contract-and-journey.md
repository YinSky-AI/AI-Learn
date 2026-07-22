# P1-16：学习契约与旅程（Learning Contract & Journey）

将本文件完整交给编码 AI 执行。前端验收必须在内部浏览器完成真实流程、console、响应式和截图。

## 任务定位

- 本任务同时受 [全局执行规则](../00-global-execution-rules.md) 约束；如与本任务具体要求冲突，以全局规则为准。

- 优先级 P1；风险中高（多 DTO/`any` 映射和巨大 store 导致状态歧义）。在传输 Seam 校验 DTO 并映射 canonical 学习模型，将 Learning Journey 与 AI/Practice 状态分离。
- 非目标：不在此任务重新设计练习状态机或聊天传输，不以本地 fallback/假数据掩盖接口失败。

## 当前证据

- Finding 16 候选为 `frontend/src/stores/learning-store.ts`、`components/learning/quiz-question-mapper.ts`、`types/index.ts`、`types/api.ts`、`app/(main)/learning/*`：课程/题目/反馈多形状与 `any`，store 混合目录、进度、对话、测验和 fallback，可能永久骨架。
- 建议以 Contract Adapter 统一 DTO 验证和领域形状，页面只消费明确 Journey 状态；逐项复核现有 API。

## 开始前调查

1. 阅读 API DTO、fetch client、types、store、所有学习页面、加载组件和测试；列出每个后端字段到 UI 的映射及 `any`/fallback 来源。
2. 定义传输校验失败、canonical 领域模型和 Journey 状态（loading/ready/empty/error/offline/retry），明确 PracticeSession/TutorConversation 的边界。
3. 若合同字段存在版本差异，拟定向后兼容转换和弃用路径，先确认产品可接受行为。

## 允许修改范围

- 可修改 DTO schema/validator、Contract Adapter、Journey store/selector、学习页面、类型和单元/集成/端到端测试；必要 API 变更需同步后端 DTO 与前端。
- 如触及数据库，先核验目标 host/database/environment，备份后在隔离库验证迁移/回滚；通常不应为前端重构修改 schema。

## 禁止操作

- 禁止继续传播 `any`、将验证放在页面各处、以空数组/本地 mock 伪装失败，或将对话/练习副作用重新塞入 Journey。
- 禁止暴露内部 validator/HTTP 对象、删除学习数据或做无关全局状态重构。

## 分阶段执行

1. 调查契约矩阵；2. 设计传输与领域边界/状态机；3. 先写 DTO 和状态测试；4. 最小替换一个适配层后迁移页面；5. 真实浏览器验收和回归。

## 跨模块耦合检查

- 检查后端 Schema/DTO、网关、API client、前端 types、缓存、路由、PracticeSession、TutorConversation 和 P0-01 题目字段边界；接口变化不可让 A 库 API 接错 B 库。
- 检查 loading/empty/error/offline 表达与 P2-21 未来可用性工作可组合、无重复真相源。

## 错误处理要求

- DTO 无效、网络失败、空数据和离线缓存必须可区分并显示用户可懂的纯文本/重试动作；不显示对象字符串、JSON、堆栈、SQL 或密钥。
- 记录脱敏 request/contract version 和错误分类；保留上次有效数据时显式标注缓存/过期状态。

## 验收标准

- 单元/集成测试覆盖有效/缺字段/类型错误 DTO、兼容映射、Journey loading→ready/empty/error/offline 转换，确认 `any` 映射被移除或有明确边界。
- 内部浏览器完成真实课程目录、课程详情和进度旅程；分别验证 loading、empty、服务错误、离线/重试，检查 Network、console、键盘和移动视口，保存截图路径。
- PracticeSession/TutorConversation 不因契约重整回归；构建、日志/健康、隔离迁移回滚（如适用）和 `git diff --check` 通过。

## 最终报告格式

报告状态、文件与 Contract/Journey 边界、Finding 16 复核、DTO/状态测试、内部浏览器/console/响应式/截图、接口兼容与数据库证据、构建/日志/健康/Git 结果、提交 SHA、残余兼容风险和人工步骤。
