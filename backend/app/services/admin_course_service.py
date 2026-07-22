"""Pure course-management rules shared by admin endpoints."""

import json
from typing import Any

COURSE_UPDATE_FIELDS = (
    "title", "description", "subject", "difficulty", "age_group",
    "duration", "image_url", "is_active", "sort_order", "slug",
)


def serialize_tags(value: Any) -> str | None:
    """Normalize admin tag input to the database JSON representation."""
    if not value:
        return None
    if isinstance(value, str):
        tags = [item.strip() for item in value.split(",") if item.strip()]
    elif isinstance(value, list):
        tags = [str(item).strip() for item in value if str(item).strip()]
    else:
        tags = [str(value).strip()]
    return json.dumps(tags, ensure_ascii=False) if tags else None


def build_course_update(body: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    """Return safe SQL fragments and bound parameters for course edits."""
    updates: list[str] = []
    params: dict[str, Any] = {"id": body.get("id")}
    for field in COURSE_UPDATE_FIELDS:
        if field in body:
            updates.append(f"{field} = :{field}")
            params[field] = body[field] if body[field] != "" else None
    if "tags" in body:
        updates.append("tags = :tags")
        params["tags"] = serialize_tags(body["tags"])
    return updates, params
