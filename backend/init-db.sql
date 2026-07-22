-- AI 智能学习平台 - 数据库初始化脚本
-- 此脚本在 PostgreSQL 容器首次启动时自动执行

-- 启用必要的扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 应用首次启动会根据 ORM 创建游戏化表；已有数据库可重复执行 migrate_gamification.py 补齐字段。
