# 双数据库 Schema 迁移运行手册

## 单一 Schema 来源

AI-Learn 的运行时、导入脚本和旧维护脚本都不再创建或修补表。Schema 只由以下两个互相独立的 Alembic root 演进：

| 目标别名 | 数据库用途 | 配置 | revision 目录 | 版本表 | 当前批准 head |
| --- | --- | --- | --- | --- | --- |
| `primary` | `learning_platform` 主业务库 | `backend/alembic-primary.ini` | `backend/migrations/primary/versions/` | `alembic_version_learning` | `lp_0002_owned_contract` |
| `question-bank` | `ai_learn` 外部题库 | `backend/alembic-question-bank.ini` | `backend/migrations/question_bank/versions/` | `alembic_version_catalog` | `catalog_0001_baseline` |

主业务 root 只能用于 `learning_platform*`，题库 root 只能用于 `ai_learn*`。两者没有共享 head、版本表或 metadata；禁止把一个 root 的 revision stamp/upgrade 到另一个数据库。

当前主业务库允许保留经调查确认但不由应用管理的 `apscheduler_jobs`、`sys_role_dept` 表，以及 `users.ruoyi_user_id` 历史列。除此之外，未版本化基线包含未知表或列时必须拒绝采用，不能通过放宽指纹绕过调查。

## 启动和导入边界

- `backend/run.py` 在创建 Uvicorn worker 前只读核验两个数据库，FastAPI lifespan 在每个 worker 启动时再次只读核验。
- `SCHEMA_VERSION_POLICY=strict` 是 CI、验收和已完成基线采用环境的要求；任一数据库缺少版本表或不在批准 head 时拒绝启动。
- `warn` 只用于当前尚未获准写入版本表的本地历史持久卷兼容期，不执行 `stamp`、`upgrade`、`ALTER` 或 `create_all`。它只放行 `current=None` 且完整 legacy contract 验证通过的未版本库；全新空库、结构漂移库以及任何已有但陈旧的 revision 都会拒绝启动。生产环境不得把 `warn` 当成长期策略。
- `migrate_questions.py` 复用主业务 ORM Table，并在任何查询或 DML 前要求 `primary` 为批准 head；它不定义表。
- `link_quiz_lessons.py` 只更新课时与知识点关联，复用同一 URL secret 配置并在查询/DML 前要求 `primary` 为批准 head；它不定义或修改 Schema。
- `migrate_gamification.py` 是无副作用停用入口，只提示使用安全迁移 Adapter。
- 管理后台题库统一复用 `app.core.database.AI_LearnAsyncSessionLocal`，避免旁路连接绕过双库启动检查。

## 安全 Adapter

所有 upgrade、downgrade、current、check 和基线采用必须通过：

```text
cd backend
python schema_admin.py <action> \
  --target <primary|question-bank> \
  --database-url-file /run/secrets/schema_database_url \
  --environment <local|ci|test|staging|production> \
  --expected-host <second-person-confirmed-host> \
  --expected-database <second-person-confirmed-database>
```

Adapter 只接受容器内绝对、非符号链接、非空单行 `--database-url-file`，明确拒绝 argv DSN；连接文件与任何直接 URL 参数不得同时出现。它会再次解析连接配置并核对实际 `current_database()`，但日志只显示 alias、host、database、environment 和 revision，不显示用户、密码或完整 DSN。自动迁移仅允许名称以 `_test`、`_restore` 或 `_recovery` 结尾的非生产数据库；真实环境部署必须经过单独审批和受控发布 Adapter。

普通数据库不是可丢弃目标，必须额外传入 `--allow-release` 和 `--approval-reference`。非空库的 upgrade、downgrade 或 adoption 还必须传入 `--backup-reference`；只有经过独立确认的真空库 upgrade 可以使用 `--confirm-empty-bootstrap` 走无历史数据的 bootstrap 分支。任何 flag 都不能替代第二人目标核验或真实证据。

示例（仅限 Compose tmpfs 演练）：

```text
python schema_admin.py upgrade --target primary --database-url-file /run/secrets/primary_database_url --environment local --expected-host postgres-test --expected-database learning_platform_test
python schema_admin.py downgrade --target primary --database-url-file /run/secrets/primary_database_url --environment local --expected-host postgres-test --expected-database learning_platform_test --revision lp_0001_legacy_baseline
```

