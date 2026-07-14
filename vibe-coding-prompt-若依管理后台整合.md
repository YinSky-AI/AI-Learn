# Vibe Coding Prompt: 若依管理后台整合

> **用途**：将此提示词直接粘贴给 AI 编码助手（如 Cursor、Trae、GitHub Copilot Chat、Claude Code 等），助手将自主完成全部整合工作。
> **前提**：助手已具备项目根目录的文件读写权限。

---

## 系统角色设定

你是一个全栈开发专家，精通 Python/FastAPI、Vue3、PostgreSQL、Docker、Nginx。你的任务是严格按照以下分阶段指令，为 AI-Learn 智能学习平台整合 RuoYi-Vue3-FastAPI 管理后台。

**核心原则**：
- 每完成一个阶段，先验证再进入下一阶段
- 修改任何现有文件前，必须先读取当前内容
- 若依框架代码通过 git clone 获取，不手写
- 保持现有用户端系统零改动（业务前端不动）
- 所有新建文件放在项目根目录下的指定位置

**项目根目录**：`当前工作目录`（你正在操作的目录）

---

## 项目现有架构（只读，不要修改这些技术选型）

```
当前容器：
  - ai-learn-postgres (PostgreSQL 16, 端口 5432, 数据库名 learning_platform)
  - ai-learn-redis (Redis 7, 端口 6379)
  - ai-learn-backend (FastAPI, 端口 8000)
  - ai-learn-frontend (Next.js, 端口 3000)

现有目录：
  - backend/          FastAPI 后端（SQLAlchemy 2.0 异步, bcrypt 密码, HS256 JWT）
  - frontend/         Next.js 14 前端（不动）
  - nginx/            Nginx 配置
  - docker-compose.yml

现有 .env 关键变量：
  - DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/learning_platform
  - REDIS_URL=redis://redis:6379/0
  - JWT_SECRET_KEY=your-super-secret-key-change-in-production
  - JWT_ALGORITHM=HS256
  - CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://127.0.0.1:3000"]
```

---

## 阶段一：克隆若依源码

### 指令

1. 在项目根目录下克隆 RuoYi-Vue3-FastAPI 仓库：

```bash
git clone https://gitee.com/yao-zhen/RuoYi-Vue3-FastAPI.git _ruoyi-temp
```

2. 查看克隆下来的目录结构，确认后端和前端代码的位置。

3. 将后端代码复制到 `ruoyi-admin-backend/`：

```bash
# 根据实际目录结构调整，通常是：
cp -r _ruoyi-temp/ruoyi-fastapi-backend/* ruoyi-admin-backend/
```

4. 将前端代码复制到 `ruoyi-admin-frontend/`：

```bash
cp -r _ruoyi-temp/ruoyi-fastapi-frontend/* ruoyi-admin-frontend/
```

5. 删除临时目录：

```bash
rm -rf _ruoyi-temp
```

### 验证

- `ruoyi-admin-backend/` 目录下有 `requirements.txt` 和 `app/` 目录
- `ruoyi-admin-frontend/` 目录下有 `package.json` 和 `src/` 目录

---

## 阶段二：若依后端 PostgreSQL 适配

### 指令

1. 在 `ruoyi-admin-backend/` 中查找 SQL 初始化文件（通常在 `sql/` 目录），找到 PostgreSQL 版本的 SQL 文件。如果只有 MySQL 版本，需要将 MySQL SQL 转换为 PostgreSQL 语法：
   - `AUTO_INCREMENT` → `SERIAL` 或 `GENERATED ALWAYS AS IDENTITY`
   - `DATETIME` → `TIMESTAMP`
   - 反引号 `` ` `` → 双引号 `"` 或去掉
   - 去掉 `ENGINE=InnoDB` 等子句
   - `COMMENT` 语法适配

2. 将适配后的 SQL 文件保存为 `ruoyi-admin-backend/sql/ruoyi-pg.sql`。

3. 在 SQL 文件开头添加 schema 切换：

```sql
CREATE SCHEMA IF NOT EXISTS ruoyi;
SET search_path TO ruoyi;
```

4. 修改若依后端的数据库配置：
   - 找到若依后端的环境配置文件（`.env`、`.env.dev` 或 `config.py` 等）
   - 将数据库连接改为：`postgresql+asyncpg://postgres:postgres@postgres:5432/learning_platform`
   - 将 Redis 连接改为：`redis://redis:6379/1`（注意 db 编号为 1，与业务系统的 db 0 隔离）
   - 确保 JWT_SECRET_KEY 与业务后端一致：`your-super-secret-key-change-in-production`

