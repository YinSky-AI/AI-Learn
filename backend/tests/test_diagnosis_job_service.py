import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.dialects import postgresql

import app.services.diagnosis_job_service as diagnosis_service
from app.models.adaptive_learning import AnswerDiagnosis
from app.models.adaptive_learning import DiagnosisJob
from app.services.diagnosis_job_service import (
    ClaimedDiagnosisJob,
    DiagnosisAnswerReference,
    claim_diagnosis_job,
    enqueue_diagnosis_job,
    persist_diagnosis_result,
)


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self, results):
        self.results = iter(results)
        self.statements = []
        self.added = []
        self.flushes = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return ScalarResult(next(self.results))

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flushes += 1
        for value in self.added:
            if value.id is None:
                value.id = uuid.uuid4()


def standard_reference() -> DiagnosisAnswerReference:
    return DiagnosisAnswerReference(standard_answer_id=uuid.uuid4())


def test_answer_reference_requires_exactly_one_answer_id():
    """Constructing an ownerless or ambiguous diagnosis job must make this fail."""

    with pytest.raises(ValueError, match="恰好一个"):
        DiagnosisAnswerReference()
    with pytest.raises(ValueError, match="恰好一个"):
        DiagnosisAnswerReference(
            standard_answer_id=uuid.uuid4(),
            generated_answer_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_enqueue_returns_existing_job_for_the_same_answer():
    """Creating a second job for one answer event must make this test fail."""

    existing = DiagnosisJob(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        standard_answer_id=uuid.uuid4(),
        status="queued",
        input_snapshot={},
    )
    session = FakeSession([existing])

    returned = await enqueue_diagnosis_job(
        session,
        DiagnosisAnswerReference(standard_answer_id=existing.standard_answer_id),
        existing.user_id,
        input_snapshot={"is_correct": False},
    )

    assert returned is existing
    assert session.added == []


@pytest.mark.asyncio
async def test_enqueue_persists_one_job_with_a_bounded_snapshot():
    """Dropping the answer reference or snapshot when enqueueing must make this fail."""

    session = FakeSession([None])
    user_id = uuid.uuid4()
    reference = standard_reference()

    job = await enqueue_diagnosis_job(
        session,
        reference,
        user_id,
        input_snapshot={"equation": "2x=8", "solution_steps": ["2x=8", "x=5"]},
    )

    assert job.user_id == user_id
    assert job.standard_answer_id == reference.standard_answer_id
    assert job.generated_answer_id is None
    assert job.status == "queued"
    assert job.input_snapshot["equation"] == "2x=8"
    assert session.added == [job]


@pytest.mark.asyncio
async def test_enqueue_rejects_an_unbounded_snapshot():
    session = FakeSession([None])

    with pytest.raises(ValueError, match="快照过大"):
        await enqueue_diagnosis_job(
            session,
            standard_reference(),
            uuid.uuid4(),
            input_snapshot={"equation": "x=1", "padding": "x" * 20_000},
        )

    assert session.added == []


@pytest.mark.asyncio
async def test_claim_uses_skip_locked_fifo_and_returns_a_detached_dto():
    """Returning a session-bound row or blocking another worker must make this fail."""

    now = datetime.now(timezone.utc)
    row = DiagnosisJob(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        standard_answer_id=uuid.uuid4(),
        status="queued",
        attempts=0,
        max_attempts=3,
        input_snapshot={"equation": "x=4", "is_correct": True, "solution_steps": []},
        created_at=now,
    )
    session = FakeSession([row])

    claimed = await claim_diagnosis_job(session, "worker-1", lease_seconds=90)

    assert isinstance(claimed, ClaimedDiagnosisJob)
    assert claimed.job_id == row.id
    assert claimed.standard_answer_id == row.standard_answer_id
    assert claimed.input_snapshot == row.input_snapshot
    assert row.status == "running"
    assert row.attempts == 1
    assert row.lease_owner == "worker-1"
    assert row.lease_expires_at > now
    sql = str(
        session.statements[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "diagnosis_jobs.created_at" in sql
    assert "diagnosis_jobs.attempts < diagnosis_jobs.max_attempts" in sql
    assert "diagnosis_jobs.lease_expires_at" in sql


@pytest.mark.asyncio
async def test_claim_returns_none_without_mutation_when_queue_is_empty():
    """Inventing work or sleeping inside the claim transaction must make this fail."""

    session = FakeSession([None])

    assert await claim_diagnosis_job(session, "worker-1") is None
    assert session.flushes == 0


class TransactionalSession(FakeSession):
    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return None

    def begin(self):
        return self


class SingleSessionFactory:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self.session


@pytest.mark.asyncio
async def test_existing_diagnosis_completes_retry_without_second_mastery_update(
    monkeypatch,
):
    answer_id = uuid.uuid4()
    claimed = ClaimedDiagnosisJob(
        job_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        standard_answer_id=answer_id,
        generated_answer_id=None,
        attempts=2,
        max_attempts=3,
        lease_owner="worker-1",
        input_snapshot={"is_correct": False},
    )
    job = DiagnosisJob(
        id=claimed.job_id,
        user_id=claimed.user_id,
        standard_answer_id=answer_id,
        status="running",
        attempts=2,
        lease_owner="worker-1",
        input_snapshot=claimed.input_snapshot,
    )
    existing = AnswerDiagnosis(
        id=uuid.uuid4(),
        user_id=claimed.user_id,
        standard_answer_id=answer_id,
        status="insufficient_evidence",
        knowledge_point_code="equation_equivalence",
        evidence="已有结果",
        confidence=0,
        source="fallback",
    )
    session = TransactionalSession([job, existing])

    async def forbidden_mastery_update(*_args, **_kwargs):
        raise AssertionError("幂等重试不得再次更新掌握度")

    monkeypatch.setattr(
        diagnosis_service, "update_mastery_once", forbidden_mastery_update
    )

    await persist_diagnosis_result(SingleSessionFactory(session), claimed, object())

    assert job.status == "succeeded"
    assert job.lease_owner is None
    assert job.lease_expires_at is None


@pytest.mark.asyncio
async def test_invalid_snapshot_uses_a_safe_failure_category(monkeypatch):
    claimed = ClaimedDiagnosisJob(
        job_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        standard_answer_id=uuid.uuid4(),
        generated_answer_id=None,
        attempts=1,
        max_attempts=3,
        lease_owner="worker-1",
        input_snapshot={"untrusted": "secret payload"},
    )
    recorded = []

    async def fake_mark(_factory, _job, reason):
        recorded.append(reason)

    monkeypatch.setattr(diagnosis_service, "_mark_retry_or_failed", fake_mark)

    await diagnosis_service.process_diagnosis_job(object(), claimed, None)

    assert recorded == ["diagnosis_processing_failed"]