只读检查仍需显式选择一个 root 和目标，两个数据库分别执行：

```text
python schema_admin.py check --target primary --database-url-file /run/secrets/primary_database_url --environment ci --expected-host <confirmed-host> --expected-database learning_platform_test
python schema_admin.py check --target question-bank --database-url-file /run/secrets/catalog_database_url --environment ci --expected-host <confirmed-host> --expected-database ai_learn_test
```

普通数据库的 `upgrade head` 推荐由 Make 入口转发安全参数。目标参数和两个布尔值缺失、或布尔值不是 `true|false`，都会非零失败：

```text
make migrate \
  target=primary \
  database_url_file=<absolute-host-secret-file> \
  environment=staging \
  expected_host=<second-person-confirmed-host> \
  expected_database=learning_platform \
  allow_release=true \
  approval_reference=CHG-1234 \
  backup_reference=BKP-5678 \
  confirm_empty_bootstrap=false
```

`allow_release=true` 时 `approval_reference` 必需；`confirm_empty_bootstrap=false` 时 `backup_reference` 也必需。真正空库显式设置 `confirm_empty_bootstrap=true` 时可以省略备份号，但 Make 只负责门禁，Adapter 仍会实查当前 revision 和用户表；数据库并非空库时会拒绝。题库必须以 `target=question-bank`、对应 URL secret 文件和 `expected_database=ai_learn` 单独执行。不得用一次命令隐式迁移两库。

降到 `base` 会删除受管理 Schema，只有可丢弃数据库并提供 `--allow-destructive-downgrade` 才可执行。除此之外，downgrade 只接受所选 root 的完整精确 revision ID；`head`、`heads`、缩写、符号和任何相对写法都被拒绝。普通 revision downgrade 仍必须先有已验证备份和隔离回滚演练。

## 全新 Compose 环境部署

Compose 不再把密码或完整 DSN 放入 environment、command 或容器 metadata。首次启动前，从受控密钥系统分别创建三个权限受限文件：PostgreSQL 密码、主业务 URL、题库 URL；不要把内容写进 shell 参数、Compose YAML 或 Git。把它们的绝对路径设置为 `POSTGRES_PASSWORD_SECRET_FILE`、`PRIMARY_DATABASE_URL_SECRET_FILE`、`CATALOG_DATABASE_URL_SECRET_FILE` 后再运行 `docker compose up -d --build`。缺少文件时应先停止并补齐，不得退回硬编码环境变量。

Compose 中有两个显式 profile 服务，不随普通 `up` 启动：`schema-bootstrap-primary` 固定处理 `postgres/learning_platform`，`schema-bootstrap-catalog` 固定处理 `postgres/ai_learn`。两者分别调用安全 Adapter，并为普通数据库传入 `--allow-release`、审批参考号和 `--confirm-empty-bootstrap`。Make 会先确保 PostgreSQL healthy，再以 `--no-deps` 运行 file-only Adapter；总目标按主业务库、题库的顺序调用：

```text
make schema-bootstrap approval_reference=CHG-LOCAL-BOOTSTRAP \
  postgres_password_file=<absolute-password-file> \
  primary_database_url_file=<absolute-primary-url-file> \
  catalog_database_url_file=<absolute-catalog-url-file>
```

没有 Make 时按相同顺序执行：

```text
docker compose --profile schema-bootstrap run --build --rm --no-deps \
  -e SCHEMA_BOOTSTRAP_APPROVAL_REFERENCE=CHG-LOCAL-BOOTSTRAP schema-bootstrap-primary
docker compose --profile schema-bootstrap run --build --rm --no-deps \
  -e SCHEMA_BOOTSTRAP_APPROVAL_REFERENCE=CHG-LOCAL-BOOTSTRAP schema-bootstrap-catalog
```

执行前确认这是新建、可丢弃的 Compose volume，并记录空 volume 基线。两个服务都不会接收 `--backup-reference`。Adapter 结构化读取当前 revision：已位于批准 head 的 `upgrade head` 是无写入的幂等成功；真空库执行首次 bootstrap；未版本化或 stale 的非空目标会被核心授权检查拒绝，防止把 bootstrap 当作历史库迁移捷径。