5. 修改若依 SQLAlchemy 模型，让所有表使用 `ruoyi` schema：
   - 方式一（推荐）：在若依后端启动入口或数据库引擎初始化时执行 `SET search_path TO ruoyi, public`
   - 方式二：修改基类的 `MetaData(schema="ruoyi")`
   - 方式三：每个模型的 `__table_args__` 中添加 `schema="ruoyi"`

6. 检查若依后端的依赖文件 `requirements.txt`，确保包含：
   - `asyncpg`（PostgreSQL 异步驱动）
   - `psycopg2` 或 `psycopg2-binary`（同步驱动，若依可能需要）
   - 如有 MySQL 相关依赖（`pymysql` 等），替换为 PostgreSQL 对应依赖

### 验证

- SQL 文件语法正确，所有 `CREATE TABLE` 都在 ruoyi schema 下
- 若依后端配置文件中的 DATABASE_URL 指向 PostgreSQL，REDIS_URL 使用 db 1

---

## 阶段三：若依前端适配

### 指令

1. 在 `ruoyi-admin-frontend/` 中找到前端环境配置文件（通常为 `.env.production` 或 `.env.development`）。

2. 修改 API 基础路径：

```env
# 后端 API 通过 Nginx 代理，前缀为 /api/admin
VITE_APP_BASE_API = '/api/admin'
```

3. 修改前端路由 base（让管理后台挂载在 /admin 路径下）：
   - 在 `vite.config.js` 或 `vue.config.js` 中设置 `base: '/admin/'`
   - 在路由配置文件（通常 `src/router/index.js`）中确认路由是否支持 base path

4. 确认若依前端的 Axios 请求拦截器是否正确使用 `VITE_APP_BASE_API` 作为 baseURL。如果没有，需修改 `src/utils/request.js` 中的 baseURL 配置。

### 验证

- `npm run build:prod` 或 `npm run build` 能成功构建（先不执行，只需确认配置文件正确）
- 前端所有 API 请求会发送到 `/api/admin/...` 路径

---

## 阶段四：Nginx 网关配置

### 指令

修改项目根目录下的 `nginx/nginx.conf`，在现有配置基础上添加若依相关配置。

**现有配置要点**（不要改动）：
- upstream `frontend:3000`（Next.js 用户端）
- upstream `backend:8000`（FastAPI 业务 API）
- `location /api/v1/ai/stream` 有 SSE 特殊配置（proxy_buffering off）
- `location /api/v1/ws` 有 WebSocket 配置

**新增内容**：

1. 添加 upstream：

```nginx
upstream ruoyi_admin_fe {
    server ruoyi-admin-frontend:80;
    keepalive 32;
}

upstream ruoyi_admin_api {
    server ruoyi-admin-backend:8088;
    keepalive 32;
}
```

2. 添加 location 块（放在 `location /` 之前，避免被通配匹配拦截）：

```nginx
# ============ 若依管理后台前端 ============
location /admin {
    proxy_pass http://ruoyi_admin_fe;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# ============ 若依管理后台 API ============
location /api/admin/ {
    rewrite ^/api/admin/(.*) /$1 break;
    proxy_pass http://ruoyi_admin_api;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Connection "";
    proxy_connect_timeout 10s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
}
```

### 验证

- nginx.conf 语法正确（可用 `nginx -t` 验证）
- `/admin` 路径指向若依前端
- `/api/admin/` 路径经过 rewrite 后指向若依后端
- 现有业务路由不受影响

---

## 阶段五：Docker 配置

### 指令

