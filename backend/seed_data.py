# -*- coding: utf-8 -*-
"""
AI 学习平台种子数据脚本
将固定的学科、年龄分级、课程和课时数据导入数据库

运行方式:
    cd backend && python seed_data.py
"""

import asyncio
import logging
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.content import AgeGroup, Subject
from app.models.course import Course, Lesson

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 用于生成确定性 UUID 的命名空间
NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def make_uuid(name: str) -> uuid.UUID:
    """根据名称生成确定性 UUID，保证多次运行结果一致"""
    return uuid.uuid5(NAMESPACE, name)


# ============ 学科数据 ============
SUBJECTS = [
    {"code": "SUBJ_MATH", "name": "数学", "icon": "math.svg", "sort_order": 1},
    {"code": "SUBJ_SCIENCE", "name": "科学", "icon": "science.svg", "sort_order": 2},
    {"code": "SUBJ_CHINESE", "name": "语文", "icon": "chinese.svg", "sort_order": 3},
    {"code": "SUBJ_ENGLISH", "name": "英语", "icon": "english.svg", "sort_order": 4},
    {"code": "SUBJ_PROGRAMMING", "name": "编程", "icon": "programming.svg", "sort_order": 5},
    {"code": "SUBJ_ART", "name": "艺术", "icon": "art.svg", "sort_order": 6},
    {"code": "SUBJ_HISTORY", "name": "历史", "icon": "history.svg", "sort_order": 7},
    {"code": "SUBJ_PHYSICS", "name": "物理", "icon": "physics.svg", "sort_order": 8},
    {"code": "SUBJ_CHEMISTRY", "name": "化学", "icon": "chemistry.svg", "sort_order": 9},
    {"code": "SUBJ_BIOLOGY", "name": "生物", "icon": "biology.svg", "sort_order": 10},
    {"code": "SUBJ_GEOGRAPHY", "name": "地理", "icon": "geography.svg", "sort_order": 11},
    {"code": "SUBJ_POLITICS", "name": "政治", "icon": "politics.svg", "sort_order": 12},
]

# ============ 年龄分级数据 ============
AGE_GROUPS = [
    {
        "code": "AGE_06_08",
        "name": "6-8岁(小学低年级)",
        "min_age": 6,
        "max_age": 8,
        "theme_config": {
            "primary_color": "#FF9F43",
            "font_size": "large",
            "spacing": "comfortable",
            "illustration_style": "cartoon",
        },
    },
    {
        "code": "AGE_09_11",
        "name": "9-11岁(小学高年级)",
        "min_age": 9,
        "max_age": 11,
        "theme_config": {
            "primary_color": "#10AC84",
            "font_size": "medium",
            "spacing": "normal",
            "illustration_style": "friendly",
        },
    },
    {
        "code": "AGE_12_14",
        "name": "12-14岁(初中)",
        "min_age": 12,
        "max_age": 14,
        "theme_config": {
            "primary_color": "#5F27CD",
            "font_size": "medium",
            "spacing": "normal",
            "illustration_style": "modern",
        },
    },
    {
        "code": "AGE_15_18",
        "name": "15-18岁(高中)",
        "min_age": 15,
        "max_age": 18,
        "theme_config": {
            "primary_color": "#341F97",
            "font_size": "normal",
            "spacing": "compact",
            "illustration_style": "minimal",
        },
    },
]

# 学科编码 -> 学科 key 映射（用于 slug）
SUBJECT_MAP = {
    "SUBJ_MATH": "math",
    "SUBJ_SCIENCE": "science",
    "SUBJ_CHINESE": "chinese",
    "SUBJ_ENGLISH": "english",
    "SUBJ_PROGRAMMING": "programming",
    "SUBJ_ART": "art",
    "SUBJ_HISTORY": "history",
    "SUBJ_PHYSICS": "physics",
    "SUBJ_CHEMISTRY": "chemistry",
    "SUBJ_BIOLOGY": "biology",
    "SUBJ_GEOGRAPHY": "geography",
    "SUBJ_POLITICS": "politics",
}

# 年龄编码 -> 年龄 key 映射
AGE_GROUP_MAP = {
    "AGE_06_08": "06-09",
    "AGE_09_11": "10-12",
    "AGE_12_14": "13-15",
    "AGE_15_18": "16-18",
}