### 部分失败恢复

两个数据库没有跨库事务，必须把每个 root 的完成状态分别记入变更单。总目标先运行 primary；primary 失败时 catalog 不会开始。primary 已成功但 catalog 失败时，不得清库或重建 volume，修复失败原因后只继续 catalog：

```text
make schema-bootstrap-catalog approval_reference=CHG-LOCAL-BOOTSTRAP database_url_file=<absolute-catalog-url-file> postgres_password_file=<absolute-password-file>
```

若通过独立命令先完成 catalog 而 primary 待处理，则运行：

```text
make schema-bootstrap-primary approval_reference=CHG-LOCAL-BOOTSTRAP database_url_file=<absolute-primary-url-file> postgres_password_file=<absolute-password-file>
```

总目标也可重跑；已经位于批准 head 的服务只读确认后返回成功。若失败库包含未版本化或 stale 用户表，停止 bootstrap 并转入“历史库基线采用”，不得给它补虚假备份号、手工 stamp 或删除数据。只有两个独立服务均成功后，才能进入 strict 启动。

双库 bootstrap 成功后，用 `strict` 重新创建 backend，而不是沿用默认兼容策略：

```text
# POSIX shell
SCHEMA_VERSION_POLICY=strict docker compose up -d --build

# PowerShell
$env:SCHEMA_VERSION_POLICY="strict"; docker compose up -d --build
```

检查 `docker compose ps`、backend 日志中的两个批准 head、`/health` 与关键 API。后续重启或部署系统也必须继续注入 `SCHEMA_VERSION_POLICY=strict`。

## 普通环境受控发布

1. 记录并由第二人核对 host、database、environment、目标 alias 和变更单。
2. 为主业务库和题库分别生成 P0-04 AES-256-GCM 备份，校验 SHA-256，并在独立 `_recovery` 数据库完成真实恢复。
3. 在同版本 PostgreSQL 的独立 `_test` 或 `_recovery` 数据库对相应 root 演练 `upgrade head`；两个 root 都运行 `check`。
4. 核对版本表只有一个 head，表、列、主键、外键、唯一约束和关键查询均符合预期。
5. 在批准窗口分别执行两次带 `--allow-release`、审批和备份参考号的发布；禁止应用进程自动迁移。
6. 以 `strict` 启动应用，确认日志同时出现两个批准 revision，并验证 `/health` 和关键 API。

## 历史库基线采用

`adopt-baseline` 不是通用修复命令。它只适用于结构已经等同于已调查历史基线、但尚无 Alembic 版本表的数据库。

执行前必须：

1. 获得数据库负责人对精确 host/database/environment 和基线采用的书面授权。
2. 创建、校验并在独立 `_recovery` 数据库真实恢复 P0-04 加密备份。
3. 在恢复库核对所有受管理表、列类型、nullable、外部表/列白名单，以及主业务库的孤立知识点关联、重复用户成就和空管理员标记。
4. 先在恢复库执行带 `--allow-baseline-adoption` 的 adoption；它会验证指纹、stamp 到显式 baseline，再 upgrade 到批准 head。
5. 运行应用 strict 启动、健康检查和业务回归。恢复库通过后，方可在批准窗口对原目标重复。

任何未知表/列、缺列、类型/nullable 差异、无效关联、重复约束数据或已有版本表都会拒绝 stamp。不得手工插入版本号来跳过验证。

普通历史库执行 adoption 时，四类授权必须同时存在：

```text
python schema_admin.py adopt-baseline \
  --target primary \
  --database-url-file /run/secrets/schema_database_url \
  --environment staging \
  --expected-host <second-person-confirmed-host> \
  --expected-database learning_platform \
  --allow-release \
  --allow-baseline-adoption \
  --approval-reference CHG-1234 \
  --backup-reference BKP-5678
```

题库使用 `question-bank` root 另行 adoption。恢复演练通过不等于自动授权原目标；对原库仍需独立批准窗口。

## 创建 revision

当前 `schema_admin.py` 不支持 revision create，`make migrate-create` 因此始终返回非零，并明确说明没有创建文件。不得恢复单一默认 root 的 `alembic revision --autogenerate` 命令，也不得把成功 `echo` 当成完成。

