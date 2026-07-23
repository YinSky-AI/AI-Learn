from app.models import Base
from migrations.runtime import run_migrations


EXTERNAL_TABLES = {"apscheduler_jobs", "sys_role_dept"}


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and reflected and name in EXTERNAL_TABLES:
        return False
    if type_ == "column" and reflected and name == "ruoyi_user_id" and obj.table.name == "users":
        return False
    if type_ == "index" and reflected and name == "users_ruoyi_user_id_key":
        return False
    return True


run_migrations(
    target_alias="primary",
    target_metadata=Base.metadata,
    version_table="alembic_version_learning",
    include_object=include_object,
)
