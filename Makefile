.PHONY: help build up down logs test migrate migrate-create schema-bootstrap schema-bootstrap-primary schema-bootstrap-catalog seed fmt lint test-delivery-scripts test-frontend typecheck-frontend build-frontend test-backend-isolated backup-safety-tests backup-drill migration-safety-tests migration-drill docker-smoke e2e verify-fast verify-ci

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
	$(PYTHON) -m unittest discover -s scripts/tests -p "test_*.py" -v

test-frontend: ## 运行前端正式测试入口
	cd frontend && npm test

typecheck-frontend: ## 运行前端 TypeScript 检查
	cd frontend && npm run typecheck

build-frontend: ## 构建前端生产制品
	cd frontend && npm run build

test-backend-isolated: ## 在无持久卷的可丢弃 PostgreSQL 中运行后端测试
	$(COMPOSE) build backend
	$(PYTHON) scripts/run_backend_tests.py

backup-safety-tests: ## 运行备份目标、校验、加密清单和保留策略安全测试
	$(PYTHON) -m unittest scripts.tests.test_backup_recovery -v

backup-drill: ## 在两个 tmpfs PostgreSQL 容器中真实执行加密备份与恢复
	$(PYTHON) scripts/run_backup_restore_drill.py

migration-safety-tests: ## 运行迁移目标、版本策略、导入边界和演练编排测试
	$(PYTHON) -m unittest scripts.tests.test_schema_migration_drill -v
	$(PYTHON) scripts/run_backend_tests.py -q tests/test_schema_migration.py

migration-drill: ## 在四个 tmpfs 数据库中演练双 revision root、回滚和基线采用
	$(PYTHON) scripts/run_schema_migration_drill.py

docker-smoke: ## 验证 Compose 服务、HTTP 健康端点与近期日志
	$(PYTHON) scripts/verify_delivery.py

e2e: ## 运行桌面和移动端真实浏览器、无障碍与 PWA 测试
	cd frontend && npm run e2e

verify-fast: ## 不启动容器的跨平台快速验证门槛
	$(PYTHON) scripts/verify.py fast

verify-ci: ## 本地与 CI 共用的完整阻断式交付验证
	$(PYTHON) scripts/verify.py full

migrate: ## 通过安全 Adapter 执行 upgrade head；授权参数按目标类型显式提供
	@test -n "$(target)" || { echo "缺少 target（primary 或 question-bank）" >&2; exit 2; }
	@test -n "$(database_url_file)" || { echo "缺少 database_url_file（容器内只读 secret 文件来源）" >&2; exit 2; }
	@test -n "$(environment)" || { echo "缺少 environment（local/ci/test/staging/production）" >&2; exit 2; }
	@test -n "$(expected_host)" || { echo "缺少 expected_host（二次确认的数据库主机）" >&2; exit 2; }
	@test -n "$(expected_database)" || { echo "缺少 expected_database（二次确认的数据库名）" >&2; exit 2; }
	@case "$(allow_release)" in true|false) ;; *) echo "allow_release 必须显式为 true 或 false" >&2; exit 2 ;; esac
	@case "$(confirm_empty_bootstrap)" in true|false) ;; *) echo "confirm_empty_bootstrap 必须显式为 true 或 false" >&2; exit 2 ;; esac
	@if [ "$(allow_release)" = "true" ] && [ -z "$(approval_reference)" ]; then echo "普通数据库 release 缺少 approval_reference（已批准变更单）" >&2; exit 2; fi
	@if [ "$(allow_release)" = "true" ] && [ "$(confirm_empty_bootstrap)" != "true" ] && [ -z "$(backup_reference)" ]; then echo "非空普通数据库 release 缺少 backup_reference（已验证备份）" >&2; exit 2; fi
	@$(COMPOSE) run --build --rm --no-deps \
		-v "$(abspath $(database_url_file)):/run/secrets/schema_database_url:ro" \
		backend python schema_admin.py upgrade \
		--target "$(target)" \
		--database-url-file /run/secrets/schema_database_url \
		--environment "$(environment)" \
		--expected-host "$(expected_host)" \
		--expected-database "$(expected_database)" \
		$(if $(filter true,$(allow_release)),--allow-release,) \
		$(if $(strip $(approval_reference)),--approval-reference "$(approval_reference)",) \
		$(if $(strip $(backup_reference)),--backup-reference "$(backup_reference)",) \
		$(if $(filter true,$(confirm_empty_bootstrap)),--confirm-empty-bootstrap,)

