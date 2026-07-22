"""pytest 共享 fixtures"""
import os
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.schema_version import SchemaVersionError, validate_test_database_target


def _test_database_url() -> str:
    file_value = os.getenv("TEST_DATABASE_URL_FILE")
    if not file_value:
        raise RuntimeError("后端测试必须通过 TEST_DATABASE_URL_FILE 提供可丢弃测试库")
    path = Path(file_value)
    if not path.is_absolute() or path.is_symlink():
        raise RuntimeError("TEST_DATABASE_URL_FILE 必须是绝对路径普通文件")
    try:
        if not path.is_file() or path.stat().st_size > 4096:
            raise RuntimeError("TEST_DATABASE_URL_FILE 文件无效")
        raw_value = path.read_text(encoding="utf-8")
    except RuntimeError:
        raise
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("TEST_DATABASE_URL_FILE 不可读") from exc
    if raw_value.startswith("\ufeff"):
        raise RuntimeError("TEST_DATABASE_URL_FILE 禁止包含 UTF-8 BOM")
    lines = raw_value.splitlines()
    if len(lines) != 1 or not lines[0].strip():
        raise RuntimeError("TEST_DATABASE_URL_FILE 必须是非空单行文件")
    database_url = lines[0].strip()
    try:
        validate_test_database_target(
            database_url,
            os.getenv("DELIVERY_TEST_ENV", "local"),
        )
    except SchemaVersionError as exc:
        raise RuntimeError(str(exc)) from exc
    return database_url


TEST_DATABASE_URL = _test_database_url()
os.environ["DATABASE_URL_FILE"] = os.environ["TEST_DATABASE_URL_FILE"]

from app.main import app  # noqa: E402
from app.core.database import get_db
from app.models import Base

engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine():
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    table_names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    async with db_engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()
    async with db_engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
