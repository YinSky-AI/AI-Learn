-- AI 智能学习平台 - 数据库初始化脚本
-- 此脚本在 PostgreSQL 容器首次启动时自动执行

-- 启用必要的扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 只建立两个明确的数据库边界；表、索引和约束仍全部来自各自 Alembic root。
SELECT 'CREATE DATABASE ai_learn'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ai_learn')\gexec

-- 本文件只准备数据库级扩展。应用 Schema 必须通过两个显式 Alembic root 部署；
-- FastAPI 启动、导入脚本和旧 migrate_gamification.py 均不得定义或修补 Schema。
