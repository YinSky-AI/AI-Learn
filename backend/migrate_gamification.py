# -*- coding: utf-8 -*-
"""为已有数据库补齐游戏化字段；可重复执行。"""

import asyncio

from sqlalchemy import text

from app.core.database import engine


STATEMENTS = (
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS current_correct_streak INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS max_correct_streak INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS total_answered INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS correct_answered INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_date DATE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS study_days_count INTEGER NOT NULL DEFAULT 0",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_achievement_user_achievement ON user_achievements (user_id, achievement_id)",
)


async def main() -> None:
    async with engine.begin() as connection:
        for statement in STATEMENTS:
            await connection.execute(text(statement))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
