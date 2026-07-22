# -*- coding: utf-8 -*-
"""
Quiz 课时与知识点绑定脚本

功能说明：
- 扫描所有 type='quiz' 的课时
- 根据课程学科、年龄段、难度匹配对应的知识点节点
- 更新 Lesson.knowledge_node_id 字段，建立关联

映射规则：
- course.subject → KnowledgeNode.subject_code (math → SUBJ_MATH)
- course.age_group → KnowledgeNode.age_group_code (6-8 → AGE_06_08)
- course.difficulty → KnowledgeNode.difficulty_level (beginner → DIFF_EASY)

使用方式：
    docker compose exec backend python link_quiz_lessons.py
"""

import asyncio
import os
import sys

# 将 backend 目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.core.schema_version import SchemaVersionError, verify_schema_target
from app.models.course import Lesson, Course
from app.models.content import KnowledgeNode

DATABASE_URL = settings.DATABASE_URL

# 学科编码映射
SUBJECT_MAP = {
    "math": "SUBJ_MATH",
    "chinese": "SUBJ_CHINESE",
    "english": "SUBJ_ENGLISH",
    "science": "SUBJ_SCIENCE",
    "physics": "SUBJ_PHYSICS",
    "chemistry": "SUBJ_CHEMISTRY",
    "biology": "SUBJ_BIOLOGY",
    "history": "SUBJ_HISTORY",
    "geography": "SUBJ_GEOGRAPHY",
    "politics": "SUBJ_POLITICS",
    "art": "SUBJ_ART",
    "programming": "SUBJ_PROGRAMMING",
}

# 年龄段编码映射
AGE_MAP = {
    "6-8": "AGE_06_08",
    "9-12": "AGE_09_11",
    "13-15": "AGE_12_14",
    "16-18": "AGE_15_18",
    "06-09": "AGE_06_08",
    "10-12": "AGE_09_11",
}

# 难度编码映射
DIFF_MAP = {
    "beginner": "DIFF_EASY",
    "intermediate": "DIFF_MEDIUM",
    "advanced": "DIFF_HARD",
}


async def ensure_schema_ready(engine) -> None:
    """任何查询或 DML 前要求主业务库处于批准 head。"""

    await verify_schema_target(engine, "primary", policy="strict")


async def link_quiz_lessons():
    """主逻辑：绑定 quiz 课时到知识点"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    await ensure_schema_ready(engine)
    async with async_session() as db:
        # 1. 查询所有 quiz 类型的课时及其所属课程信息
        stmt = (
            select(Lesson, Course)
            .join(Course, Lesson.course_id == Course.id)
            .where(Lesson.type == "quiz")
        )
        result = await db.execute(stmt)
        quiz_lessons = result.all()

        print(f"发现 {len(quiz_lessons)} 个 quiz 类型课时")

        linked = 0
        skipped = 0
        not_found = 0

        for lesson, course in quiz_lessons:
            # 2. 编码映射
            subject_code = SUBJECT_MAP.get(course.subject)
            age_group_code = AGE_MAP.get(course.age_group)
            difficulty_level = DIFF_MAP.get(course.difficulty)

            if not all([subject_code, age_group_code, difficulty_level]):
                print(
                    f"  [跳过] 课时 '{lesson.title}' (课程: {course.subject}/{course.age_group}/{course.difficulty}) "
                    f"映射失败: subject={subject_code}, age={age_group_code}, diff={difficulty_level}"
                )
                skipped += 1
                continue

            # 3. 查找匹配的知识点节点
            kn_stmt = select(KnowledgeNode).where(
                and_(
                    KnowledgeNode.subject_code == subject_code,
                    KnowledgeNode.age_group_code == age_group_code,
                    KnowledgeNode.difficulty_level == difficulty_level,
                    KnowledgeNode.content_type == "TYPE_QUIZ",
                )
            )
            kn_result = await db.execute(kn_stmt)
            knowledge_node = kn_result.scalar_one_or_none()

            if knowledge_node is None:
                # 尝试放宽条件，只匹配学科+年龄段（不限制难度）
                kn_stmt2 = select(KnowledgeNode).where(
                    and_(
                        KnowledgeNode.subject_code == subject_code,
                        KnowledgeNode.age_group_code == age_group_code,
                        KnowledgeNode.content_type == "TYPE_QUIZ",
                    )
                )
                kn_result2 = await db.execute(kn_stmt2)
                knowledge_node = kn_result2.scalars().first()

            if knowledge_node is None:
                print(
                    f"  [未找到] 课时 '{lesson.title}' → 知识点 ({subject_code}, {age_group_code}, {difficulty_level}) 不存在"
                )
                not_found += 1
                continue

            # 4. 更新 Lesson.knowledge_node_id
            lesson.knowledge_node_id = str(knowledge_node.id)
            linked += 1
            print(
                f"  [已绑定] 课时 '{lesson.title}' → 知识点 '{knowledge_node.title}' ({knowledge_node.id})"
            )

        # 5. 提交事务
        await db.commit()

        print("\n========== 绑定结果 ==========")
        print(f"  总 quiz 课时: {len(quiz_lessons)}")
        print(f"  成功绑定: {linked}")
        print(f"  映射失败跳过: {skipped}")
        print(f"  未找到知识点: {not_found}")
        print("==============================")

    await engine.dispose()


def run() -> int:
    try:
        asyncio.run(link_quiz_lessons())
    except SchemaVersionError as exc:
        print(f"绑定已拒绝：{exc}", file=sys.stderr)
        return 2
    except Exception:
        print("绑定失败，事务已停止；请检查脱敏服务日志。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
