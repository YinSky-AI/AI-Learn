# Prompts 4 优化提示词包

本目录将 [项目优化汇总](../reviews/project-optimization-summary.html) 中的 21 项建议拆分为可逐项执行的实施任务。它是**实施待办包**：提示词已编写，并不代表功能已经实施，也不应被视为当前系统状态或验收结论。

## 使用方式

1. 先阅读 [全局执行规则](00-global-execution-rules.md) 和 [依赖驱动实施顺序](01-implementation-order.md)。
2. 每次只将一个任务提示词交给编码 Agent；不得将 21 项任务同时执行。
3. 任务执行时重新调查真实代码、测试、配置和 Git 状态，不以优化报告的候选文件或行号替代调查。
4. 完成一项后，按该任务和全局规则完成证据报告，再更新下列清单。

本包的范围与模板说明见 [提示词包设计](02-prompt-package-design.md)。它不直接授权修改业务代码、配置、数据库或基础设施。

## 任务导航

- [P0：优先修复](P0/)
- [P1：重要增强](P1/)
- [P2：后续优化](P2/)

## 执行进度

> 状态仅代表本提示词包中的任务是否已执行和验收，不代表任何功能天然存在。

### P0

- [x] [01 题目访问隔离](P0/01-question-access.md)
- [x] [02 访问控制](P0/02-access-control.md)
- [x] [03 管理变更保护](P0/03-administrative-change.md)
- [x] [04 备份与恢复](P0/04-backup-and-recovery.md)
- [x] [05 答题提交事务](P0/05-answer-submission-transaction.md)
- [ ] [06 学习维度与题库目录](P0/06-learning-dimensions-and-question-catalog.md)
- [x] [07 Schema 迁移](P0/07-schema-migration.md)
- [x] [08 交付验证](P0/08-delivery-verification.md)

### P1

- [ ] [09 账号主体](P1/09-account-principal.md)
- [ ] [10 流量保护与 AI 预算](P1/10-traffic-protection-and-ai-budget.md)
- [ ] [11 运行就绪](P1/11-runtime-readiness.md)
- [ ] [12 运行诊断](P1/12-operational-diagnostics.md)
- [ ] [13 生成任务](P1/13-generation-job.md)
- [ ] [14 练习会话](P1/14-practice-session.md)
- [ ] [15 导师对话](P1/15-tutor-conversation.md)
- [ ] [16 学习契约与旅程](P1/16-learning-contract-and-journey.md)
- [ ] [17 复习调度](P1/17-review-scheduler.md)

### P2

- [ ] [18 学习读模型](P2/18-learning-read-model.md)
- [ ] [19 管理后台](P2/19-admin-backoffice.md)
- [ ] [20 学生数据治理](P2/20-student-data-governance.md)
- [ ] [21 客户端可用性](P2/21-client-availability.md)
