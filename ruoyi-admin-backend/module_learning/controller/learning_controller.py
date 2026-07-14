from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession

from config.get_db import get_db
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from module_learning.dao.learning_dao import CourseDao, LearningStatsDao, PlatformUserDao
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil


# ==================== 请求/响应模型 ====================


class CourseStatusModel(BaseModel):
    """课程状态修改模型"""

    model_config = ConfigDict(alias_generator=to_camel)

    course_id: int = Field(..., description='课程ID')
    is_active: bool = Field(..., description='是否上架')


class UpdatePlatformUserModel(BaseModel):
    """修改平台用户模型"""

    model_config = ConfigDict(alias_generator=to_camel)

    user_id: int = Field(..., description='用户ID')
    nickname: Optional[str] = Field(None, description='昵称')
    phone: Optional[str] = Field(None, description='手机号')
    age_group: Optional[str] = Field(None, description='年龄段')
    avatar_url: Optional[str] = Field(None, description='头像地址')


# ==================== 字段映射工具函数 ====================


def map_course_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """将数据库 snake_case 字段映射为前端 camelCase"""
    return {
        'courseId': row.get('id'),
        'courseName': row.get('title'),
        'coverUrl': row.get('image_url'),
        'subject': row.get('subject'),
        'difficulty': row.get('difficulty'),
        'ageGroup': row.get('age_group'),
        'totalLessons': row.get('total_lessons') or row.get('lesson_count', 0),
        'duration': row.get('duration'),
        'enrollmentCount': row.get('enroll_count'),
        'rating': row.get('rating'),
        'isActive': row.get('is_active'),
        'createTime': row.get('created_at'),
        'updateTime': row.get('updated_at'),
        'description': row.get('description'),
        'tags': row.get('tags'),
        'sortOrder': row.get('sort_order'),
        'slug': row.get('slug'),
    }


def map_user_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """将用户数据 snake_case 映射为前端 camelCase"""
    return {
        'userId': row.get('id'),
        'nickname': row.get('nickname'),
        'email': row.get('email'),
        'ageGroup': row.get('age_group'),
        'totalScore': row.get('total_score'),
        'streakDays': row.get('streak_days'),
        'avatarUrl': row.get('avatar_url'),
        'birthDate': row.get('birth_date'),
        'lastLoginDate': row.get('last_login_date'),
        'behaviorProfile': row.get('behavior_profile'),
        'createTime': row.get('created_at'),
        'updateTime': row.get('updated_at'),
        'enrollCount': row.get('enroll_count'),
        'completedLessons': row.get('completed_lessons'),
        'totalStudySeconds': row.get('total_study_seconds'),
    }


# ==================== 路由定义 ====================

router = APIRouter(prefix='/learning', dependencies=[Depends(LoginService.get_current_user)])


# ==================== 课程管理接口 ====================


@router.get('/course/list', response_model=PageResponseModel)
async def get_course_list(
    request: Request,
    page_num: int = Query(default=1, alias='pageNum', description='页码'),
    page_size: int = Query(default=10, alias='pageSize', description='每页数量'),
    course_name: Optional[str] = Query(default=None, alias='courseName', description='课程名称关键词'),
    subject: Optional[str] = Query(default=None, description='学科'),
    difficulty: Optional[str] = Query(default=None, description='难度'),
    age_group: Optional[str] = Query(default=None, alias='ageGroup', description='年龄段'),
    is_active: Optional[bool] = Query(default=None, alias='isActive', description='是否上架'),
    query_db: AsyncSession = Depends(get_db),
):
    """获取课程列表（分页）"""
    query_params = {
        'keyword': course_name,
        'subject': subject,
        'difficulty': difficulty,
        'age_group': age_group,
        'is_active': is_active,
    }
    course_page_result = await CourseDao.get_course_list(query_db, query_params, page_num, page_size, is_page=True)
    # 字段映射
    course_page_result.rows = [map_course_row(row) for row in course_page_result.rows]
    logger.info('获取课程列表成功')
    return ResponseUtil.success(model_content=course_page_result)


@router.get('/course/{course_id}')
async def get_course_detail(
    request: Request,
    course_id: int,
    query_db: AsyncSession = Depends(get_db),
):
    """获取课程详情"""
    course_detail = await CourseDao.get_course_detail(query_db, course_id)
    if not course_detail:
        logger.warning(f'课程ID {course_id} 不存在')
        return ResponseUtil.failure(msg=f'课程ID {course_id} 不存在')
    logger.info(f'获取课程ID {course_id} 详情成功')
    return ResponseUtil.success(data=map_course_row(course_detail))


