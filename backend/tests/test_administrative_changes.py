"""管理删除必须可恢复、可审计，并保留关联学习数据。"""

from pathlib import Path
import uuid

import pytest
from sqlalchemy import text

from app.services.admin_changes import AdminChangeService
from app.services import course_service
from app.core.database import AI_LearnAsyncSessionLocal


@pytest.mark.asyncio
async def test_course_soft_delete_and_restore_preserve_learning_rows(db_session):
    actor_id = uuid.uuid4()
    user_id = uuid.uuid4()
    course_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO users (id, nickname, email, password_hash, birth_date, age_group, is_admin) "
            "VALUES (:id, '学习者', :email, 'hash', DATE '2012-01-01', 'AGE_10_12', false)"
        ),
        {"id": user_id, "email": f"p003-{user_id}@example.test"},
    )
    await db_session.execute(
        text(
            "INSERT INTO courses (id, title, subject, age_group, difficulty, duration, rating, "
            "enroll_count, total_lessons, is_active, sort_order) "
            "VALUES (:id, '可恢复课程', 'math', 'AGE_10_12', 'beginner', 0, 4.0, 0, 0, true, 0)"
        ),
        {"id": course_id},
    )
    await db_session.execute(
        text(
            "INSERT INTO user_courses (id, user_id, course_id, progress, completed_lessons, status) "
            "VALUES (:id, :user_id, :course_id, 50, 1, 'enrolled')"
        ),
        {"id": uuid.uuid4(), "user_id": user_id, "course_id": course_id},
    )
    await course_service.save_chat_message(
        db_session, str(user_id), "user", "保留的课程聊天", course_id=str(course_id)
    )

    service = AdminChangeService(db_session)
    removed = await service.change(
        action="soft_delete",
        entity_type="course",
        entity_id=str(course_id),
        actor_id=actor_id,
        reason="课程内容需要暂时下线复核",
        request_id="p003-delete",
    )
    assert removed.changed is True
    assert removed.impact_scope["user_courses"] == 1
    assert removed.impact_scope["chat_messages"] == 1
    assert (
        await db_session.execute(
            text("SELECT COUNT(*) FROM user_courses WHERE course_id = :id"),
            {"id": course_id},
        )
    ).scalar_one() == 1
    hidden_courses = await course_service.list_courses(db_session, page=1, page_size=20)
    assert all(str(item.id) != str(course_id) for item in hidden_courses["items"])
    hidden_user_courses = await course_service.get_user_courses(
        db_session, str(user_id), page=1, page_size=20
    )
    assert hidden_user_courses["total"] == 0
    hidden_chat = await course_service.get_chat_history(
        db_session, str(user_id), course_id=str(course_id)
    )
    assert hidden_chat["total"] == 0
    with pytest.raises(ValueError, match="课程不存在"):
        await course_service.save_chat_message(
            db_session, str(user_id), "user", "不得写入已停用课程", course_id=str(course_id)
        )

    restored = await service.change(
        action="restore",
        entity_type="course",
        entity_id=str(course_id),
        actor_id=actor_id,
        reason="复核完成，恢复课程访问",
        request_id="p003-restore",
    )
    assert restored.changed is True
    assert (
        await db_session.execute(
            text("SELECT deleted_at FROM courses WHERE id = :id"), {"id": course_id}
        )
    ).scalar_one() is None
    visible_user_courses = await course_service.get_user_courses(
        db_session, str(user_id), page=1, page_size=20
    )
    assert visible_user_courses["total"] == 1

    audits = (
        await db_session.execute(
            text(
                "SELECT action, actor_id, reason, before_summary, after_summary, impact_scope "
                "FROM admin_change_audits WHERE entity_id = :id ORDER BY created_at"
            ),
            {"id": str(course_id)},
        )
    ).mappings().all()
    assert [row["action"] for row in audits] == ["soft_delete", "restore"]
    assert all(row["actor_id"] == actor_id for row in audits)
    assert all(row["reason"] for row in audits)
    assert audits[0]["before_summary"]["state"] == "active"
    assert audits[0]["after_summary"]["state"] == "deleted"


