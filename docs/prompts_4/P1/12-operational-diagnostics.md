# P1-12：运行诊断与 AI Run（Operational Diagnostics / AI Run）

将本文件完整交给编码 AI 执行。先调查实际链路，遵守全局脱敏和两层 AI Agent 约束。

## 任务定位

- 本任务同时受 [全局执行规则](../00-global-execution-rules.md) 约束；如与本任务具体要求冲突，以全局规则为准。

- 优先级 P1；风险中高（AI 失败不可定位）。建立 Operational Run：request ID、run ID、HarnessRun、ToolCallLog 与 provider 阶段日志/指标可关联，且默认脱敏。
- 非目标：不引入复杂分布式追踪平台，不记录 prompt、令牌或用户私密内容，不改变出题 Agent + 审题 Agent 两层。

## 当前证据

- Finding 12 的候选为 `middlewares/request_logging.py`、`main.py:106-126`、`models/ai_generated.py:253-386`、`ai/provider.py`。问题：报告指出 request ID、HarnessRun、ToolCallLog 与 provider 日志可能未贯穿，部分观测模型可能未接线；影响：一次 AI 失败可能需跨多处猜测，缺少阶段耗时、token、成本和错误分类。
- 建议边界：报告建议以统一 run ID 串联结构化日志、指标、脱敏错误和阶段状态，形成 Operational Run；预期收益：一次查询即可定位完整链路并集中诊断知识。候选文件、行号、调用顺序和结论均须在当前代码中重验，建议不得视为已实施。

## 开始前调查

1. 追踪 HTTP 请求至 AI provider、生成任务和持久化的调用链，盘点当前 trace/request/run 字段、日志格式、指标和保留策略。
2. 设计 run 生命周期、父子关联、阶段枚举、采样、失败分类及 redaction 规则；区分可记录的元数据和禁止记录的内容。
3. 检查与 P1-13 的作业 ID、P1-10 的消耗账本是否可关联而不重复定义身份。

## 允许修改范围

- 可修改中间件、AI 服务/provider Adapter、观测模型/迁移、结构化日志、指标和测试；数据库操作须核验 host/database/environment、备份并隔离验证迁移/回滚。
- 可新增窄接口的诊断 Adapter，不修改无关业务或将日志系统耦合进前端状态。

## 禁止操作

- 禁止把日志当数据转储、记录 API key、认证头、完整 prompt/回复、真实邮箱或连接串；禁止用随机不可关联 ID 代替传播。
- 禁止吞掉 provider 异常、伪造成功或将内部 run 详情返回终端用户。

## 分阶段执行

1. 调查现有观测和数据保留；2. 设计 run 状态机/字段与脱敏策略；3. 先写关联、redaction、失败分类测试；4. 最小接线所有 AI 阶段；5. 用一次成功和一次受控失败端到端验收。

## 跨模块耦合检查

- 核验请求中间件、异步作业、provider、预算、数据库 ORM/Schema/DTO、日志采集和环境配置；不同服务传递同一关联上下文。
- 诊断模型迁移不得影响业务主库/题库路由；对外 API 如暴露状态，必须只给授权后的安全摘要。

## 错误处理要求

- 用户只收到纯文本可行动错误和安全错误码；对象异常取 `message`，不返回 JSON 对象字符串、堆栈、SQL 或 provider 原文。
- 结构化日志带 request/run/job ID、阶段、耗时、token/成本数值和分类，所有敏感字段 redaction；失败状态可重试或终止均可辨识。

## 验收标准

- 真实或受控集成流程证明单个 run 可从 HTTP 到 provider、预算、持久化和响应全程关联；并发 run 不串号。
- 覆盖 provider 超时、限流、解析失败、取消与数据库失败；日志/指标中存在阶段耗时和分类，且扫描确认无 token、密钥、认证头、prompt 或用户隐私泄露。
- 观测表（如有）在独立测试库完成 upgrade/downgrade 或恢复演练；测试、健康、日志和 `git diff --check` 通过。

## 最终报告格式

报告状态、文件与 run 数据模型、Finding 12 复核、关联样例（脱敏）、测试/迁移/构建/日志/健康/Git 结果、数据库目标和回滚证据、提交 SHA、采样和保留风险及人工配置步骤。
