# PostgreSQL 备份与恢复运行手册

## 目标与边界

本手册定义 AI-Learn 应用数据库的备份 Adapter 和隔离恢复演练。当前实现覆盖每个 PostgreSQL 数据库的逻辑备份，不替代云平台快照、WAL/PITR、数据库角色或基础设施配置备份。

当前数据资产：

| 数据库 | 当前用途 | 故障域 |
| --- | --- | --- |
| `learning_platform` | 用户、课程、学习过程与生成任务 | `ai-learn_postgres_data` |
| `ai_learn` | 管理后台题库与内容读取 | 与主库相同的 PostgreSQL 实例和 named volume |

题库的最终数据库边界由 P0-06 统一；新增数据库后必须逐库创建独立备份、清单、校验和与恢复演练，禁止用 A 库备份覆盖 B 库。

本工具明确不做以下操作：

- 不删除数据库、volume 或备份；保留策略仅输出 dry-run 候选。
- 不恢复到生产环境或已有 Schema 的数据库。
- 不把 Docker named volume 当成备份。
- 不在命令、日志、清单或 CI 制品中保存密码和加密密钥。

## 初始服务目标

生产负责人确认实际业务、容量和合规要求前，采用以下保守假设：

- RPO：24 小时；每个应用数据库至少每日一次逻辑备份。
- RTO：30 分钟；恢复到预建 PostgreSQL 16 环境并完成关键查询验证。
- 在线保留：35 天；任何实际删除必须经过独立审批，当前工具不执行删除。
- 恢复演练：至少每月一次，并在 Schema 迁移、PostgreSQL 大版本或备份工具变更后追加一次。
- 告警：备份、SHA-256、副本复制、解密、归档检查、恢复或业务指纹任一步失败均以非零退出码阻断，并由调度/CI 将日志发送给值班负责人。

## 加密、密钥与副本

- 备份格式为 PostgreSQL custom archive，经 AES-256-GCM 认证加密；密钥文件必须恰好 32 字节。
- 密钥必须来自组织批准的 Secret Manager/KMS 挂载，只读提供给一次性备份容器；不得与备份存放在同一位置。
- 主备份和副本均生成 SHA-256 并在复制后复验。
- 生产备份要求副本目录位于不同存储设备；同设备仅可用 `--allow-same-device-rehearsal` 在 local/ci 演练，清单会标记 `rehearsal_only=true`。
- 生产异地目标、对象锁、访问策略、生命周期和凭据必须由授权人员配置。未配置前，本地副本只能证明流程，不构成异地灾备。

## 本地/CI 恢复演练

统一命令：

```text
python scripts/run_backup_restore_drill.py
```

演练固定核验并显示：

- 源：`postgres-test / learning_platform_test / local|ci`。
- 目标：`postgres-restore / learning_platform_restore / local|ci`。
- 两者均为独立 Compose 服务、tmpfs 数据目录、无宿主机端口。

流程：

1. 强制重建两个可丢弃容器并写入两条合成记录、主键和唯一约束。
2. 真实运行 PostgreSQL 16 `pg_dump --format=custom`。
3. AES-256-GCM 加密，计算 SHA-256，复制副本并复验。
4. 解密并用 `pg_restore --list` 检查归档。
5. 构造损坏副本，证明校验和失败会停止；尝试非 `_restore` 目标，证明安全保护会停止。
6. 确认恢复目标为空后真实运行 `pg_restore --exit-on-error`。
7. 对比源库恢复前后和目标库的行数、唯一值、主键/唯一约束指纹。
8. 运行 35 天保留策略 dry-run，不删除任何产物；停止两个可丢弃容器并删除临时密钥/密码文件。

证据位于 `test/acceptance/P0-04/`。加密的合成数据备份可上传为短期 CI 制品；`test/.runtime/P0-04/` 不得上传。

## 生产只读备份接入

生产源备份默认拒绝，只有批准变更窗口内才能向一次性 `backup-tool` 传入 `--allow-production-source-backup`。执行前必须逐项记录并复核：

1. `host`、`database`、`environment=production` 与资产清单一致。
2. 使用最小权限只读备份账号；密码从只读 secret 文件提供。
3. 32 字节加密密钥来自独立 Secret Manager/KMS 挂载。
4. `--backup-dir` 与 `--replica-dir` 位于不同设备，副本域名称对应已批准的异地目标。
5. 存储空间、RPO/RTO、对象锁、保留和告警负责人已确认。

生产恢复不由本工具执行。事故恢复必须先把备份恢复到新的 `_recovery` 数据库，完成 SHA-256、解密、`pg_restore --list`、Schema、行数、约束和业务查询验证，再由变更负责人批准流量切换。

## 保留、监控与失败处理

查看 35 天以前的候选但不删除：

```text
docker compose --profile delivery-test run --rm --no-deps backup-tool retention-plan --backup-dir /mounted/backup --keep-days 35
```

任何失败均应：

1. 停止后续恢复或删除动作，保留源库不变。
2. 记录阶段、关联 backup id、脱敏的 host/database/environment、退出码和校验结果。
3. 不输出连接串、密码、密钥、完整 SQL 或真实数据行。
4. 将失败的可丢弃恢复目标隔离；未获得明确授权不得清理真实数据库、volume 或备份。
5. 向数据库负责人和当班运维升级；校验和或 GCM 标签错误按备份损坏/篡改事件处理。

## 责任与待配置项

| 项目 | 责任人/系统 |
| --- | --- |
| RPO/RTO 与业务优先级批准 | 产品负责人 + 数据库负责人 |
| 备份只读账号与恢复审批 | 数据库负责人 |
| KMS/Secret Manager、密钥轮换 | 安全/平台负责人 |
| 异地对象存储、对象锁与生命周期 | 平台负责人 |
| 调度、监控、告警升级 | 运维值班负责人 |
| 月度恢复演练与证据复核 | 数据库负责人 + 应用负责人 |

上述生产项尚未获得本仓库会话对外部系统的配置授权；实现和本地/CI 演练不会擅自创建 bucket、密钥、账号、调度或删除策略。
