# P1-15：导师对话（TutorConversation）

将本文件完整交给编码 AI 执行。必须分离 JSON/SSE 传输 Adapter 与 TutorConversation 行为；UI 用内部浏览器真实验收、console、响应式和截图。

## 任务定位

- 本任务同时受 [全局执行规则](../00-global-execution-rules.md) 约束；如与本任务具体要求冲突，以全局规则为准。

- 优先级 P1；风险中高（双实现、流截断与伪成功污染历史）。建立单一会话行为，JSON/SSE 仅为传输 Adapter，支持缓冲、取消、持久化和明确 unavailable 状态。
- 非目标：不改变 tutor 教学内容策略、不以 fallback 回复掩盖故障，不重构无关学习 store。

## 当前证据

- Finding 15 候选为 `frontend/src/stores/learning-store.ts:403-588`、`components/ai/tutor-chat.tsx`、`types/api.ts`：两套聊天实现，失败被伪装成成功，SSE 半行未缓冲。
- 建议统一协议、历史、取消、持久化和 unavailable；先复核端点的 JSON/SSE 格式及后端错误契约。

## 开始前调查

1. 阅读聊天组件、store、API client、SSE parser、后端端点、持久化模型和现有测试；记录所有入口、角色/上下文与失败分支。
2. 定义 canonical 消息/会话模型、传输 Adapter 接口、流分帧缓冲、Abort/cancel、持久化时机、重连与 unavailable 语义。
3. 对接 P1-10 预算、P1-12 run ID；若服务端协议不稳定，先提出兼容策略。

## 允许修改范围

- 可修改聊天行为模块、JSON/SSE Adapter、类型、局部 store/组件、持久化调用和真实测试；后端协议变更同步 DTO 并保持兼容。
- 数据库变更前核验 host/database/environment、备份并在隔离库验证迁移升级/降级或恢复。

## 禁止操作

- 禁止第二套行为实现、将 transport 分支散布在 UI、丢弃半帧、取消后继续写入，或以假回复代替错误。
- 禁止记录/展示密钥、原始内部异常或其他用户历史；禁止以 mock SSE 取代真实浏览器验收。

## 分阶段执行

1. 复核两实现与协议；2. 设计 canonical 会话和 Adapter；3. 先写 JSON/SSE 等价、半帧、取消、失败测试；4. 最小替换消费者；5. 真实浏览器双协议验收。

## 跨模块耦合检查

- 核验 API DTO、鉴权、预算、诊断、持久化 ORM/迁移、前端类型、路由、离线状态和 provider 错误映射；传输变化不得改变业务行为。
- 与 P1-16 分离：Conversation 管消息生命周期，Learning Journey 管课程目录/进度。

## 错误处理要求

- unavailable、超限、取消、断流和持久化失败显示明确纯文本状态及重试/恢复动作，不能伪装普通导师回复；不暴露 JSON、堆栈、SQL、prompt 或密钥。
- 日志以脱敏 conversation/run/request ID、阶段和错误分类关联；失败不污染历史，重复持久化幂等。

## 验收标准

- 测试证明 JSON 与 SSE 产生同一 canonical 行为；SSE 分段/半行正确缓冲；取消中止网络和写入；成功持久化一次；失败不会写成功消息且显示 unavailable。
- 内部浏览器完成真实 JSON 与 SSE 对话、断流/取消/重试和已持久化历史流程，检查 console、Network、键盘、loading/empty/error/offline 和移动视口，保存截图。
- 预算/诊断关联、构建、日志/健康、隔离迁移回滚（如适用）和 `git diff --check` 通过。

## 最终报告格式

报告状态、文件与 canonical/Adapter 设计、Finding 15 复核、协议/取消/持久化测试、内部浏览器/console/响应式/截图、数据库与回滚证据、构建/日志/健康/Git 结果、提交 SHA、残余网络风险和人工步骤。
