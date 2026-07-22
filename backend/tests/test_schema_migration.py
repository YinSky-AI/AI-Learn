"""Schema 版本检查和迁移目标保护。"""

from copy import deepcopy
import os
from types import SimpleNamespace

import pytest
from sqlalchemy import Column, DateTime, MetaData, Numeric, String, Table
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import make_url

import app.main as main_module
from app.admin import routes as admin_routes
from app.core import database as database_module
from app.core.config import Settings
import run as run_module
import migrate_questions as question_importer
import migrate_gamification as legacy_gamification_migration
import link_quiz_lessons as quiz_lesson_linker
import schema_admin as schema_admin_module
from app.models.user import User
from app.models.content import KnowledgeNode, Question
from app.catalog import catalog_metadata
from schema_admin import (
    _audit,
    _normalize_index_predicate,
    build_parser,
    build_expected_contract_snapshot,
    load_database_url,
    remove_allowed_external_contract,
    validate_release_authorization,
    validate_contract_snapshot,
    validate_migration_action,
    validate_table_ownership,
)
from app.core.schema_version import (
    SchemaVersionError,
    enforce_schema_revision,
    evaluate_schema_revision,
    get_expected_schema_revision,
    get_schema_version_table,
    validate_migration_target,
    verify_schema_target,
    verify_schema_targets,
)


DISPOSABLE_URL = (
    "postgresql+asyncpg://postgres:secret@postgres-test:5432/"
    "learning_platform_test"
)


def test_migration_target_accepts_only_the_verified_primary_disposable_database():
    target = validate_migration_target(
        DISPOSABLE_URL,
        target_alias="primary",
        environment="local",
        expected_host="postgres-test",
        expected_database="learning_platform_test",
    )

    assert target.host == "postgres-test"
    assert target.database == "learning_platform_test"
    assert target.environment == "local"
    assert target.alias == "primary"
    assert "secret" not in repr(target)


@pytest.mark.parametrize(
    (
        "database_url",
        "target_alias",
        "environment",
        "expected_host",
        "expected_database",
        "message",
    ),
    [
        (
            "postgresql+asyncpg://postgres:secret@postgres:5432/learning_platform",
            "primary",
            "local",
            "postgres",
            "learning_platform",
            "可丢弃",
        ),
        (
            "postgresql+asyncpg://postgres:secret@postgres-test:5432/ai_learn_test",
            "primary",
            "local",
            "postgres-test",
            "ai_learn_test",
            "题库",
        ),
        (
            DISPOSABLE_URL,
            "primary",
            "production",
            "postgres-test",
            "learning_platform_test",
            "非生产",
        ),
        (
            DISPOSABLE_URL,
            "primary",
            "local",
            "postgres-restore",
            "learning_platform_test",
            "目标不一致",
        ),
    ],
)
def test_migration_target_rejects_unapproved_or_cross_database_targets(
    database_url,
    target_alias,
    environment,
    expected_host,
    expected_database,
    message,
):
    with pytest.raises(SchemaVersionError, match=message) as exc_info:
        validate_migration_target(
            database_url,
            target_alias=target_alias,
            environment=environment,
            expected_host=expected_host,
            expected_database=expected_database,
        )

    assert "secret" not in str(exc_info.value)
    assert "postgresql" not in str(exc_info.value)


def test_question_bank_revision_accepts_only_its_own_disposable_database():
    target = validate_migration_target(
        "postgresql+asyncpg://postgres:secret@postgres-test:5432/ai_learn_test",
        target_alias="question-bank",
        environment="ci",
        expected_host="postgres-test",
        expected_database="ai_learn_test",
    )

    assert target.alias == "question-bank"
    assert target.database == "ai_learn_test"

    with pytest.raises(SchemaVersionError, match="主业务库"):
        validate_migration_target(
            DISPOSABLE_URL,
            target_alias="question-bank",
            environment="ci",
            expected_host="postgres-test",
            expected_database="learning_platform_test",
        )


def test_primary_revision_rejects_non_learning_platform_database_names():
    with pytest.raises(SchemaVersionError, match="learning_platform"):
        validate_migration_target(
            "postgresql+asyncpg://postgres:secret@postgres-test:5432/billing_test",
            target_alias="primary",
            environment="ci",
            expected_host="postgres-test",
            expected_database="billing_test",
        )


