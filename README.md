# AI 智能学习平台 (AI-Learn v0.1)

> 面向 6-18 岁学习者的 AI 自适应学习平台

## 项目简介

AI 智能学习平台是一个基于人工智能的自适应学习系统，专为 6-18 岁不同年龄段的学习者设计。平台通过 AI 驱动的个性化推荐、自适应难度调整和丰富的互动内容，为每位学习者提供量身定制的学习路径。

**核心特性：**

- 分龄适配：4 个年龄分级（6-9 / 10-12 / 13-15 / 16-18），自动匹配适龄内容和界面主题
- AI 自适应：基于学习者行为模型，智能推荐知识点、调整难度和生成个性化题目
- 多学科覆盖：数学、语文、英语、科学、历史、编程、艺术等 7 大学科
- 游戏化学习：成就系统、积分奖励、连续学习打卡，激发学习动力
- 多端适配：响应式设计，支持 PC、平板和手机访问

## 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| **前端** | Next.js 14 + TypeScript + TailwindCSS | React 框架，SSR 支持，组件化开发 |
| **UI 组件** | Radix UI + Framer Motion + Lucide Icons | 无障碍组件库，流畅动画，图标系统 |
| **状态管理** | Zustand | 轻量级 React 状态管理 |
| **后端** | FastAPI + Python 3.12 | 高性能异步 Web 框架 |
| **数据库** | PostgreSQL 16 | 关系型数据库，JSONB 灵活字段 |
| **缓存** | Redis 7 | 会话缓存，速率限制，滑动窗口 |
| **ORM** | SQLAlchemy 2.0 (async) | 异步数据库访问 |
| **数据库迁移** | Alembic | 版本化数据库 Schema 管理 |
| **认证** | JWT (PyJWT + bcrypt) | 无状态令牌认证 |
| **AI 服务** | OpenAI API / 兼容接口 | 题目生成、内容审核、学习总结 |
| **反向代理** | Nginx 1.25 | 负载均衡、SSL 终结、静态缓存 |
| **容器化** | Docker + Docker Compose | 一键部署，环境隔离 |

## 项目结构

```
ai-learn/
├── docker-compose.yml           # Docker 服务编排
├── README.md                    # 项目说明文档
├── backend/                     # 后端服务
│   ├── Dockerfile               # 后端 Docker 镜像
│   ├── init-db.sql              # PostgreSQL 初始化脚本
│   ├── seed_data.py             # 种子数据脚本
│   ├── requirements.txt         # Python 依赖
│   ├── alembic.ini              # 数据库迁移配置
│   ├── .env.example             # 环境变量示例
│   ├── run.py                   # 本地启动脚本
│   ├── alembic/                 # 数据库迁移文件
│   └── app/                     # 应用核心代码
│       ├── main.py              # FastAPI 入口
│       ├── core/                # 核心模块（配置、数据库、Redis、安全）
│       ├── models/              # 数据模型（SQLAlchemy）
│       ├── schemas/             # Pydantic 数据校验
│       ├── api/v1/              # API 路由
│       ├── services/            # 业务逻辑层
│       └── ai/                  # AI 服务（Agent、提示词、工具）
├── frontend/                    # 前端服务
│   ├── Dockerfile               # 前端 Docker 镜像（多阶段构建）
│   ├── package.json             # Node.js 依赖
│   ├── next.config.js           # Next.js 配置
│   ├── tailwind.config.ts       # TailwindCSS 配置
│   └── src/                     # 源代码
│       ├── app/                 # 页面路由
│       ├── components/          # 组件（UI、布局、通用）
│       ├── lib/                 # 工具库
│       ├── stores/              # 状态管理
│       └── types/               # TypeScript 类型定义
├── nginx/                       # Nginx 配置
│   ├── nginx.conf               # 反向代理配置
│   └── ssl/                     # SSL 证书（生产环境放置）
└── design_imgs/                  # UI 设计参考图
```

## 快速开始

### 方式一：Docker 一键启动（推荐）

**前置要求：**
- Docker 20.10+
- Docker Compose V2+

**启动步骤：**

```bash
# 1. 克隆项目
git clone <repository-url>
cd ai-learn

# 2. 复制并配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，至少修改以下配置：
#   - DATABASE_URL（默认 Docker 环境已配置，无需修改）
#   - JWT_SECRET_KEY（生产环境务必修改）
#   - OPENAI_API_KEY（如需使用 AI 功能）

# 3. 一键启动所有服务
docker compose up -d --build

# 4. 查看服务状态
docker compose ps

# 5. 初始化数据库表结构
docker compose exec backend alembic upgrade head

# 6. 导入种子数据
docker compose exec backend python seed_data.py

# 7. 访问服务
#   前端:     http://localhost
#   后端 API: http://localhost/api
#   API 文档: http://localhost:8000/docs
```