1. 创建 `ruoyi-admin-backend/Dockerfile`：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8088

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8088"]
```

2. 创建 `ruoyi-admin-frontend/Dockerfile`（多阶段构建）：

```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build:prod

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# 若依前端需要 history 模式路由支持
RUN echo -e 'server {\n    listen 80;\n    location / {\n        root /usr/share/nginx/html;\n        index index.html;\n        try_files $uri $uri/ /index.html;\n    }\n}' > /etc/nginx/conf.d/default.conf
EXPOSE 80
```

3. 修改项目根目录的 `docker-compose.yml`，新增 3 个服务：

```yaml
  # 在现有 frontend 服务之后添加：

  # --- Nginx 统一网关 ---
  nginx-gateway:
    image: nginx:alpine
    container_name: ai-learn-nginx
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - frontend
      - backend
      - ruoyi-admin-frontend
      - ruoyi-admin-backend
    networks:
      - ai-learn-net

  # --- 若依管理后台后端 ---
  ruoyi-admin-backend:
    build:
      context: ./ruoyi-admin-backend
      dockerfile: Dockerfile
    container_name: ai-learn-ruoyi-api
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/learning_platform
      REDIS_URL: redis://redis:6379/1
      JWT_SECRET_KEY: your-super-secret-key-change-in-production
      JWT_ALGORITHM: HS256
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8088/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    networks:
      - ai-learn-net

  # --- 若依管理后台前端 ---
  ruoyi-admin-frontend:
    build:
      context: ./ruoyi-admin-frontend
      dockerfile: Dockerfile
    container_name: ai-learn-ruoyi-fe
    restart: unless-stopped
    networks:
      - ai-learn-net
```

**重要**：若依后端和前端容器不暴露宿主机端口，仅通过 Nginx 内部网络访问。

### 验证

- `docker-compose config` 验证配置语法正确
- 3 个新服务正确加入 `ai-learn-net` 网络
- 依赖关系正确：nginx-gateway 依赖所有服务，若依后端依赖 postgres 和 redis

---

## 阶段六：数据库初始化

### 指令

1. 修改 `backend/init-db.sql`，在末尾追加：

```sql
-- 若依管理后台 schema
CREATE SCHEMA IF NOT EXISTS ruoyi;
GRANT ALL ON SCHEMA ruoyi TO postgres;
```

2. 如果若依有独立的 SQL 初始化脚本（`ruoyi-admin-backend/sql/ruoyi-pg.sql`），需要将其挂载到 PostgreSQL 容器的初始化目录中。修改 `docker-compose.yml` 的 postgres 服务：

```yaml
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/init-db.sql:/docker-entrypoint-initdb.d/01-init-db.sql:ro
      - ./ruoyi-admin-backend/sql/ruoyi-pg.sql:/docker-entrypoint-initdb.d/02-ruoyi-init.sql:ro
```

3. **注意**：PostgreSQL 的 docker-entrypoint-initdb.d 只在数据库首次初始化时执行。如果数据库已存在，需要手动执行 SQL：

```bash
docker exec -i ai-learn-postgres psql -U postgres -d learning_platform -f /docker-entrypoint-initdb.d/02-ruoyi-init.sql
```

### 验证

- 连接 PostgreSQL 确认 `ruoyi` schema 存在：`\dn` 命令
- 确认若依系统表（sys_user, sys_role, sys_menu 等）在 ruoyi schema 下

---

## 阶段七：业务后端适配（最小改动）

### 指令

本阶段对现有业务后端做最小改动，添加管理后台关联支持。

1. **修改 `backend/app/models/user.py`**，在 User 模型末尾添加两个字段：

```python
    ruoyi_user_id = Column(Integer, nullable=True, unique=True,
                           comment="若依 sys_user 表的 user_id，用于关联管理后台")
    is_admin = Column(Boolean, default=False, server_default=text("false"),
                     comment="是否为管理员（同步自若依角色）")