def test_regular_release_target_requires_explicit_release_authorization():
    url = "postgresql+asyncpg://postgres:secret@postgres:5432/learning_platform"
    with pytest.raises(SchemaVersionError, match="发布"):
        validate_migration_target(
            url,
            target_alias="primary",
            environment="local",
            expected_host="postgres",
            expected_database="learning_platform",
        )

    target = validate_migration_target(
        url,
        target_alias="primary",
        environment="local",
        expected_host="postgres",
        expected_database="learning_platform",
        allow_release=True,
    )
    with pytest.raises(SchemaVersionError, match="审批"):
        validate_release_authorization(
            action="upgrade",
            target=target,
            current_revision="lp_0001_legacy_baseline",
            has_user_tables=True,
            approval_reference=None,
            backup_reference=None,
            confirm_empty_bootstrap=False,
        )
    with pytest.raises(SchemaVersionError, match="备份"):
        validate_release_authorization(
            action="upgrade",
            target=target,
            current_revision="lp_0001_legacy_baseline",
            has_user_tables=True,
            approval_reference="CHG-123",
            backup_reference=None,
            confirm_empty_bootstrap=False,
        )


def test_verified_empty_release_bootstrap_has_a_separate_confirmation_path():
    target = validate_migration_target(
        "postgresql+asyncpg://postgres:secret@postgres:5432/learning_platform_new",
        target_alias="primary",
        environment="staging",
        expected_host="postgres",
        expected_database="learning_platform_new",
        allow_release=True,
    )

    validate_release_authorization(
        action="upgrade",
        target=target,
        current_revision=None,
        has_user_tables=False,
        approval_reference="CHG-124",
        backup_reference=None,
        confirm_empty_bootstrap=True,
    )

    validate_release_authorization(
        action="upgrade",
        target=target,
            current_revision="lp_0006_review_scheduler",
        has_user_tables=True,
        approval_reference="CHG-124",
        backup_reference=None,
        confirm_empty_bootstrap=True,
    )


def test_strict_schema_policy_rejects_an_unversioned_or_stale_database():
    unversioned = evaluate_schema_revision(None, "lp_0002_owned_contract")
    stale = evaluate_schema_revision(
        "lp_0001_legacy_baseline",
        "lp_0002_owned_contract",
    )

    assert not unversioned.compatible
    assert not stale.compatible
    assert "尚未纳入版本管理" in unversioned.message
    assert "lp_0001_legacy_baseline" in stale.message
    assert "lp_0002_owned_contract" in stale.message

    with pytest.raises(SchemaVersionError, match="Schema 版本不匹配"):
        enforce_schema_revision(stale, policy="strict")


def test_warn_schema_policy_reports_but_does_not_mutate_or_raise():
    status = evaluate_schema_revision(None, "lp_0002_owned_contract")

    returned = enforce_schema_revision(
        status,
        policy="warn",
        legacy_contract_validated=True,
    )

    assert returned is status
    assert not returned.compatible


def test_unknown_schema_policy_is_rejected_with_plain_text():
    status = evaluate_schema_revision(
        "lp_0002_owned_contract",
        "lp_0002_owned_contract",
    )

    with pytest.raises(SchemaVersionError, match="strict 或 warn"):
        enforce_schema_revision(status, policy="automatic")


def test_two_database_targets_publish_independent_revision_heads():
    assert get_expected_schema_revision("primary") == "lp_0006_review_scheduler"
    assert get_expected_schema_revision("question-bank") == "catalog_0002_admin_recovery"
    assert get_schema_version_table("primary") == "alembic_version_learning"
    assert get_schema_version_table("question-bank") == "alembic_version_catalog"

    with pytest.raises(SchemaVersionError, match="目标别名"):
        get_expected_schema_revision("unknown")


def test_owned_schema_keeps_admin_flag_non_nullable():
    assert User.__table__.c.is_admin.nullable is False


def test_admin_question_bank_uses_the_canonical_session_factory():
    assert admin_routes.AiLearnSessionLocal is database_module.AI_LearnAsyncSessionLocal


def test_question_importer_reuses_versioned_primary_table_contracts():
    assert question_importer.knowledge_nodes_table is KnowledgeNode.__table__
    assert question_importer.questions_table is Question.__table__