migrate-create: ## 安全 Adapter 尚不支持 revision create；本入口始终非零拒绝
	@echo "已拒绝：schema_admin.py 尚不支持 revision create，本命令没有创建任何文件。" >&2
	@echo "双 root 安全流程：先选择 primary 或 question-bank，再分别使用对应配置、版本目录和版本表；完成 review 后运行 migration-safety-tests 与 migration-drill。" >&2
	@echo "详见 docs/operations/schema-migrations.md 的“创建 revision”章节。" >&2
	@exit 2

schema-bootstrap: ## 依次运行两个可重入的全新空库 bootstrap target
	@test -n "$(approval_reference)" || { echo "缺少 approval_reference（全新空库 bootstrap 审批号）" >&2; exit 2; }
	@test -n "$(primary_database_url_file)" || { echo "缺少 primary_database_url_file" >&2; exit 2; }
	@test -n "$(catalog_database_url_file)" || { echo "缺少 catalog_database_url_file" >&2; exit 2; }
	@test -n "$(postgres_password_file)" || { echo "缺少 postgres_password_file" >&2; exit 2; }
	@$(MAKE) schema-bootstrap-primary approval_reference="$(approval_reference)" database_url_file="$(primary_database_url_file)" postgres_password_file="$(postgres_password_file)"
	@$(MAKE) schema-bootstrap-catalog approval_reference="$(approval_reference)" database_url_file="$(catalog_database_url_file)" postgres_password_file="$(postgres_password_file)"
	@echo "双库 bootstrap 已就绪；现在必须以 SCHEMA_VERSION_POLICY=strict 重新创建 backend。"

schema-bootstrap-primary: ## 独立 bootstrap 或复核已完成的 Compose 主业务库
	@test -n "$(approval_reference)" || { echo "缺少 approval_reference（主业务库 bootstrap 审批号）" >&2; exit 2; }
	@test -n "$(database_url_file)" || { echo "缺少 database_url_file" >&2; exit 2; }
	@test -n "$(postgres_password_file)" || { echo "缺少 postgres_password_file" >&2; exit 2; }
	@POSTGRES_PASSWORD_SECRET_FILE="$(abspath $(postgres_password_file))" $(COMPOSE) up -d --wait postgres
	@POSTGRES_PASSWORD_SECRET_FILE="$(abspath $(postgres_password_file))" PRIMARY_DATABASE_URL_SECRET_FILE="$(abspath $(database_url_file))" $(COMPOSE) --profile schema-bootstrap run --build --rm --no-deps \
		-e SCHEMA_BOOTSTRAP_APPROVAL_REFERENCE="$(approval_reference)" schema-bootstrap-primary

schema-bootstrap-catalog: ## 独立 bootstrap 或复核已完成的 Compose 题库
	@test -n "$(approval_reference)" || { echo "缺少 approval_reference（题库 bootstrap 审批号）" >&2; exit 2; }
	@test -n "$(database_url_file)" || { echo "缺少 database_url_file" >&2; exit 2; }
	@test -n "$(postgres_password_file)" || { echo "缺少 postgres_password_file" >&2; exit 2; }
	@POSTGRES_PASSWORD_SECRET_FILE="$(abspath $(postgres_password_file))" $(COMPOSE) up -d --wait postgres
	@POSTGRES_PASSWORD_SECRET_FILE="$(abspath $(postgres_password_file))" CATALOG_DATABASE_URL_SECRET_FILE="$(abspath $(database_url_file))" $(COMPOSE) --profile schema-bootstrap run --build --rm --no-deps \
		-e SCHEMA_BOOTSTRAP_APPROVAL_REFERENCE="$(approval_reference)" schema-bootstrap-catalog

seed: ## 初始化种子数据
	docker-compose exec backend python seed_data.py

fmt: ## 格式化后端代码（需安装 black）
	cd backend && black app/ tests/

lint: ## 后端代码检查（需安装 flake8）
	cd backend && flake8 app/ tests/ --max-line-length=120