```

注意：需要在文件头部确认 `Integer` 和 `Boolean` 以及 `text` 已导入。

2. **修改 `backend/app/core/config.py`**，在 CORS_ORIGINS 配置中添加管理后台地址：

在 Settings 类中，将 CORS_ORIGINS 默认值改为：

```python
CORS_ORIGINS: list = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://localhost/admin",       # 新增
    "http://localhost:80",          # 新增：Nginx 网关
]
```

3. **修改 `backend/.env.example`**，在 CORS_ORIGINS 中添加新地址。

### 验证

- User 模型包含 `ruoyi_user_id` 和 `is_admin` 字段
- CORS 配置包含管理后台来源地址

---

## 阶段八：构建与启动

### 指令

1. 停止现有容器（如果有运行中的）：

```bash
docker-compose down
```

2. 重新构建所有镜像：

```bash
docker-compose build
```

3. 启动所有服务：

```bash
docker-compose up -d
```

4. 查看所有容器状态：

```bash
docker-compose ps
docker-compose logs --tail=50
```

### 验证清单

按以下顺序逐项验证，遇到问题立即修复：

| # | 验证项 | 预期结果 | 验证命令 |
|---|--------|---------|---------|
| 1 | PostgreSQL 启动 | 容器 healthy | `docker-compose ps postgres` |
| 2 | Redis 启动 | 容器 healthy | `docker-compose ps redis` |
| 3 | 业务后端启动 | 容器 healthy，端口 8000 | `curl http://localhost:8000/health` |
| 4 | 用户端前端启动 | 容器 running，端口 3000 | 浏览器访问 `http://localhost:3000` |
| 5 | Nginx 启动 | 容器 running，端口 80 | `curl http://localhost/` 能返回用户端页面 |
| 6 | 若依后端启动 | 容器 healthy | 检查日志无报错 |
| 7 | 若依前端启动 | 容器 running | 检查日志无报错 |
| 8 | 管理后台页面 | 浏览器访问 `http://localhost/admin/` 显示若依登录页 |
| 9 | 管理后台登录 | 使用 admin / admin123 登录成功 |
| 10 | 用户端不受影响 | `http://localhost:3000` 正常，API 正常 |

### 如果验证失败的排查方向

- **若依后端启动失败**：查看 `docker-compose logs ruoyi-admin-backend`，检查数据库连接和 SQL 初始化
- **管理后台 404/502**：检查 Nginx 配置中的 upstream 名称是否与容器名匹配
- **管理后台登录失败**：确认 SQL 已执行，ruoyi.sys_user 表中有 admin 记录
- **用户端受影响**：检查 Nginx location 匹配顺序，确保 `/admin` 不拦截其他路径

---

## 阶段九：清理与收尾

### 指令

1. 确认所有服务正常运行后，检查是否有不需要的临时文件，清理干净。

2. 在项目根目录创建或更新 `Makefile`，添加管理后台相关快捷命令：

```makefile
# 管理后台相关
ruoyi-build:
	docker-compose build ruoyi-admin-backend ruoyi-admin-frontend

ruoyi-logs:
	docker-compose logs -f ruoyi-admin-backend ruoyi-admin-frontend

ruoyi-restart:
	docker-compose restart ruoyi-admin-backend ruoyi-admin-frontend
```

3. 验证最终目录结构：

```
项目根目录/
├── docker-compose.yml          ← 已修改（新增 3 个服务）
├── nginx/nginx.conf           ← 已修改（新增若依路由）
├── backend/
│   ├── init-db.sql           ← 已修改（添加 ruoyi schema）
│   ├── .env.example          ← 已修改（CORS）
│   ├── app/
│   │   ├── models/user.py    ← 已修改（新增 2 字段）
│   │   └── core/config.py    ← 已修改（CORS）
│   └── ...
├── frontend/                  ← 不动
├── ruoyi-admin-backend/       ← 新增
│   ├── Dockerfile
│   ├── sql/ruoyi-pg.sql
│   ├── requirements.txt
│   └── app/...
├── ruoyi-admin-frontend/      ← 新增
│   ├── Dockerfile
│   ├── src/...
│   └── ...
└── Makefile                   ← 已修改（新增 ruoyi 命令）
```

---

## 注意事项

1. **若依版本兼容性**：RuoYi-Vue3-FastAPI 社区版本可能迭代较快，克隆后请检查版本号。如果 Gitee 仓库不可用，可尝试其他镜像：
   - `https://gitee.com/lanjue/RuoYi-Vue-FastAPI`
   - `https://gitee.com/if-according-to-the-framework_1/ruo-yi-vue3-fast-api`

2. **PostgreSQL 首次初始化**：docker-entrypoint-initdb.d 中的 SQL 仅在数据卷为空时执行。如果已有数据，需要手动执行。

3. **密码兼容性**：若依和业务后端都使用 bcrypt，密码哈希算法一致。但两套系统各自维护自己的用户表，管理后台的 admin 账号是独立的。

4. **JWT Token 独立**：本方案中两套系统各自签发 Token，不强制互通。如需 Token 互通（如管理员从管理后台直接跳转到用户端），需要在后续阶段扩展。

5. **数据备份**：建议在开始实施前备份 PostgreSQL 数据：
   ```bash
   docker exec ai-learn-postgres pg_dump -U postgres learning_platform > backup.sql
   ```