def test_question_importer_describes_target_without_credentials():
    description = question_importer.describe_database_target(
        "postgresql+asyncpg://student:sentinel-secret@postgres-test:5432/"
        "learning_platform_test"
    )

    assert description == "host=postgres-test database=learning_platform_test"
    assert "sentinel-secret" not in description
    assert "student" not in description


def test_legacy_gamification_schema_script_is_a_non_mutating_shim(capsys):
    result = legacy_gamification_migration.main()

    assert result == 2
    diagnostics = capsys.readouterr()
    assert "schema_admin.py" in diagnostics.err
    assert "ALTER TABLE" not in diagnostics.err


@pytest.mark.asyncio
async def test_question_importer_requires_primary_head_before_dml(monkeypatch):
    calls = []

    async def fake_verify(engine, target_alias, *, policy):
        calls.append((engine, target_alias, policy))

    monkeypatch.setattr(
        question_importer,
        "verify_schema_target",
        fake_verify,
        raising=False,
    )

    await question_importer.ensure_schema_ready()

    assert calls == [(question_importer.engine, "primary", "strict")]


def test_question_importer_runner_returns_plain_text_on_schema_failure(
    monkeypatch,
    capsys,
):
    async def reject():
        raise SchemaVersionError("primary revision 未批准")

    monkeypatch.setattr(question_importer, "ensure_schema_ready", reject)

    assert question_importer.run() == 2
    diagnostics = capsys.readouterr()
    assert "primary revision 未批准" in diagnostics.err
    assert "Traceback" not in diagnostics.err
    assert "postgresql" not in diagnostics.err


@pytest.mark.asyncio
async def test_quiz_lesson_linker_requires_primary_head_before_dml(monkeypatch):
    calls = []

    async def fake_verify(engine, target_alias, *, policy):
        calls.append((engine, target_alias, policy))

    monkeypatch.setattr(quiz_lesson_linker, "verify_schema_target", fake_verify)
    target_engine = object()

    await quiz_lesson_linker.ensure_schema_ready(target_engine)

    assert calls == [(target_engine, "primary", "strict")]
    assert quiz_lesson_linker.DATABASE_URL == database_module.settings.DATABASE_URL


def test_quiz_lesson_linker_returns_plain_text_on_schema_failure(monkeypatch, capsys):
    async def reject():
        raise SchemaVersionError("primary revision 未批准")

    monkeypatch.setattr(quiz_lesson_linker, "link_quiz_lessons", reject)

    assert quiz_lesson_linker.run() == 2
    diagnostics = capsys.readouterr()
    assert "primary revision 未批准" in diagnostics.err
    assert "Traceback" not in diagnostics.err
    assert "postgresql" not in diagnostics.err


def test_baseline_adoption_and_destructive_downgrade_require_explicit_flags():
    with pytest.raises(SchemaVersionError, match="基线采用"):
        validate_migration_action(
            "adopt-baseline",
            target_alias="primary",
            revision=None,
            allow_baseline_adoption=False,
            allow_destructive_downgrade=False,
        )

    with pytest.raises(SchemaVersionError, match="破坏性降级"):
        validate_migration_action(
            "downgrade",
            target_alias="primary",
            revision="base",
            allow_baseline_adoption=False,
            allow_destructive_downgrade=False,
        )

    validate_migration_action(
        "adopt-baseline",
        target_alias="primary",
        revision=None,
        allow_baseline_adoption=True,
        allow_destructive_downgrade=False,
    )
    validate_migration_action(
        "downgrade",
        target_alias="primary",
        revision="base",
        allow_baseline_adoption=False,
        allow_destructive_downgrade=True,
    )


@pytest.mark.parametrize(
    "revision",
    [
        "-1",
        "+1",
        "head",
        "heads",
        "head-1",
        "lp_0002_owned_contract-1",
        "lp_0002_owned_contract-2",
        "lp_0001",
        "catalog_0001_baseline",
    ],
)
def test_downgrade_accepts_only_an_exact_revision_from_the_selected_root(revision):
    with pytest.raises(SchemaVersionError, match="显式 revision"):
        validate_migration_action(
            "downgrade",
            target_alias="primary",
            revision=revision,
            allow_baseline_adoption=False,
            allow_destructive_downgrade=True,
        )