@router.put('/course/status')
async def update_course_status(
    request: Request,
    course_status: CourseStatusModel,
    query_db: AsyncSession = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """修改课程上下架状态"""
    row_count = await CourseDao.update_course_status(query_db, course_status.course_id, course_status.is_active)
    if row_count <= 0:
        logger.warning(f'课程ID {course_status.course_id} 状态修改失败')
        return ResponseUtil.failure(msg=f'课程ID {course_status.course_id} 不存在或状态未变更')
    await query_db.commit()
    status_text = '上架' if course_status.is_active else '下架'
    logger.info(f'课程ID {course_status.course_id} 已{status_text}')
    return ResponseUtil.success(msg=f'课程{status_text}成功')


@router.delete('/course/{course_id}')
async def delete_course(
    request: Request,
    course_id: int,
    query_db: AsyncSession = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """删除课程"""
    row_count = await CourseDao.delete_course(query_db, course_id)
    if row_count <= 0:
        logger.warning(f'课程ID {course_id} 删除失败')
        return ResponseUtil.failure(msg=f'课程ID {course_id} 不存在')
    await query_db.commit()
    logger.info(f'课程ID {course_id} 删除成功')
    return ResponseUtil.success(msg='删除成功')


# ==================== 平台用户管理接口 ====================


@router.get('/user/list', response_model=PageResponseModel)
async def get_platform_user_list(
    request: Request,
    page_num: int = Query(default=1, alias='pageNum', description='页码'),
    page_size: int = Query(default=10, alias='pageSize', description='每页数量'),
    keyword: Optional[str] = Query(default=None, description='关键词（用户名/昵称/手机号）'),
    age_group: Optional[str] = Query(default=None, alias='ageGroup', description='年龄段'),
    query_db: AsyncSession = Depends(get_db),
):
    """获取平台用户列表（分页）"""
    query_params = {
        'keyword': keyword,
        'age_group': age_group,
    }
    user_page_result = await PlatformUserDao.get_platform_user_list(
        query_db, query_params, page_num, page_size, is_page=True
    )
    # 字段映射
    user_page_result.rows = [map_user_row(row) for row in user_page_result.rows]
    logger.info('获取平台用户列表成功')
    return ResponseUtil.success(model_content=user_page_result)


@router.get('/user/{user_id}')
async def get_platform_user_detail(
    request: Request,
    user_id: int,
    query_db: AsyncSession = Depends(get_db),
):
    """获取平台用户详情"""
    user_detail = await PlatformUserDao.get_platform_user_detail(query_db, user_id)
    if not user_detail:
        logger.warning(f'平台用户ID {user_id} 不存在')
        return ResponseUtil.failure(msg=f'用户ID {user_id} 不存在')
    logger.info(f'获取平台用户ID {user_id} 详情成功')
    return ResponseUtil.success(data=map_user_row(user_detail))


@router.put('/user')
async def update_platform_user(
    request: Request,
    update_user: UpdatePlatformUserModel,
    query_db: AsyncSession = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """修改平台用户信息"""
    update_data = update_user.model_dump(exclude={'user_id'}, exclude_none=True, by_alias=False)
    if not update_data:
        return ResponseUtil.failure(msg='未提供需要修改的字段')

    row_count = await PlatformUserDao.update_platform_user(query_db, update_user.user_id, update_data)
    if row_count <= 0:
        logger.warning(f'平台用户ID {update_user.user_id} 修改失败')
        return ResponseUtil.failure(msg=f'用户ID {update_user.user_id} 不存在或信息未变更')
    await query_db.commit()
    logger.info(f'平台用户ID {update_user.user_id} 修改成功')
    return ResponseUtil.success(msg='修改成功')


@router.delete('/user/{user_id}')
async def delete_platform_user(
    request: Request,
    user_id: int,
    query_db: AsyncSession = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """删除平台用户"""
    row_count = await PlatformUserDao.delete_platform_user(query_db, user_id)
    if row_count <= 0:
        logger.warning(f'平台用户ID {user_id} 删除失败')
        return ResponseUtil.failure(msg=f'用户ID {user_id} 不存在')
    await query_db.commit()
    logger.info(f'平台用户ID {user_id} 删除成功')
    return ResponseUtil.success(msg='删除成功')


# ==================== 学习统计接口 ====================


@router.get('/stats/overview')
async def get_stats_overview(
    request: Request,
    query_db: AsyncSession = Depends(get_db),
):
    """获取学习平台总览统计"""
    course_stats = await CourseDao.get_course_stats(query_db)
    user_stats = await PlatformUserDao.get_user_stats_overview(query_db)
    learning_stats = await LearningStatsDao.get_learning_stats(query_db)

    result = {
        'course_stats': course_stats,
        'user_stats': user_stats,
        'learning_stats': learning_stats,
    }
    logger.info('获取学习平台总览统计成功')
    return ResponseUtil.success(data=result)


@router.get('/stats/daily-active')
async def get_daily_active_users(
    request: Request,
    days: int = Query(default=30, description='统计天数'),
    query_db: AsyncSession = Depends(get_db),
):
    """获取近N天每日活跃用户数"""
    daily_active = await LearningStatsDao.get_daily_active_users(query_db, days)
    logger.info(f'获取近{days}天每日活跃用户数成功')
    return ResponseUtil.success(data=daily_active)


@router.get('/stats/course-ranking')
async def get_course_ranking(
    request: Request,
    limit: int = Query(default=10, description='排行数量'),
    query_db: AsyncSession = Depends(get_db),
):
    """获取课程报名排行"""
    ranking = await LearningStatsDao.get_course_enroll_ranking(query_db, limit)
    # 课程排行也需要字段映射
    ranking = [map_course_row(row) for row in ranking]
    logger.info(f'获取课程报名排行TOP{limit}成功')
    return ResponseUtil.success(data=ranking)


@router.get('/stats/subject-dist')
async def get_subject_distribution(
    request: Request,
    query_db: AsyncSession = Depends(get_db),
):
    """获取学科分布统计"""
    subject_dist = await LearningStatsDao.get_subject_distribution(query_db)
    logger.info('获取学科分布统计成功')
    return ResponseUtil.success(data=subject_dist)