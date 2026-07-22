# P0-07：Schema 迁移链（Schema Migration）

将本文件完整交给编码 AI 执行。该任务涉及数据库结构，必须先验证目标、完成备份并只在隔离可丢弃数据库试验。遵守 `AGENTS.md` 和全局规则；不得影响“出题 Agent + 审题 Agent”两层约束。

## 任务定位

- 优先级：P0；风险：极高（环境分叉、不可证明部署与回滚）。目标是建立单一可审计 Schema 演进路径（推荐 Alembic revision 链），让启动只检查/应用批准版本，数据导入脚本不再定义 Schema。
- 非目标：不在本任务重写所有模型或清理历史数据，不在未授权环境执行生产迁移，不把 `create_all` 的移除变成无迁移时的启动故障。

## 当前证据

- Finding 7 候选文件为 `backend/app/main.py:154-170`、`migrate_gamification.py`、`migrate_questions.py`、`init-db.sql`。Schema 疑似由启动 `create_all`、手写 `ALTER` 和零散脚本共同维护，缺少 revision 历史。
- 影响是环境分叉、部署顺序不可证明，无法可靠 upgrade/rollback。建议为 Alembic 版本链、启动仅检查版本、导入脚本不再定义 Schema；收益是单一 Schema Locality 和可重复部署。
- 必须重查模型元数据、每个数据库、现有 bootstrap/初始化脚本、启动路径、部署/CI、历史数据和当前实际 Schema。

## 开始前调查

1. 阅读数据库模型、Engine/Session、`main.py`、所有 migration/init/seed/导入脚本、compose、CI/Makefile、测试及 `git status`。
2. 全局搜索 `create_all`、`drop_all`、`ALTER`、`CREATE TABLE`、Alembic/revision、初始化 SQL 和启动钩子，形成当前 Schema 来源清单与依赖顺序。
3. 对每个操作先验证并记录 `host`、`database`、`environment`；先取得可恢复备份，只在独立可丢弃测试数据库做 upgrade/downgrade。生产 Schema、历史基线、停机窗口和破坏性转换须用户明确授权。

## 允许修改范围

- 可新增/修改迁移配置、revision、模型元数据接线、启动版本检查、初始化/导入脚本职责、测试和最小 CI/运行命令。
- 可保留受控 bootstrap 以支持全新环境，但其 Schema 来源必须是 revision 链；迁移必须具备可判定 rollback 或隔离恢复路径。
- 不删除历史数据、数据库、volume 或旧脚本，除非完成引用检查、备份、影响清单并取得明确授权。

## 禁止操作

- 禁止在未验证目标、唯一副本或生产环境试验 `upgrade`、`downgrade`、`DROP`、`create_all`/清库；禁止将 migration URL 或凭据硬编码/输出。
- 禁止仅生成空 revision 或仅通过源码字符串测试；禁止让启动静默修改未知版本 Schema。
- 禁止与 P0-04/P0-05/P0-06 并行编辑数据库连接、模型或共享 Schema 配置。

## 分阶段执行

1. 调查：复核所有 Schema 来源与实际数据库版本，确认前置 P0-04 已提供可验证备份/恢复能力或在明确隔离环境实施。
2. 设计：选择 revision 基线、命名规范、multi-database 策略、启动检查、upgrade/downgrade/恢复方案和脚本迁移边界；高风险基线先获授权。
3. 测试先行：为全新数据库、当前基线升级、每个 downgrade、版本不匹配启动拒绝和导入脚本无 Schema 副作用编写测试。
4. 最小实施：建立连续 revisions，迁移启动/导入职责；执行隔离库 upgrade/downgrade 并记录实际版本与结果。
5. 自主验收：从空库和现有快照恢复的数据库运行完整链路，检查应用启动、日志、健康、容器和回滚证据。

## 跨模块耦合检查

- 同步核对 ORM 模型、迁移、主库/题库 Engine、Session、连接串、启动、初始化/导入、API DTO、Docker/环境变量和 CI。
- 确认 P0-03 的可恢复状态、P0-05 的幂等/事务表和 P0-06 的维度/题库连接都有明确 revision 路径，且不会让 A 库 revision 应用于 B 库。
- 检查前端/API 契约的字段可用性、部署顺序、健康检查和未来阶段 9 消费者。

## 错误处理要求

- 版本冲突、目标不匹配、迁移失败或 downgrade 不安全时停止并给出清晰纯文本诊断，不显示连接串、SQL、堆栈、密钥或对象字符串。
- 记录脱敏的 revision、目标、阶段、耗时、关联 ID 和回滚状态；对象异常取 `message`。
- 失败时用已验证备份在隔离环境恢复或按审批回滚，绝不继续对源库执行猜测性修复。

## 验收标准

- 在独立空数据库运行从零到 head 的真实 upgrade，验证应用启动及关键表/约束；在代表当前基线的隔离数据库运行 upgrade，并记录 revision 一致。
- 对每个可逆 revision 运行真实 downgrade 再 upgrade；不可逆变更必须有明确、经批准的隔离恢复方案与备份证据。
- 启动不再依赖未版本化 `create_all`/零散 `ALTER` 定义 Schema，导入脚本不会暗中建表；版本不匹配有安全、可操作的失败信息。
- 通过迁移/集成测试、构建、日志/健康、容器、`git diff --check` 和 Git 范围审计，且报告包含目标验证与命令结果。

## 最终报告格式

依次报告状态与目标；修改文件、revision 基线和多库策略；Finding 7 复核；每个目标 host/database/environment 与备份证明；空库/基线 upgrade、downgrade/隔离恢复、启动、容器、日志和 Git 命令结果；截图路径（如有）；提交 SHA；残余不可逆风险和需授权的生产执行步骤。
