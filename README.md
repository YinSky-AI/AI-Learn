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

复制后端环境变量模板并编辑：

```bash
cp backend/.env.example backend/.env
```

根据实际需要修改 `backend/.env` 中的数据库连接、JWT 密钥等配置。

### 3. 启动服务

使用 Docker Compose 一键启动所有服务：

```bash
docker-compose up -d
```

或使用 Make 命令：

```bash
make up
```

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
│   ├── alembic/            # 数据库迁移脚本
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
make migrate        # 执行数据库迁移
make migrate-create msg="描述"  # 创建新迁移
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

本项目使用 Alembic 管理数据库迁移。

### 执行迁移

将数据库升级到最新版本：

```bash
make migrate
```

或：

```bash
docker-compose exec backend alembic upgrade head
```

### 创建新迁移

修改模型后，自动生成迁移脚本：

```bash
make migrate-create msg="add_user_table"
```

或：

```bash
docker-compose exec backend alembic revision --autogenerate -m "add_user_table"
```

> 提示：生成迁移脚本后，请务必检查脚本内容，确认变更是否符合预期。

### 回滚迁移

```bash
docker-compose exec backend alembic downgrade -1
```

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
