from app.catalog import catalog_metadata
from migrations.runtime import run_migrations


run_migrations(
    target_alias="question-bank",
    target_metadata=catalog_metadata,
    version_table="alembic_version_catalog",
)
