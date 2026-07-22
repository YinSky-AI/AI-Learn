from app.services.admin_course_service import build_course_update, serialize_tags


def test_serialize_tags_normalizes_supported_admin_inputs():
    assert serialize_tags("math, science, ") == '["math", "science"]'
    assert serialize_tags(["math", " science "]) == '["math", "science"]'
    assert serialize_tags("") is None


def test_build_course_update_only_allows_course_fields_and_binds_values():
    updates, params = build_course_update({"id": "course-1", "title": "New", "tags": "a,b", "deleted_at": "x"})
    assert updates == ["title = :title", "tags = :tags"]
    assert params == {"id": "course-1", "title": "New", "tags": '["a", "b"]'}