@pytest.mark.asyncio
async def test_duplicate_change_is_rejected_and_audited(db_session):
    actor_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO users (id, nickname, email, password_hash, birth_date, age_group, is_admin) "
            "VALUES (:id, '待停用', :email, 'hash', DATE '2012-01-01', 'AGE_10_12', false)"
        ),
        {"id": user_id, "email": f"p003-duplicate-{user_id}@example.test"},
    )
    service = AdminChangeService(db_session)
    first = await service.change(
        action="soft_delete", entity_type="user", entity_id=str(user_id),
        actor_id=actor_id, reason="账号由监护人申请暂时停用", request_id="first",
    )
    duplicate = await service.change(
        action="soft_delete", entity_type="user", entity_id=str(user_id),
        actor_id=actor_id, reason="重复请求不得重复变更", request_id="duplicate",
    )
    assert first.changed is True
    assert duplicate.changed is False
    assert duplicate.status == "rejected"
    rows = (
        await db_session.execute(
            text("SELECT status FROM admin_change_audits WHERE entity_id=:id ORDER BY created_at"),
            {"id": str(user_id)},
        )
    ).scalars().all()
    assert rows == ["succeeded", "rejected"]


@pytest.mark.asyncio
async def test_invalid_management_request_is_rejected_and_audited(db_session):
    actor_id = uuid.uuid4()
    target_id = uuid.uuid4()
    service = AdminChangeService(db_session)
    with pytest.raises(ValueError, match="不支持"):
        await service.change(
            action="purge", entity_type="course", entity_id="not-a-uuid",
            actor_id=actor_id, reason="未授权的清理尝试", request_id="invalid-action",
        )
    row = (
        await db_session.execute(
            text(
                "SELECT actor_id, action, status, reason FROM admin_change_audits "
                "WHERE request_id='invalid-action'"
            )
        )
    ).mappings().one()
    assert row["actor_id"] == actor_id
    assert row["action"] == "purge"
    assert row["status"] == "rejected"

    with pytest.raises(ValueError, match="5 到 500"):
        await service.change(
            action="restore", entity_type="user", entity_id=str(target_id),
            actor_id=actor_id, reason="短", request_id="invalid-reason",
        )
    rejected_reason = (
        await db_session.execute(
            text("SELECT reason FROM admin_change_audits WHERE request_id='invalid-reason'")
        )
    ).scalar_one()
    assert rejected_reason == "[未提供有效原因]"


@pytest.mark.asyncio
async def test_lesson_soft_delete_and_restore_recalculate_active_lesson_count(db_session):
    actor_id = uuid.uuid4()
    course_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO courses (id, title, subject, age_group, difficulty, duration, rating, "
            "enroll_count, total_lessons, is_active, sort_order) "
            "VALUES (:id, '课时计数课程', 'math', 'AGE_10_12', 'beginner', 0, 4.0, 0, 1, true, 0)"
        ),
        {"id": course_id},
    )
    await db_session.execute(
        text(
            'INSERT INTO lessons (id, course_id, title, type, duration, "order", is_active) '
            "VALUES (:id, :course_id, '可恢复课时', 'video', 10, 1, true)"
        ),
        {"id": lesson_id, "course_id": course_id},
    )
    service = AdminChangeService(db_session)

    await service.change(
        action="soft_delete", entity_type="lesson", entity_id=str(lesson_id),
        actor_id=actor_id, reason="课时内容需要暂时下线复核", request_id="lesson-delete",
    )
    assert (
        await db_session.execute(text("SELECT total_lessons FROM courses WHERE id=:id"), {"id": course_id})
    ).scalar_one() == 0
    with pytest.raises(ValueError, match="课时不存在"):
        await course_service.complete_lesson(
            db_session, str(uuid.uuid4()), str(lesson_id), time_spent_seconds=10
        )

    await service.change(
        action="restore", entity_type="lesson", entity_id=str(lesson_id),
        actor_id=actor_id, reason="课时内容复核完成并恢复", request_id="lesson-restore",
    )
    assert (
        await db_session.execute(text("SELECT total_lessons FROM courses WHERE id=:id"), {"id": course_id})
    ).scalar_one() == 1