# ============ 课程与课时数据 ============
COURSES_DATA = [
    {
        "slug": "course-1",
        "title": "趣味数学入门",
        "description": "通过趣味故事和游戏，带领孩子走进数学的奇妙世界，培养基础数学思维。",
        "subject_code": "SUBJ_MATH",
        "difficulty": "beginner",
        "age_group_code": "AGE_06_08",
        "duration": 130,
        "rating": 4.5,
        "enroll_count": 328,
        "lessons": [
            ("课程导学", "video", 10),
            ("基础概念", "text", 15),
            ("核心知识点", "text", 20),
            ("实例讲解", "video", 15),
            ("互动练习", "interactive", 20),
            ("知识测验", "quiz", 15),
            ("拓展阅读", "text", 10),
            ("综合练习", "interactive", 25),
        ],
    },
    {
        "slug": "course-2",
        "title": "小小科学家",
        "description": "探索身边的科学现象，通过简单实验培养观察力和科学兴趣。",
        "subject_code": "SUBJ_SCIENCE",
        "difficulty": "beginner",
        "age_group_code": "AGE_06_08",
        "duration": 120,
        "rating": 4.2,
        "enroll_count": 256,
        "lessons": [
            ("课程导学", "video", 10),
            ("科学观察", "text", 15),
            ("自然现象", "text", 20),
            ("实验演示", "video", 15),
            ("动手实验", "interactive", 20),
            ("知识测验", "quiz", 15),
            ("科学故事", "text", 10),
            ("综合实践", "interactive", 15),
        ],
    },
    {
        "slug": "course-3",
        "title": "语法基础入门",
        "description": "系统学习英语基础语法，构建扎实的语言框架，为进阶学习打下基础。",
        "subject_code": "SUBJ_ENGLISH",
        "difficulty": "beginner",
        "age_group_code": "AGE_09_11",
        "duration": 150,
        "rating": 4.3,
        "enroll_count": 412,
        "lessons": [
            ("课程导学", "video", 10),
            ("词性基础", "text", 15),
            ("时态入门", "text", 20),
            ("句型结构", "text", 15),
            ("实例讲解", "video", 15),
            ("语法练习", "interactive", 20),
            ("阶段测验", "quiz", 15),
            ("常见错误", "text", 15),
            ("综合练习", "interactive", 20),
            ("课程总结", "text", 5),
        ],
    },
    {
        "slug": "course-4",
        "title": "游戏开发入门",
        "description": "学习使用游戏引擎开发2D游戏，掌握游戏设计基础与编程逻辑。",
        "subject_code": "SUBJ_PROGRAMMING",
        "difficulty": "intermediate",
        "age_group_code": "AGE_12_14",
        "duration": 200,
        "rating": 4.6,
        "enroll_count": 189,
        "lessons": [
            ("课程导学", "video", 10),
            ("引擎介绍", "text", 15),
            ("场景搭建", "text", 20),
            ("角色控制", "text", 20),
            ("动画系统", "video", 15),
            ("物理碰撞", "interactive", 20),
            ("关卡设计", "interactive", 20),
            ("UI系统", "text", 15),
            ("音效集成", "interactive", 15),
            ("项目实践", "interactive", 25),
            ("阶段测试", "quiz", 15),
            ("发布分享", "text", 10),
        ],
    },
    {
        "slug": "course-5",
        "title": "创意绘画课",
        "description": "激发创造力与想象力，通过多种绘画技法表达内心世界。",
        "subject_code": "SUBJ_ART",
        "difficulty": "beginner",
        "age_group_code": "AGE_06_08",
        "duration": 110,
        "rating": 4.4,
        "enroll_count": 198,
        "lessons": [
            ("课程导学", "video", 10),
            ("色彩认知", "text", 15),
            ("线条练习", "text", 15),
            ("创意启发", "video", 15),
            ("自由创作", "interactive", 20),
            ("作品欣赏", "text", 15),
            ("互动点评", "interactive", 10),
            ("综合创作", "interactive", 10),
        ],
    },
    {
        "slug": "course-6",
        "title": "世界历史故事",
        "description": "以故事形式讲述世界历史上的重要事件与人物，培养历史视野。",
        "subject_code": "SUBJ_HISTORY",
        "difficulty": "beginner",
        "age_group_code": "AGE_09_11",
        "duration": 140,
        "rating": 4.1,
        "enroll_count": 267,
        "lessons": [
            ("课程导学", "video", 10),
            ("古代文明", "text", 15),
            ("中世纪", "text", 15),
            ("文艺复兴", "text", 15),
            ("工业革命", "text", 15),
            ("历史人物", "video", 15),
            ("事件分析", "interactive", 20),
            ("知识测验", "quiz", 15),
            ("拓展阅读", "text", 15),
            ("课程总结", "text", 5),
        ],
    },
    {
        "slug": "course-7",
        "title": "代数基础",
        "description": "系统学习代数基本概念与运算规则，建立抽象思维能力。",
        "subject_code": "SUBJ_MATH",
        "difficulty": "intermediate",
        "age_group_code": "AGE_12_14",
        "duration": 180,
        "rating": 4.5,
        "enroll_count": 345,
        "lessons": [
            ("课程导学", "video", 10),
            ("代数符号", "text", 15),
            ("方程基础", "text", 20),
            ("不等式", "text", 20),
            ("函数概念", "text", 20),
            ("实例讲解", "video", 20),
            ("解题技巧", "interactive", 20),
            ("阶段测验", "quiz", 15),
            ("综合练习", "interactive", 25),
            ("课程总结", "text", 5),
        ],
    },
    {
        "slug": "course-8",
        "title": "化学反应探秘",
        "description": "深入理解化学反应原理，通过虚拟实验掌握化学方程式与反应类型。",
        "subject_code": "SUBJ_SCIENCE",
        "difficulty": "intermediate",
        "age_group_code": "AGE_12_14",
        "duration": 190,
        "rating": 4.3,
        "enroll_count": 234,
        "lessons": [
            ("课程导学", "video", 10),
            ("原子结构", "text", 15),
            ("化学键", "text", 15),
            ("化学方程式", "text", 20),
            ("反应类型", "text", 20),
            ("虚拟实验", "interactive", 20),
            ("计算练习", "interactive", 20),
            ("酸碱盐", "text", 15),
            ("氧化还原", "text", 15),
            ("阶段测验", "quiz", 15),
            ("项目实践", "interactive", 20),
            ("课程总结", "text", 5),
        ],
    },
    {
        "slug": "course-9",
        "title": "语文基础知识",
        "description": "夯实语文基础，涵盖字词句段、修辞手法与阅读理解核心要点。",
        "subject_code": "SUBJ_CHINESE",
        "difficulty": "beginner",
        "age_group_code": "AGE_09_11",
        "duration": 160,
        "rating": 4.6,
        "enroll_count": 445,
        "lessons": [
            ("课程导学", "video", 10),
            ("汉字基础", "text", 15),
            ("词语运用", "text", 20),
            ("句子结构", "text", 15),
            ("修辞手法", "text", 15),
            ("阅读理解", "interactive", 20),
            ("写作入门", "interactive", 20),
            ("知识测验", "quiz", 15),
            ("名篇赏析", "text", 15),
            ("课程总结", "text", 5),
        ],
    },
    {
        "slug": "course-10",
        "title": "英语自然拼读",
        "description": "通过自然拼读法建立字母与发音的联系，轻松开启英语阅读之门。",
        "subject_code": "SUBJ_ENGLISH",
        "difficulty": "beginner",
        "age_group_code": "AGE_06_08",
        "duration": 120,
        "rating": 4.4,
        "enroll_count": 389,
        "lessons": [
            ("课程导学", "video", 10),
            ("字母发音", "text", 15),
            ("短元音", "text", 15),
            ("长元音", "text", 15),
            ("辅音组合", "video", 15),
            ("拼读练习", "interactive", 20),
            ("阅读实践", "interactive", 15),
            ("课程回顾", "text", 5),
        ],
    },
    {
        "slug": "course-11",
        "title": "Python入门之旅",
        "description": "从零开始学习Python编程，掌握变量、循环、函数等核心概念。",
        "subject_code": "SUBJ_PROGRAMMING",
        "difficulty": "beginner",
        "age_group_code": "AGE_12_14",
        "duration": 170,
        "rating": 4.7,
        "enroll_count": 512,
        "lessons": [
            ("课程导学", "video", 10),
            ("环境搭建", "text", 10),
            ("变量与数据类型", "text", 20),
            ("条件判断", "text", 20),
            ("循环结构", "text", 20),
            ("函数定义", "text", 20),
            ("编程实践", "interactive", 25),
            ("阶段测验", "quiz", 15),
            ("小项目实战", "interactive", 20),
            ("课程总结", "text", 5),
        ],
    },
    {
        "slug": "course-12",
        "title": "古诗词鉴赏",
        "description": "深入鉴赏经典古诗词，理解意境、格律与文化背景，提升文学素养。",
        "subject_code": "SUBJ_CHINESE",
        "difficulty": "advanced",
        "age_group_code": "AGE_15_18",
        "duration": 200,
        "rating": 4.8,
        "enroll_count": 176,
        "lessons": [
            ("课程导学", "video", 10),
            ("诗词格律", "text", 20),
            ("唐诗鉴赏", "text", 20),
            ("宋词赏析", "text", 20),
            ("诗人背景", "text", 15),
            ("意象分析", "interactive", 20),
            ("创作手法", "text", 15),
            ("对比阅读", "interactive", 20),
            ("名篇精读", "text", 20),
            ("写作练习", "interactive", 20),
            ("阶段测试", "quiz", 15),
            ("课程总结", "text", 5),
        ],
    },
]