**停止服务：**

```bash
docker compose down        # 停止并删除容器
docker compose down -v     # 同时删除数据卷（慎用！）
```

### 方式二：开发环境启动

**前置要求：**
- Python 3.12+
- Node.js 18+
- PostgreSQL 16+
- Redis 7+

**后端启动：**

```bash
cd backend

# 1. 创建虚拟环境
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 配置本地数据库和 Redis 连接

# 4. 数据库迁移
alembic upgrade head

# 5. 导入种子数据（可选）
python seed_data.py

# 6. 启动开发服务器
python run.py
# 服务运行在 http://localhost:8000
```

**前端启动：**

```bash
cd frontend

# 1. 安装依赖
npm install

# 2. 启动开发服务器
npm run dev
# 服务运行在 http://localhost:3000
```

## 环境变量说明

核心环境变量及其用途（详见 `backend/.env.example`）：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `APP_NAME` | 应用名称 | 智慧学习平台 API |
| `APP_VERSION` | 应用版本 | 0.1.0 |
| `DEBUG` | 调试模式 | false |
| `DATABASE_URL` | PostgreSQL 连接字符串 | postgresql+asyncpg://postgres:postgres@localhost:5432/learning_platform |
| `DATABASE_POOL_SIZE` | 数据库连接池大小 | 10 |
| `REDIS_URL` | Redis 连接字符串 | redis://localhost:6379/0 |
| `JWT_SECRET_KEY` | JWT 签名密钥（生产环境必须修改） | your-super-secret-key-change-in-production |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 有效期（分钟） | 30 |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh Token 有效期（天） | 7 |
| `CORS_ORIGINS` | 允许的跨域来源 | ["http://localhost:3000"] |
| `RATE_LIMIT_PER_MINUTE` | 每分钟请求次数限制 | 60 |
| `OPENAI_API_KEY` | OpenAI API 密钥 | （空） |
| `OPENAI_BASE_URL` | OpenAI API 基础 URL | https://api.openai.com/v1 |
| `AI_MODEL_NAME` | AI 模型名称 | gpt-4o-mini |

## API 文档

服务启动后，访问以下地址查看自动生成的 API 文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

**主要 API 模块：**

| 模块 | 路径前缀 | 说明 |
|------|----------|------|
| 认证 | `/api/v1/auth` | 注册、登录、Token 刷新 |
| 用户 | `/api/v1/users` | 用户信息、行为模型 |
| 内容 | `/api/v1/content` | 知识点、学科、年龄分级 |
| 学习 | `/api/v1/learning` | 学习会话、答题 |
| 题目 | `/api/v1/questions` | 题库查询 |
| 进度 | `/api/v1/progress` | 学习进度统计 |
| 成就 | `/api/v1/achievement` | 成就系统 |
| AI | `/api/v1/ai` | AI 对话、流式生成、题目生成 |

## 部署说明

### 生产环境部署清单

1. **环境配置**
   - 修改 `backend/.env` 中的所有敏感配置（JWT 密钥、数据库密码等）
   - 设置 `DEBUG=false`
   - 配置真实的 OpenAI API Key

2. **SSL 证书**
   - 将 SSL 证书放置在 `nginx/ssl/` 目录下
   - 取消 `nginx/nginx.conf` 中 HTTPS server 配置的注释
   - 配置 HTTP -> HTTPS 重定向

3. **数据持久化**
   - Docker Compose 已配置命名卷（`postgres_data`、`redis_data`）
   - 数据在容器重建后自动保留

4. **健康检查**
   - 后端：`GET /health` 返回服务状态
   - Nginx：`GET /health` 返回 nginx 状态
   - 所有服务配置了 Docker 原生 healthcheck

5. **日志查看**
   ```bash
   docker compose logs -f backend    # 查看后端日志
   docker compose logs -f frontend   # 查看前端日志
   docker compose logs -f nginx      # 查看 Nginx 访问日志
   ```

### 性能参考

| 服务 | 镜像大小（约） | 内存占用（约） |
|------|----------------|----------------|
| PostgreSQL 16 | 230 MB | 200-500 MB |
| Redis 7 | 40 MB | 50-256 MB |
| Backend | 180 MB | 200-400 MB |
| Frontend | 150 MB | 100-200 MB |
| Nginx | 25 MB | 10-20 MB |

## 测试账号

种子数据脚本会自动创建测试用户：

- **邮箱**: test@ai-learn.com
- **密码**: test123456

## 许可证

MIT License