def test_every_downgrade_requires_destructive_confirmation_then_accepts_exact_revisions():
    with pytest.raises(SchemaVersionError, match="破坏性降级确认"):
        validate_migration_action(
            "downgrade",
            target_alias="primary",
            revision="lp_0001_legacy_baseline",
            allow_baseline_adoption=False,
            allow_destructive_downgrade=False,
        )
    validate_migration_action(
        "downgrade",
        target_alias="primary",
        revision="lp_0001_legacy_baseline",
        allow_baseline_adoption=False,
        allow_destructive_downgrade=True,
    )
    validate_migration_action(
        "downgrade",
        target_alias="question-bank",
        revision="catalog_0001_baseline",
        allow_baseline_adoption=False,
        allow_destructive_downgrade=True,
    )


def test_database_url_is_accepted_only_from_a_secret_file(tmp_path):
    secret_file = tmp_path / "database_url"
    secret_file.write_text(DISPOSABLE_URL + "\n", encoding="utf-8")

    args = build_parser().parse_args(
        [
            "current",
            "--target",
            "primary",
            "--database-url-file",
            str(secret_file),
            "--environment",
            "local",
            "--expected-host",
            "postgres-test",
            "--expected-database",
            "learning_platform_test",
        ]
    )
    assert load_database_url(args.database_url_file) == DISPOSABLE_URL

    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "current",
                "--target",
                "primary",
                "--database-url",
                DISPOSABLE_URL,
                "--environment",
                "local",
                "--expected-host",
                "postgres-test",
                "--expected-database",
                "learning_platform_test",
            ]
        )


def test_database_url_secret_file_rejects_multiline_or_symlink(tmp_path):
    multiline = tmp_path / "multiline"
    multiline.write_text(DISPOSABLE_URL + "\nunexpected\n", encoding="utf-8")
    with pytest.raises(SchemaVersionError, match="单行"):
        load_database_url(str(multiline))

    link = tmp_path / "url-link"
    try:
        link.symlink_to(multiline)
    except OSError:
        pytest.skip("当前测试环境不允许创建符号链接")
    with pytest.raises(SchemaVersionError, match="符号链接"):
        load_database_url(str(link))


def test_application_settings_load_database_urls_from_secret_files(tmp_path):
    primary_file = tmp_path / "primary-url"
    catalog_file = tmp_path / "catalog-url"
    primary_file.write_text(DISPOSABLE_URL + "\n", encoding="utf-8")
    catalog_url = (
        "postgresql+asyncpg://postgres:secret@postgres-test:5432/ai_learn_test"
    )
    catalog_file.write_text(catalog_url + "\n", encoding="utf-8")

    loaded = Settings(
        _env_file=None,
        DATABASE_URL_FILE=str(primary_file),
        AI_LEARN_DATABASE_URL_FILE=str(catalog_file),
    )

    assert loaded.DATABASE_URL == DISPOSABLE_URL
    assert loaded.AI_LEARN_DATABASE_URL == catalog_url


def test_application_settings_reject_direct_and_file_database_url_together(tmp_path):
    primary_file = tmp_path / "primary-url"
    primary_file.write_text(DISPOSABLE_URL + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="不得同时提供"):
        Settings(
            _env_file=None,
            DATABASE_URL=DISPOSABLE_URL,
            DATABASE_URL_FILE=str(primary_file),
        )


def _complete_contract_snapshot():
    return {
        "columns": {
            "id": {
                "type": "UUID",
                "nullable": False,
                "default": "uuid_generate_v4()",
            },
            "code": {
                "type": "VARCHAR(20)",
                "nullable": False,
                "default": "'active'",
            },
        },
        "primary_key": ("id",),
        "foreign_keys": {
            (("code",), "statuses", ("code",), "CASCADE"),
        },
        "uniques": {("code",)},
        "indexes": {("idx_contract_code", ("code",), False, None)},
        "required_named_unique_indexes": {
            ("uq_contract_code", ("code",)),
        },
        "checks": {"code <> ''"},
    }


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda value: value["columns"]["code"].update(type="VARCHAR(10)"),
            "类型",
        ),
        (
            lambda value: value["columns"]["code"].update(default="'disabled'"),
            "default",
        ),
        (lambda value: value.update(primary_key=()), "主键"),
        (lambda value: value.update(foreign_keys=set()), "外键"),
        (lambda value: value.update(uniques=set()), "唯一"),
        (lambda value: value.update(indexes=set()), "索引"),
        (
            lambda value: value.update(
                required_named_unique_indexes={("uq_wrong_name", ("code",))}
            ),
            "命名唯一索引",
        ),
        (lambda value: value.update(checks=set()), "check"),
        (
            lambda value: value.update(
                foreign_keys={(("code",), "statuses", ("code",), "SET NULL")}
            ),
            "ON DELETE",
        ),
    ],
)
def test_baseline_contract_rejects_exact_schema_drift(mutate, message):
    expected = _complete_contract_snapshot()
    actual = deepcopy(expected)
    mutate(actual)

    with pytest.raises(SchemaVersionError, match=message):
        validate_contract_snapshot("contract_table", expected, actual)