async def seed_subjects(session: AsyncSession) -> None:
    """导入学科数据，跳过已存在的记录"""
    logger.info("[1/4] 开始检查学科数据...")
    result = await session.execute(select(Subject.code))
    existing_codes = set(result.scalars().all())

    to_add = []
    for subj in SUBJECTS:
        if subj["code"] not in existing_codes:
            to_add.append(Subject(**subj))
            existing_codes.add(subj["code"])

    if to_add:
        session.add_all(to_add)
        await session.flush()
        logger.info(f"  -> 成功导入 {len(to_add)} 个学科")
    else:
        logger.info("  -> 学科数据已存在，跳过导入")


async def seed_age_groups(session: AsyncSession) -> None:
    """导入年龄分级数据，跳过已存在的记录"""
    logger.info("[2/4] 开始检查年龄分级数据...")
    result = await session.execute(select(AgeGroup.code))
    existing_codes = set(result.scalars().all())

    to_add = []
    for ag in AGE_GROUPS:
        if ag["code"] not in existing_codes:
            to_add.append(AgeGroup(**ag))
            existing_codes.add(ag["code"])

    if to_add:
        session.add_all(to_add)
        await session.flush()
        logger.info(f"  -> 成功导入 {len(to_add)} 个年龄分级")
    else:
        logger.info("  -> 年龄分级数据已存在，跳过导入")