在安全 Adapter 增加并测试 revision create 能力之前，只允许以下受 review 的双 root 流程：

1. 先声明唯一目标为 `primary` 或 `question-bank`，核对对应 metadata、配置、版本目录、版本表和当前 head；另一 root 必须保持不变。
2. 在隔离分支中手工编写单个 revision 文件：主业务库放入 `backend/migrations/primary/versions/`，题库放入 `backend/migrations/question_bank/versions/`；`down_revision` 必须精确连接本表列出的 head。
3. review upgrade/downgrade、数据兼容、不可逆点和回滚/恢复方案，不接受空 revision 或只验证源码字符串。
4. 对两个 root 分别运行 Alembic drift check，再运行 `make migration-safety-tests` 和 `make migration-drill`。隔离证据全部通过后，才可更新应用批准 head。

## 回滚与恢复

- `lp_0002_owned_contract` 可回滚到 `lp_0001_legacy_baseline`；演练会真实撤销并重新应用外键/唯一约束归一化。
- 两个 root 的 baseline 到 `base` 会删除全部受管理表，只能在 tmpfs 可丢弃目标验证；真实环境回滚到 baseline 之前的方案是使用已验证备份恢复到新的 `_recovery` 数据库，再经审批切换，而不是原地删表。
- migration 失败后立即停止，不对源库执行猜测性 SQL。保存脱敏阶段/revision/目标/耗时/关联备份 ID，恢复到独立目标复盘。
- 连接、SQL、堆栈、密码和真实数据行不得进入面向用户的诊断或 CI artifact。

## 本地与 CI 演练

```text
python scripts/run_schema_migration_drill.py
```

演练强制重建两个 tmpfs PostgreSQL 服务，并使用四个可丢弃数据库和两个普通命名空库 bootstrap 目标：

- `postgres-test/learning_platform_test`
- `postgres-test/ai_learn_test`
- `postgres-restore/learning_platform_restore`
- `postgres-restore/ai_learn_restore`
- `postgres-test/learning_platform_bootstrap`
- `postgres-test/ai_learn_bootstrap`

它真实验证：普通命名空库首次/重复 bootstrap、主库成功题库失败后的单库与总入口重试；两个可丢弃空库从零到各自 head；每个 revision 的 downgrade/upgrade；交叉 root 拒绝；strict 未版本/错版启动拒绝；未版本化历史基线指纹；未知表拒绝；P0-04 AES-256-GCM 备份、SHA-256、副本和独立 restore；源结构与数据不变；恢复库 adoption 后 head/表/约束一致；strict 双库应用启动和 `/health`；以及 Compose config、容器 metadata、argv、报告中不存在完整 DSN 或密码。

证据写入 `test/acceptance/P0-07/`；临时密钥和密码只存在于 `test/.runtime/P0-07/`，演练结束即删除，不得上传。本地 current-snapshot 模式还要求通过 `PERSISTENT_POSTGRES_PASSWORD_FILE` 指向受限的现有数据库密码文件，仅供 `pg_dump` 只读备份使用。演练不会对持久原库执行 bootstrap、stamp、upgrade 或其他写入。

CI 的 `python scripts/verify.py full` 是阻断式门禁：隔离后端测试会对 `primary` 与 `question-bank` 分别运行 `schema_admin.py check`，随后执行完整 P0-07 drill。GitHub Actions 的 `schema-migration-evidence` artifact 只收集 `drill-report.json` 与备份的 `*.manifest.json`/`*.sha256`，不收集临时密钥、密码或 `*.aibak` 归档正文；如果演练未到达产证阶段，artifact 步骤会给出缺失警告，原门禁仍保持失败。

## 发布检查单

- [ ] 两个目标的 host/database/environment 和 alias 已由第二人确认。
- [ ] 两库分别存在可解密、校验并已恢复的近期备份。
- [ ] revision 文件、ORM metadata、API/前端契约和导入脚本已复核。
- [ ] 空库 upgrade、现有基线 adoption、每 revision downgrade/upgrade 均在隔离环境通过。
- [ ] `strict` 错版会拒绝，正确双 head 可启动且健康。
- [ ] 未输出或提交 DSN、密码、密钥、SQL、堆栈和真实数据。
- [ ] 发布后版本表各只有一个批准 head，日志、健康和关键接口无新增错误。