def test_baseline_contract_accepts_an_exact_match():
    contract = _complete_contract_snapshot()

    validate_contract_snapshot("contract_table", contract, deepcopy(contract))


def test_expected_contract_preserves_precision_timezone_and_array_item_type():
    metadata = MetaData()
    table = Table(
        "typed_contract",
        metadata,
        Column("amount", Numeric(10, 2), nullable=False),
        Column("occurred_at", DateTime(timezone=True), nullable=False),
        Column("tags", ARRAY(String(12)), nullable=False),
    )

    snapshot = build_expected_contract_snapshot(table)

    assert snapshot["columns"]["amount"]["type"] == "NUMERIC(10, 2)"
    assert snapshot["columns"]["occurred_at"]["type"] == "TIMESTAMP WITH TIME ZONE"
    assert snapshot["columns"]["tags"]["type"] == "VARCHAR(12)[]"
    quality_check = build_expected_contract_snapshot(
        User.metadata.tables["question_quality_checks"]
    )
    assert quality_check["columns"]["score"]["type"] == "DOUBLE PRECISION"


def test_catalog_tags_canonical_type_matches_current_text_array():
    snapshot = build_expected_contract_snapshot(catalog_metadata.tables["questions"])
    stats_snapshot = build_expected_contract_snapshot(
        catalog_metadata.tables["question_stats"]
    )

    assert snapshot["columns"]["tags"]["type"] == "TEXT[]"
    assert snapshot["columns"]["estimated_difficulty"]["type"] == "NUMERIC(3, 2)"
    assert stats_snapshot["columns"]["correct_rate"]["type"] == "NUMERIC(5, 2)"
    assert stats_snapshot["columns"]["question_id"]["default"] is None
    question_knowledge = build_expected_contract_snapshot(
        catalog_metadata.tables["question_knowledge"]
    )
    assert question_knowledge["columns"]["question_id"]["default"] is None
    assert question_knowledge["columns"]["knowledge_point_id"]["default"] is None
    assert question_knowledge["indexes"] == {
        ("idx_qk_primary", ("question_id",), False, None, "is_primary = true")
    }


def test_expected_contract_normalizes_default_index_method_to_none():
    snapshot = build_expected_contract_snapshot(User.__table__)

    assert {value[3] for value in snapshot["indexes"]} == {None}


def test_index_predicate_normalizes_postgres_boolean_keyword_case():
    assert _normalize_index_predicate(
        "(is_primary IS TRUE)", "question_knowledge"
    ) == "is_primary = true"
    assert _normalize_index_predicate(
        "is_primary = false", "question_knowledge"
    ) == "is_primary = false"


def test_external_column_whitelist_removes_only_its_own_constraints():
    snapshot = {
        "columns": {"email": {}, "ruoyi_user_id": {}},
        "uniques": {("email",), ("ruoyi_user_id",)},
        "required_named_unique_indexes": {
            ("users_email_key", ("email",)),
            ("users_ruoyi_user_id_key", ("ruoyi_user_id",)),
        },
    }

    remove_allowed_external_contract(snapshot, {"ruoyi_user_id"})

    assert set(snapshot["columns"]) == {"email"}
    assert snapshot["uniques"] == {("email",)}
    assert snapshot["required_named_unique_indexes"] == {
        ("users_email_key", ("email",))
    }


def test_expected_contract_supports_literal_string_server_defaults():
    snapshot = build_expected_contract_snapshot(User.__table__)
    learning_session = build_expected_contract_snapshot(
        User.metadata.tables["learning_sessions"]
    )
    gamification_event = build_expected_contract_snapshot(
        User.metadata.tables["gamification_events"]
    )

    assert snapshot["columns"]["total_score"]["default"] == "0"
    assert snapshot["columns"]["created_at"]["default"] == "now()"
    assert learning_session["columns"]["status"]["default"] == "'in_progress'"
    assert gamification_event["columns"]["new_achievements"]["default"] == "'[]'"