async def seed_courses_and_lessons(session: AsyncSession) -> None:
    """导入课程和课时数据，逐门检查避免重复"""
    logger.info("[3/4] 开始检查课程与课时数据...")
    result = await session.execute(select(Course.id))
    existing_course_ids = set(result.scalars().all())

    courses_added = 0
    lessons_added = 0

    for idx, course_data in enumerate(COURSES_DATA, start=1):
        course_id = make_uuid(f"course:{course_data['slug']}")
        if course_id in existing_course_ids:
            continue

        subject_key = SUBJECT_MAP.get(course_data["subject_code"], "math")
        age_key = AGE_GROUP_MAP.get(course_data["age_group_code"], "06-09")

        course = Course(
            id=course_id,
            title=course_data["title"],
            description=course_data["description"],
            subject=subject_key,
            age_group=age_key,
            difficulty=course_data["difficulty"],
            duration=course_data["duration"],
            rating=course_data.get("rating", 4.0),
            enroll_count=course_data.get("enroll_count", 0),
            total_lessons=len(course_data["lessons"]),
            tags=[subject_key, course_data["difficulty"]],
            is_active=True,
            sort_order=idx,
            slug=course_data["slug"],
        )
        session.add(course)
        await session.flush()

        courses_added += 1
        logger.info(f"  -> 导入课程: {course.title} ({course.slug})")

        lesson_objs = []
        for l_idx, (lesson_title, lesson_type, duration) in enumerate(course_data["lessons"], start=1):
            lesson_id = make_uuid(f"lesson:{course_data['slug']}:{l_idx}")
            lesson = Lesson(
                id=lesson_id,
                course_id=course_id,
                title=lesson_title,
                type=lesson_type,
                duration=duration,
                order=l_idx,
                is_active=True,
            )
            lesson_objs.append(lesson)

        session.add_all(lesson_objs)
        await session.flush()
        lessons_added += len(lesson_objs)

    if courses_added:
        logger.info(f"  -> 共导入 {courses_added} 门课程，{lessons_added} 个课时")
    else:
        logger.info("  -> 课程数据已存在，跳过导入")


async def main() -> None:
    """主入口：创建异步引擎和会话，在事务中执行种子数据导入"""
    logger.info("=" * 50)
    logger.info("AI 学习平台种子数据导入开始")
    logger.info(f"数据库: {settings.DATABASE_URL.replace('://', '://***:***@')}")
    logger.info("=" * 50)

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with AsyncSessionLocal() as session:
        try:
            await seed_subjects(session)
            await seed_age_groups(session)
            await seed_courses_and_lessons(session)

            await session.commit()
            logger.info("=" * 50)
            logger.info("种子数据导入完成，事务已提交")
            logger.info("=" * 50)
        except Exception as exc:
            await session.rollback()
            logger.error(f"导入失败，事务已回滚: {exc}", exc_info=True)
            sys.exit(1)
        finally:
            await session.close()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
