from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from utils.log_util import logger


class CourseDao:
    """
    课程管理模块数据库操作层（public schema）
    """

    @classmethod
    async def get_course_list(
        cls,
        db: AsyncSession,
        query_params: Dict[str, Any],
        page_num: int = 1,
        page_size: int = 10,
        is_page: bool = True,
    ) -> Any:
        """分页查询课程列表"""
        conditions = []
        params: Dict[str, Any] = {}

        keyword = query_params.get('keyword')
        if keyword:
            conditions.append("(c.title LIKE :keyword OR c.description LIKE :keyword)")
            params['keyword'] = f'%{keyword}%'

        subject = query_params.get('subject')
        if subject:
            conditions.append("c.subject = :subject")
            params['subject'] = subject

        difficulty = query_params.get('difficulty')
        if difficulty:
            conditions.append("c.difficulty = :difficulty")
            params['difficulty'] = difficulty

        age_group = query_params.get('age_group')
        if age_group:
            conditions.append("c.age_group = :age_group")
            params['age_group'] = age_group

        is_active = query_params.get('is_active')
        if is_active is not None and is_active != '' and is_active != 'None':
            conditions.append("c.is_active = :is_active")
            params['is_active'] = is_active

        where_clause = ' AND '.join(conditions) if conditions else '1=1'

        # 查询总数
        count_sql = f"SELECT COUNT(*) FROM public.courses c WHERE {where_clause}"
        total_result = await db.execute(text(count_sql), params)
        total = total_result.scalar() or 0

        # 查询数据
        offset = (page_num - 1) * page_size
        data_sql = f"""
            SELECT c.*, (
                SELECT COUNT(*) FROM public.lessons l WHERE l.course_id = c.id
            ) AS lesson_count
            FROM public.courses c
            WHERE {where_clause}
            ORDER BY c.created_at DESC
        """
        if is_page:
            data_sql += " LIMIT :limit OFFSET :offset"
            params['limit'] = page_size
            params['offset'] = offset

        result = await db.execute(text(data_sql), params)
        rows = result.mappings().all()
        data = [dict(row) for row in rows]

        if is_page:
            from utils.page_util import PageResponseModel
            has_next = (total // page_size) >= page_num if page_size > 0 else False
            return PageResponseModel(
                rows=data, page_num=page_num, page_size=page_size,
                total=total, has_next=has_next,
            )
        return data

    @classmethod
    async def get_course_detail(cls, db: AsyncSession, course_id: int) -> Optional[Dict[str, Any]]:
        """查询单个课程详情（含关联课时数）"""
        sql = """
            SELECT c.*, (
                SELECT COUNT(*) FROM public.lessons l WHERE l.course_id = c.id
            ) AS lesson_count
            FROM public.courses c
            WHERE c.id = :course_id
        """
        result = await db.execute(text(sql), {'course_id': course_id})
        row = result.mappings().first()
        return dict(row) if row else None

    @classmethod
    async def update_course_status(cls, db: AsyncSession, course_id: int, is_active: bool) -> int:
        """修改课程上下架状态"""
        sql = """
            UPDATE public.courses
            SET is_active = :is_active, updated_at = :updated_at
            WHERE id = :course_id
        """
        result = await db.execute(
            text(sql),
            {'course_id': course_id, 'is_active': is_active, 'updated_at': datetime.now()},
        )
        await db.flush()
        return result.rowcount

    @classmethod
    async def delete_course(cls, db: AsyncSession, course_id: int) -> int:
        """删除课程"""
        sql = "DELETE FROM public.courses WHERE id = :course_id"
        result = await db.execute(text(sql), {'course_id': course_id})
        await db.flush()
        return result.rowcount

    @classmethod
    async def get_course_stats(cls, db: AsyncSession) -> Dict[str, Any]:
        """课程统计数据：总数、各学科分布、难度分布"""
        total_result = await db.execute(text("SELECT COUNT(*) FROM public.courses"))
        total = total_result.scalar() or 0

        subject_result = await db.execute(text("""
            SELECT subject, COUNT(*) AS count FROM public.courses
            GROUP BY subject ORDER BY count DESC
        """))
        subject_dist = [dict(row) for row in subject_result.mappings().all()]

        difficulty_result = await db.execute(text("""
            SELECT difficulty, COUNT(*) AS count FROM public.courses
            GROUP BY difficulty ORDER BY count DESC
        """))
        difficulty_dist = [dict(row) for row in difficulty_result.mappings().all()]

        return {
            'total': total,
            'subject_distribution': subject_dist,
            'difficulty_distribution': difficulty_dist,
        }


class PlatformUserDao:
    """
    平台用户管理模块数据库操作层（public schema）
    """

    @classmethod
    async def get_platform_user_list(
        cls,
        db: AsyncSession,
        query_params: Dict[str, Any],
        page_num: int = 1,
        page_size: int = 10,
        is_page: bool = True,
    ) -> Any:
        """分页查询平台用户列表"""
        conditions = []
        params: Dict[str, Any] = {}

        keyword = query_params.get('keyword')
        if keyword:
            conditions.append("(u.nickname LIKE :keyword OR u.email LIKE :keyword)")
            params['keyword'] = f'%{keyword}%'

        age_group = query_params.get('age_group')
        if age_group:
            conditions.append("u.age_group = :age_group")
            params['age_group'] = age_group

        where_clause = ' AND '.join(conditions) if conditions else '1=1'

        count_sql = f"SELECT COUNT(*) FROM public.users u WHERE {where_clause}"
        total_result = await db.execute(text(count_sql), params)
        total = total_result.scalar() or 0

        offset = (page_num - 1) * page_size
        data_sql = f"""
            SELECT u.*,
                COALESCE(enroll_stat.enroll_count, 0) AS enroll_count,
                COALESCE(enroll_stat.completed_lessons, 0) AS completed_lessons,
                COALESCE(lesson_stat.total_study_seconds, 0) AS total_study_seconds
            FROM public.users u
            LEFT JOIN (
                SELECT
                    uc.user_id,
                    COUNT(DISTINCT uc.course_id) AS enroll_count,
                    SUM(uc.completed_lessons) AS completed_lessons
                FROM public.user_courses uc
                GROUP BY uc.user_id
            ) enroll_stat ON enroll_stat.user_id = u.id
            LEFT JOIN (
                SELECT
                    ul.user_id,
                    COALESCE(SUM(ul.time_spent_seconds), 0) AS total_study_seconds
                FROM public.user_lessons ul
                GROUP BY ul.user_id
            ) lesson_stat ON lesson_stat.user_id = u.id
            WHERE {where_clause}
            ORDER BY u.created_at DESC
        """
        if is_page:
            data_sql += " LIMIT :limit OFFSET :offset"
            params['limit'] = page_size
            params['offset'] = offset

        result = await db.execute(text(data_sql), params)
        rows = result.mappings().all()
        data = [dict(row) for row in rows]

        if is_page:
            from utils.page_util import PageResponseModel
            has_next = (total // page_size) >= page_num if page_size > 0 else False
            return PageResponseModel(
                rows=data, page_num=page_num, page_size=page_size,
                total=total, has_next=has_next,
            )
        return data

    @classmethod
    async def get_platform_user_detail(cls, db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
        """查询平台用户详情（含学习统计）"""
        sql = """
            SELECT u.*,
                COALESCE(enroll_stat.enroll_count, 0) AS enroll_count,
                COALESCE(enroll_stat.completed_lessons, 0) AS completed_lessons
            FROM public.users u
            LEFT JOIN (
                SELECT user_id, COUNT(DISTINCT course_id) AS enroll_count,
                       SUM(completed_lessons) AS completed_lessons
                FROM public.user_courses GROUP BY user_id
            ) enroll_stat ON enroll_stat.user_id = u.id
            WHERE u.id = :user_id
        """
        result = await db.execute(text(sql), {'user_id': user_id})
        row = result.mappings().first()
        return dict(row) if row else None

    @classmethod
    async def update_platform_user(cls, db: AsyncSession, user_id: int, update_data: Dict[str, Any]) -> int:
        """修改平台用户信息"""
        if not update_data:
            return 0

        update_data['updated_at'] = datetime.now()
        update_data['user_id'] = user_id

        set_clauses = []
        for key, value in update_data.items():
            if key not in ('user_id', 'id'):
                set_clauses.append(f"{key} = :{key}")

        if not set_clauses:
            return 0

        sql = f"UPDATE public.users SET {', '.join(set_clauses)} WHERE id = :user_id"
        result = await db.execute(text(sql), update_data)
        await db.flush()
        return result.rowcount

    @classmethod
    async def delete_platform_user(cls, db: AsyncSession, user_id: int) -> int:
        """删除平台用户"""
        await db.execute(text("DELETE FROM public.user_courses WHERE user_id = :user_id"), {'user_id': user_id})
        await db.execute(text("DELETE FROM public.user_lessons WHERE user_id = :user_id"), {'user_id': user_id})
        sql = "DELETE FROM public.users WHERE id = :user_id"
        result = await db.execute(text(sql), {'user_id': user_id})
        await db.flush()
        return result.rowcount

    @classmethod
    async def get_user_stats_overview(cls, db: AsyncSession) -> Dict[str, Any]:
        """用户统计概览：总用户数、今日新增、活跃用户数"""
        total_result = await db.execute(text("SELECT COUNT(*) FROM public.users"))
        total_users = total_result.scalar() or 0

        today = datetime.now().date()
        today_result = await db.execute(
            text("SELECT COUNT(*) FROM public.users WHERE DATE(created_at) = :today"),
            {'today': today}
        )
        today_new = today_result.scalar() or 0

        # 近30天有学习记录的用户
        active_result = await db.execute(text("""
            SELECT COUNT(DISTINCT user_id) FROM public.user_lessons
            WHERE created_at >= :active_date
        """), {'active_date': datetime.now() - timedelta(days=30)})
        active_users = active_result.scalar() or 0

        return {
            'total_users': total_users,
            'today_new_users': today_new,
            'active_users_30d': active_users,
        }


class LearningStatsDao:
    """
    学习统计模块数据库操作层（public schema）
    """

    @classmethod
    async def get_learning_stats(cls, db: AsyncSession) -> Dict[str, Any]:
        """总体学习数据：总学习时长、总完成课时"""
        result = await db.execute(text("""
            SELECT
                COALESCE(SUM(time_spent_seconds), 0) AS total_study_seconds,
                COUNT(*) AS total_completed_lessons
            FROM public.user_lessons
            WHERE completed = true
        """))
        row = result.mappings().first()
        if row:
            data = dict(row)
            data['total_study_hours'] = round(data['total_study_seconds'] / 3600, 1)
            return data
        return {'total_study_seconds': 0, 'total_completed_lessons': 0, 'total_study_hours': 0}

    @classmethod
    async def get_daily_active_users(cls, db: AsyncSession, days: int = 30) -> List[Dict[str, Any]]:
        """近N天每日活跃用户数"""
        sql = """
            SELECT DATE(created_at) AS date, COUNT(DISTINCT user_id) AS active_count
            FROM public.user_lessons
            WHERE created_at >= :start_date
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        """
        start_date = datetime.now() - timedelta(days=days)
        result = await db.execute(text(sql), {'start_date': start_date})
        return [dict(row) for row in result.mappings().all()]

    @classmethod
    async def get_course_enroll_ranking(cls, db: AsyncSession, limit: int = 10) -> List[Dict[str, Any]]:
        """课程报名排行"""
        sql = """
            SELECT c.id, c.title, c.subject, c.difficulty,
                c.enroll_count
            FROM public.courses c
            ORDER BY c.enroll_count DESC
            LIMIT :limit
        """
        result = await db.execute(text(sql), {'limit': limit})
        return [dict(row) for row in result.mappings().all()]

    @classmethod
    async def get_subject_distribution(cls, db: AsyncSession) -> List[Dict[str, Any]]:
        """学科分布统计"""
        result = await db.execute(text("""
            SELECT subject, COUNT(*) AS course_count
            FROM public.courses
            GROUP BY subject ORDER BY course_count DESC
        """))
        return [dict(row) for row in result.mappings().all()]

    @classmethod
    async def get_age_group_distribution(cls, db: AsyncSession) -> List[Dict[str, Any]]:
        """年龄段分布统计"""
        result = await db.execute(text("""
            SELECT age_group, COUNT(*) AS user_count
            FROM public.users
            GROUP BY age_group ORDER BY user_count DESC
        """))
        return [dict(row) for row in result.mappings().all()]