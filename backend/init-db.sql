-- AI 智能学习平台 - 数据库初始化脚本
-- 此脚本在 PostgreSQL 容器首次启动时自动执行

-- 启用必要的扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