def test_schema_audit_is_plain_redacted_text_not_json_or_connection_data(capsys):
    _audit(
        correlation_id="corr-1",
        action="upgrade",
        stage="failed",
        target_alias="primary",
        host="postgres-test\nSELECT secret",
        database="learning_platform_test",
        environment="test",
        revision="lp_0001_legacy_baseline",
        elapsed_ms=12,
        result="failed",
        approval_reference="CHG-1",
        backup_reference="BKP-1",
        rollback_status="transaction_rolled_back",
        error_type="RuntimeError",
    )

    output = capsys.readouterr().err
    assert "schema_audit correlation_id=corr-1" in output
    assert "rollback_status=transaction_rolled_back" in output
    assert "{" not in output and "}" not in output
    assert "postgresql" not in output
    assert "SELECT" not in output
    assert "Traceback" not in output


@pytest.mark.asyncio
async def test_failed_baseline_adoption_rolls_back_stamp_and_schema_changes(
    db_engine,
    monkeypatch,
):
    async_url = db_engine.url.render_as_string(hide_password=False)
    sync_url = make_url(async_url).set(drivername="postgresql+psycopg2")
    sync_engine = create_engine(sync_url)
    config = SimpleNamespace(attributes={})

    with sync_engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS adoption_atomic_sentinel"))

    monkeypatch.setattr(schema_admin_module, "_config", lambda _alias: config)
    monkeypatch.setattr(
        schema_admin_module,
        "validate_legacy_schema",
        lambda _connection, _alias: None,
    )

    def fake_stamp(received_config, _revision):
        received_config.attributes["connection"].execute(
            text("CREATE TABLE adoption_atomic_sentinel(id integer)")
        )

    def fail_upgrade(_config, _revision):
        raise RuntimeError("injected upgrade failure")

    monkeypatch.setattr(schema_admin_module.command, "stamp", fake_stamp)
    monkeypatch.setattr(schema_admin_module.command, "upgrade", fail_upgrade)

    target = validate_migration_target(
        async_url,
        target_alias="primary",
        environment="test",
        expected_host=make_url(async_url).host,
        expected_database=make_url(async_url).database,
    )
    with pytest.raises(RuntimeError, match="injected upgrade failure"):
        schema_admin_module.execute_migration(
            action="adopt-baseline",
            target=target,
            database_url=async_url,
            revision=None,
        )

    with sync_engine.connect() as connection:
        assert connection.execute(
            text("SELECT to_regclass('public.adoption_atomic_sentinel')")
        ).scalar_one() is None
    sync_engine.dispose()


def test_primary_allows_only_named_external_tables_and_catalog_allows_no_unknowns():
    validate_table_ownership(
        target_alias="primary",
        actual_tables={"users", "apscheduler_jobs", "sys_role_dept"},
        required_tables={"users"},
    )

    with pytest.raises(SchemaVersionError, match="未知表"):
        validate_table_ownership(
            target_alias="primary",
            actual_tables={"users", "mystery_table"},
            required_tables={"users"},
        )

    with pytest.raises(SchemaVersionError, match="未知表"):
        validate_table_ownership(
            target_alias="question-bank",
            actual_tables={"questions", "apscheduler_jobs"},
            required_tables={"questions"},
        )


@pytest.mark.asyncio
async def test_schema_guard_checks_both_database_heads_before_startup():
    current = {
        "primary": "lp_0006_review_scheduler",
        "question-bank": "catalog_0002_admin_recovery",
    }

    async def revision_reader(engine, target_alias):
        assert engine == f"{target_alias}-engine"
        return current[target_alias]

    statuses = await verify_schema_targets(
        {
            "primary": "primary-engine",
            "question-bank": "question-bank-engine",
        },
        policy="strict",
        revision_reader=revision_reader,
    )

    assert {status.current_revision for status in statuses} == set(current.values())
    assert all(status.compatible for status in statuses)


