# AI 学堂智能学习平台

基于 AI 的智能学习管理系统，支持个性化学习路径、智能题库生成、学习进度追踪等功能。

## 技术栈

| 层级       | 技术选型                                      |
| ---------- | --------------------------------------------- |
| 前端       | Next.js 14 + React + TypeScript + Tailwind CSS |
| 后端       | FastAPI + Python 3.11 + SQLAlchemy + Alembic  |
| 数据库     | PostgreSQL 16                                 |
| 缓存       | Redis 7                                       |
| 容器化     | Docker + Docker Compose                       |
| 反向代理   | Nginx                                         |

## 快速开始

### 1. 环境准备

确保已安装：
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- [Make](https://www.gnu.org/software/make/)（可选，用于快捷命令）

### 2. 配置环境变量

`backend/.env` 是可选的本地配置文件，仓库不提供需要复制的模板。需要覆盖非敏感默认值或配置本地 AI Provider 时可自行创建；该文件已被 Git 忽略，禁止提交真实密钥。Compose 的 PostgreSQL 密码及两个数据库 DSN 不写入 `.env`，统一使用下一节所述的文件型 secret 注入；非开发环境还必须替换默认 JWT 密钥。

### 3. 全新 Compose 首次启动

全新空 volume 不能直接启动应用。先通过显式 profile 将两个数据库分别迁移到批准 head：

先准备三个仅当前用户可读、UTF-8 无 BOM 的非空单行 secret 文件：PostgreSQL 密码、指向 `postgres/learning_platform` 的主库 DSN，以及使用同一密码并指向 `postgres/ai_learn` 的题库 DSN。以下路径均须替换为本机绝对路径：

```bash
make schema-bootstrap \
  approval_reference="CHG-LOCAL-BOOTSTRAP" \
  postgres_password_file="/secure/ai-learn/postgres_password" \
  primary_database_url_file="/secure/ai-learn/primary_database_url" \
  catalog_database_url_file="/secure/ai-learn/catalog_database_url"
```

总目标会先处理主业务库，再处理题库。没有 Make 时按同一顺序分别运行两个明确服务：

```bash
POSTGRES_PASSWORD_SECRET_FILE="/secure/ai-learn/postgres_password" \
docker compose up -d --wait postgres
POSTGRES_PASSWORD_SECRET_FILE="/secure/ai-learn/postgres_password" \
PRIMARY_DATABASE_URL_SECRET_FILE="/secure/ai-learn/primary_database_url" \
docker compose --profile schema-bootstrap run --build --rm \
  -e SCHEMA_BOOTSTRAP_APPROVAL_REFERENCE="CHG-LOCAL-BOOTSTRAP" schema-bootstrap-primary
POSTGRES_PASSWORD_SECRET_FILE="/secure/ai-learn/postgres_password" \
CATALOG_DATABASE_URL_SECRET_FILE="/secure/ai-learn/catalog_database_url" \
docker compose --profile schema-bootstrap run --build --rm \
  -e SCHEMA_BOOTSTRAP_APPROVAL_REFERENCE="CHG-LOCAL-BOOTSTRAP" schema-bootstrap-catalog
```

两个服务分别固定核验 `postgres/learning_platform` 与 `postgres/ai_learn`，并为普通数据库传入 `--allow-release`、审批号和 `--confirm-empty-bootstrap`。每个服务会先只读查询 current：已在批准 head 时成功退出且不重复写入；未版本化或 stale 的非空库由于没有备份证明会由安全 Adapter 拒绝，历史库必须走备份恢复与基线采用流程。

如果主业务库已成功而题库失败，不要清库；修复失败原因后只继续题库：

```bash
make schema-bootstrap-catalog \
  approval_reference="CHG-LOCAL-BOOTSTRAP" \
  postgres_password_file="/secure/ai-learn/postgres_password" \
  database_url_file="/secure/ai-learn/catalog_database_url"
```

反向的部分完成状态使用 `make schema-bootstrap-primary ... postgres_password_file=... database_url_file=...`。总目标也可安全重跑，因为已经位于批准 head 的单库只做只读确认；运维记录仍应明确哪个 root 已完成、哪个 root 待继续。

bootstrap 成功后，必须用 `strict` 重新创建并启动 backend：

```bash
# POSIX shell
POSTGRES_PASSWORD_SECRET_FILE="/secure/ai-learn/postgres_password" \
PRIMARY_DATABASE_URL_SECRET_FILE="/secure/ai-learn/primary_database_url" \
CATALOG_DATABASE_URL_SECRET_FILE="/secure/ai-learn/catalog_database_url" \
SCHEMA_VERSION_POLICY=strict docker compose up -d --build

# PowerShell
$env:POSTGRES_PASSWORD_SECRET_FILE="C:\secure\ai-learn\postgres_password"
$env:PRIMARY_DATABASE_URL_SECRET_FILE="C:\secure\ai-learn\primary_database_url"
$env:CATALOG_DATABASE_URL_SECRET_FILE="C:\secure\ai-learn\catalog_database_url"
$env:SCHEMA_VERSION_POLICY="strict"; docker compose up -d --build
```

Compose 默认仍保留 `warn`，仅用于当前尚未获准写入版本表的历史持久卷。`warn` 只读校验完整 legacy contract；全新空库会拒绝启动，不会以“健康但未迁移”的状态假绿。历史库不要运行 bootstrap，按[双数据库 Schema 迁移运行手册](docs/operations/schema-migrations.md)完成备份、恢复演练和 adoption。

### 4. 访问服务

| 服务         | 地址                     |
| ------------ | ------------------------ |
| 前端页面     | http://localhost:3000    |
| 后端 API     | http://localhost:8000    |
| API 文档     | http://localhost:8000/docs |
| 替代文档     | http://localhost:8000/redoc |

### 5. 初始化数据（可选）

首次启动后，可执行种子脚本初始化基础数据：

```bash
make seed
```

或手动执行：

```bash
docker-compose exec backend python seed_data.py
```

## 目录结构

```
.
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── ai/             # AI 相关模块（智能出题、反馈聚合等）
│   │   ├── api/            # API 路由
│   │   ├── core/           # 核心配置（数据库、Redis、安全等）
│   │   ├── models/         # SQLAlchemy 数据模型
│   │   ├── schemas/        # Pydantic 数据校验模型
│   │   └── services/       # 业务逻辑服务层
│   ├── migrations/         # primary 与 question-bank 两个独立 revision root
│   ├── alembic-primary.ini
│   ├── alembic-question-bank.ini
│   ├── Dockerfile
│   ├── requirements.txt
│   └── seed_data.py        # 种子数据脚本
├── frontend/               # Next.js 前端
│   ├── app/                # Next.js App Router
│   ├── public/             # 静态资源
│   ├── Dockerfile
│   └── next.config.js
├── nginx/                  # Nginx 配置文件
├── docker-compose.yml      # Docker Compose 编排文件
├── Makefile               # 常用命令快捷方式
└── README.md              # 项目说明（本文件）
```

## 常用命令

### Docker Compose 操作

```bash
# 构建所有镜像
docker-compose build

# 启动所有服务（后台）
docker-compose up -d

# 查看所有服务日志
docker-compose logs -f

# 查看指定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 停止并移除所有服务
docker-compose down
```

### Make 快捷命令

```bash
make help           # 查看所有可用命令
make build          # 构建镜像
make up             # 启动服务
make down           # 停止服务
make logs           # 查看日志
make backend-logs   # 查看后端日志
make frontend-logs  # 查看前端日志
make test           # 运行后端测试
make migrate        # 显式参数齐全后，通过安全 Adapter 执行单个 root 的 upgrade head
make migrate-create # 当前会非零拒绝；安全 Adapter 尚不支持 revision create
make schema-bootstrap approval_reference="CHG-..." postgres_password_file="..." primary_database_url_file="..." catalog_database_url_file="..." # 依次处理全新空 Compose 双库
make schema-bootstrap-primary approval_reference="CHG-..." postgres_password_file="..." database_url_file="..." # 单独继续主业务库
make schema-bootstrap-catalog approval_reference="CHG-..." postgres_password_file="..." database_url_file="..." # 单独继续题库
make seed           # 初始化种子数据
make fmt            # 格式化代码
make lint           # 代码检查
```

## 测试

运行后端单元测试：

```bash
make test
```

或手动执行：

```bash
docker-compose exec backend pytest -v
```

## 数据库迁移

Schema 只由两个互相隔离的 Alembic root 管理：

| 目标 | 配置 | 版本目录 | 版本表 | 批准 head |
| --- | --- | --- | --- | --- |
| `primary` | `backend/alembic-primary.ini` | `backend/migrations/primary/versions/` | `alembic_version_learning` | `lp_0002_owned_contract` |
| `question-bank` | `backend/alembic-question-bank.ini` | `backend/migrations/question_bank/versions/` | `alembic_version_catalog` | `catalog_0001_baseline` |

禁止使用隐式默认 root 的 `alembic upgrade head`。每个数据库必须独立核验和执行；普通数据库发布还必须提供审批与已验证备份。例如主业务库发布：

```bash
make migrate \
  target=primary \
  database_url_file='/secure/ai-learn/primary_database_url' \
  environment=staging \
  expected_host='<second-person-confirmed-host>' \
  expected_database=learning_platform \
  allow_release=true \
  approval_reference='CHG-1234' \
  backup_reference='BKP-5678' \
  confirm_empty_bootstrap=false
```

`make migrate` 固定执行所选 root 的 `upgrade head`。目标参数和两个布尔值缺一即非零失败；`allow_release=true` 时审批号必需，且 `confirm_empty_bootstrap=false` 时备份号必需。真正空库显式设置 `confirm_empty_bootstrap=true` 后可以省略 `backup_reference`，最终仍由 Adapter 实查空库；如果数据库非空，Adapter 会拒绝。普通执行不会回显连接串。题库发布必须另行执行，并把目标改为 `question-bank` / `ai_learn`。全新空 Compose 请优先使用前述拆分 bootstrap targets，不要把通用发布命令当作自动启动钩子。

`make migrate-create` 当前始终非零拒绝，因为安全 Adapter 尚未实现 revision create；它不会创建文件，也不会以成功提示冒充执行。创建 revision 时必须先选择一个 root，保持另一 root 不变，并按运维手册完成 review、双 root drift check、downgrade/upgrade 和隔离演练。

历史库 adoption、显式 downgrade、备份恢复和发布后 `strict` 检查的完整命令见[双数据库 Schema 迁移运行手册](docs/operations/schema-migrations.md)。

### CI 门禁与证据

```bash
python scripts/verify.py full
```

`full` 是本地与 GitHub Actions 共用的 15 步交付门禁，按顺序执行交付脚本单测、160 条方程诊断规则评测、前端测试/类型检查/生产构建、后端镜像与隔离测试、加密备份恢复、双数据库迁移、Compose 空库 bootstrap 与 strict 启动、Docker smoke 以及真实浏览器 E2E；任一步失败即返回非零退出码。

门禁会为当前运行创建临时随机的文件型 secret，并在结束后清理；也可显式传入 `POSTGRES_PASSWORD_SECRET_FILE`、`PRIMARY_DATABASE_URL_SECRET_FILE` 和 `CATALOG_DATABASE_URL_SECRET_FILE` 复用受控凭据。自动 bootstrap 只作用于门禁创建的可丢弃空数据库，不会采用或迁移现有的未版本化数据库。GitHub Actions 的 `schema-migration-evidence` artifact 只上传 `drill-report.json` 及备份 manifest/SHA-256 证据，不上传临时密钥、数据库密码或加密归档正文。

截至 2026-08-13，PR #4 已在 GitHub Actions clean runner 上完整通过该门禁（[Delivery verification #31675270726](https://github.com/YinSky-AI/AI-Learn/actions/runs/31675270726)），其中真实浏览器 E2E 为 12 项通过。该记录是当前分支的可复现交付证据，不代表生产环境效果或线上可用性承诺。

## 健康检查

各服务均配置了健康检查：

- **PostgreSQL**：`pg_isready` 检测
- **Redis**：`redis-cli ping` 检测
- **Backend**：HTTP `/health` 端点检测
- **Frontend**：HTTP `wget` 端口检测

可通过以下命令查看健康状态：

```bash
docker-compose ps
```

## 开发注意事项

1. **代码格式化**：后端使用 `black` 进行代码格式化，使用 `flake8` 进行代码检查。
2. **环境隔离**：开发时建议直接在后端目录使用虚拟环境安装依赖，前端使用 `npm install`。
3. **日志查看**：服务日志输出到 Docker 标准输出，可通过 `docker-compose logs` 查看。
4. **数据持久化**：PostgreSQL 和 Redis 数据通过 Docker Volume 持久化，执行 `docker-compose down -v` 会清除数据。

## License

MIT License
