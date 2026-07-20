.PHONY: help build up down logs test migrate seed fmt lint

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
	docker-compose exec backend pytest -v

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