@pytest.mark.asyncio
async def test_schema_guard_rejects_when_either_database_is_stale():
    async def revision_reader(_engine, target_alias):
        if target_alias == "primary":
            return "lp_0006_review_scheduler"
        return None

    with pytest.raises(SchemaVersionError, match="question-bank.*尚未纳入版本管理"):
        await verify_schema_targets(
            {"primary": object(), "question-bank": object()},
            policy="strict",
            revision_reader=revision_reader,
        )


@pytest.mark.asyncio
async def test_warn_allows_only_an_unversioned_database_with_a_valid_legacy_contract():
    calls = []

    async def unversioned(_engine, _alias):
        return None

    async def valid_legacy(engine, alias):
        calls.append((engine, alias))

    status = await verify_schema_target(
        "primary-engine",
        "primary",
        policy="warn",
        revision_reader=unversioned,
        legacy_validator=valid_legacy,
    )

    assert not status.compatible
    assert calls == [("primary-engine", "primary")]


@pytest.mark.asyncio
async def test_warn_rejects_an_empty_or_drifted_unversioned_database():
    async def unversioned(_engine, _alias):
        return None

    async def invalid_legacy(_engine, _alias):
        raise SchemaVersionError("基线结构缺少受管理表")

    with pytest.raises(SchemaVersionError, match="缺少受管理表"):
        await verify_schema_target(
            object(),
            "primary",
            policy="warn",
            revision_reader=unversioned,
            legacy_validator=invalid_legacy,
        )


@pytest.mark.asyncio
async def test_warn_rejects_stale_revision_without_running_legacy_validator():
    validator_called = False

    async def stale(_engine, _alias):
        return "lp_0001_legacy_baseline"

    async def must_not_validate(_engine, _alias):
        nonlocal validator_called
        validator_called = True

    with pytest.raises(SchemaVersionError, match="current=lp_0001_legacy_baseline"):
        await verify_schema_target(
            object(),
            "primary",
            policy="warn",
            revision_reader=stale,
            legacy_validator=must_not_validate,
        )

    assert validator_called is False


@pytest.mark.asyncio
async def test_application_lifespan_only_checks_both_schema_heads(monkeypatch):
    calls = []
    primary_engine = object()
    question_bank_engine = object()

    async def fake_verify(engines, *, policy):
        calls.append((engines, policy))
        return [
            evaluate_schema_revision(
                "lp_0002_owned_contract", "lp_0002_owned_contract"
            ),
            evaluate_schema_revision(
                "catalog_0001_baseline", "catalog_0001_baseline"
            ),
        ]

    async def noop():
        return None

    monkeypatch.setattr(main_module, "verify_schema_targets", fake_verify, raising=False)
    monkeypatch.setattr(main_module.settings, "SCHEMA_VERSION_POLICY", "strict")
    monkeypatch.setattr(main_module, "engine", primary_engine)
    monkeypatch.setattr(main_module, "ai_learn_engine", question_bank_engine, raising=False)
    monkeypatch.setattr(main_module.redis_client, "init", noop)
    monkeypatch.setattr(main_module.redis_client, "close", noop)

    async with main_module.lifespan(main_module.app):
        pass

    assert calls == [
        (
            {"primary": primary_engine, "question-bank": question_bank_engine},
            "strict",
        )
    ]


@pytest.mark.asyncio
async def test_process_launcher_preflights_both_databases(monkeypatch):
    calls = []

    async def fake_verify(engines, *, policy):
        calls.append((set(engines), policy))
        return []

    monkeypatch.setattr(run_module, "verify_schema_targets", fake_verify, raising=False)
    monkeypatch.setattr(run_module.settings, "SCHEMA_VERSION_POLICY", "strict")

    await run_module.preflight_schema()

    assert calls == [({"primary", "question-bank"}, "strict")]


def test_process_launcher_returns_plain_text_when_preflight_fails(monkeypatch, capsys):
    async def reject():
        raise SchemaVersionError("question-bank revision 未批准")

    monkeypatch.setattr(run_module, "preflight_schema", reject, raising=False)
    monkeypatch.setattr(
        run_module.uvicorn,
        "run",
        lambda *args, **kwargs: pytest.fail("错版时不得启动 Uvicorn"),
    )

    assert run_module.main() == 2
    diagnostics = capsys.readouterr()
    assert "question-bank revision 未批准" in diagnostics.err
    assert "Traceback" not in diagnostics.err
    assert "postgresql" not in diagnostics.err