@pytest.mark.asyncio
async def test_catalog_question_soft_delete_restore_and_audit_use_catalog_database():
    actor_id = uuid.uuid4()
    async with AI_LearnAsyncSessionLocal() as catalog_db:
        question_id = (await catalog_db.execute(
            text(
                "INSERT INTO questions "
                "(subject, age_group, difficulty, content, correct_answer, explanation, type) "
                "VALUES ('math', 'AGE_10_12', 'beginner', '可恢复题目', '1', '解释', 'fill_blank') "
                "RETURNING id"
            )
        )).scalar_one()
        service = AdminChangeService(catalog_db)
        await service.change(
            action="soft_delete", entity_type="question", entity_id=str(question_id),
            actor_id=actor_id, reason="题目内容需要暂时下线复核", request_id="catalog-delete",
        )
        assert (await catalog_db.execute(
            text("SELECT deleted_at IS NOT NULL FROM questions WHERE id=:id"), {"id": question_id}
        )).scalar_one() is True
        await service.change(
            action="restore", entity_type="question", entity_id=str(question_id),
            actor_id=actor_id, reason="题目内容复核完成并恢复", request_id="catalog-restore",
        )
        assert (await catalog_db.execute(
            text("SELECT COUNT(*) FROM admin_change_audits WHERE entity_id=:id"), {"id": str(question_id)}
        )).scalar_one() == 2
        await catalog_db.rollback()


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_the_soft_delete(db_session, monkeypatch):
    course_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO courses (id, title, subject, age_group, difficulty, duration, rating, "
            "enroll_count, total_lessons, is_active, sort_order) "
            "VALUES (:id, '回滚课程', 'math', 'AGE_10_12', 'beginner', 0, 4.0, 0, 0, true, 0)"
        ),
        {"id": course_id},
    )
    await db_session.commit()
    service = AdminChangeService(db_session)

    async def fail_audit(**_kwargs):
        raise RuntimeError("simulated audit write failure")

    monkeypatch.setattr(service, "_write_audit", fail_audit)
    with pytest.raises(RuntimeError, match="simulated audit"):
        await service.change(
            action="soft_delete", entity_type="course", entity_id=str(course_id),
            actor_id=uuid.uuid4(), reason="验证审计失败会回滚业务变更", request_id="rollback",
        )
    await db_session.rollback()
    assert (await db_session.execute(
        text("SELECT deleted_at FROM courses WHERE id=:id"), {"id": course_id}
    )).scalar_one() is None


def test_admin_routes_have_no_physical_delete_and_expose_restore():
    source = (Path(__file__).resolve().parents[1] / "app" / "admin" / "routes.py").read_text(encoding="utf-8")
    recovery = (Path(__file__).resolve().parents[1] / "app" / "admin" / "templates" / "recovery.html").read_text(encoding="utf-8")
    for table in ("users", "courses", "lessons", "questions"):
        assert f"DELETE FROM public.{table}" not in source
    assert source.count('/restore"') >= 4
    assert "FROM courses WHERE id = :id AND deleted_at IS NULL" in source
    assert 'UPDATE public.questions SET {\', \'.join(updates)} WHERE id = :id AND deleted_at IS NULL' in source
    assert "state=deleted" in recovery
    assert "/restore" in recovery
    assert 'affected_course_ids = {str(original_course_id)' in source


def test_recovery_center_lists_all_soft_deleted_entity_types():
    template = (Path(__file__).resolve().parents[1] / "app" / "admin" / "templates" / "recovery.html").read_text(encoding="utf-8")
    for entity in ("courses", "lessons", "questions", "users"):
        assert f"/admin/{entity}/api/list?state=deleted" in template
    assert "const plural = {course: 'courses', lesson: 'lessons', question: 'questions', user: 'users'}" in template
    assert "/admin/${plural}/api/${id}/restore" in template
