.PHONY: help build up down logs test migrate seed fmt lint test-delivery-scripts test-frontend typecheck-frontend build-frontend test-backend-isolated docker-smoke e2e verify-fast verify-ci

PYTHON ?= python
COMPOSE ?= docker compose

help: ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## 构建所有 Docker 镜像
	docker-compose build

up: ## 启动所有服务（后台运行）
	docker-compose up -d

down: ## 停止所有服务
	docker-compose down

logs: ## 查看所有服务日志
	docker-compose logs -f

backend-logs: ## 查看后端日志
	docker-compose logs -f backend

frontend-logs: ## 查看前端日志
	docker-compose logs -f frontend

test: ## 运行后端测试（需要先启动服务）
	$(COMPOSE) exec backend pytest -v

test-delivery-scripts: ## 运行交付验证脚本单元测试
	$(PYTHON) -m unittest scripts.tests.test_verify_delivery -v

test-frontend: ## 运行前端正式测试入口
	cd frontend && npm test

typecheck-frontend: ## 运行前端 TypeScript 检查
	cd frontend && npm run typecheck

build-frontend: ## 构建前端生产制品
	cd frontend && npm run build

test-backend-isolated: ## 在无持久卷的可丢弃 PostgreSQL 中运行后端测试
	$(COMPOSE) build backend
	$(PYTHON) scripts/run_backend_tests.py

docker-smoke: ## 验证 Compose 服务、HTTP 健康端点与近期日志
	$(PYTHON) scripts/verify_delivery.py

e2e: ## 运行桌面和移动端真实浏览器、无障碍与 PWA 测试
	cd frontend && npm run e2e

verify-fast: ## 不启动容器的跨平台快速验证门槛
	$(PYTHON) scripts/verify.py fast

verify-ci: ## 本地与 CI 共用的完整阻断式交付验证
	$(PYTHON) scripts/verify.py full

migrate: ## 运行数据库迁移
	docker-compose exec backend alembic upgrade head

migrate-create: ## 创建新的迁移文件（需传递 msg 参数，如 make migrate-create msg="add_user_table"）
	docker-compose exec backend alembic revision --autogenerate -m "$(msg)"

seed: ## 初始化种子数据
	docker-compose exec backend python seed_data.py

fmt: ## 格式化后端代码（需安装 black）
	cd backend && black app/ tests/

lint: ## 后端代码检查（需安装 flake8）
	cd backend && flake8 app/ tests/ --max-line-length=120
