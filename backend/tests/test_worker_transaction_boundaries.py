import uuid

import pytest

import app.services.diagnosis_job_service as diagnosis_service
import app.services.question_generation_service as generation_service
import run_diagnosis_worker
import run_generation_worker
from app.models.ai_generated import GeneratedQuestion, GenerationJob
from app.services.diagnosis_job_service import ClaimedDiagnosisJob
from app.services.question_generation_service import (
    ClaimedGenerationJob,
    GenerationJobContext,
)


class Tracker:
    def __init__(self):
        self.transaction_open = False
        self.commits = 0


class TransactionContext:
    def __init__(self, tracker):
        self.tracker = tracker

    async def __aenter__(self):
        assert not self.tracker.transaction_open
        self.tracker.transaction_open = True

    async def __aexit__(self, exc_type, exc, traceback):
        self.tracker.transaction_open = False
        if exc_type is None:
            self.tracker.commits += 1


class FakeSession:
    def __init__(self, tracker):
        self.tracker = tracker

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _traceback):
        assert not self.tracker.transaction_open

    def begin(self):
        return TransactionContext(self.tracker)


class FakeSessionFactory:
    def __init__(self, tracker):
        self.tracker = tracker

    def __call__(self):
        return FakeSession(self.tracker)


@pytest.mark.asyncio
async def test_diagnosis_worker_commits_claim_before_processing(monkeypatch):
    """Keeping the claim transaction open during diagnosis must make this fail."""

    tracker = Tracker()
    claimed = ClaimedDiagnosisJob(
        job_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        standard_answer_id=uuid.uuid4(),
        generated_answer_id=None,
        attempts=1,
        max_attempts=3,
        lease_owner="worker-1",
        input_snapshot={"equation": "x=4", "is_correct": True, "solution_steps": [], "knowledge_point_code": "equation_equivalence"},
    )

    async def fake_claim(_db, _worker_id):
        assert tracker.transaction_open
        return claimed

    async def fake_process(_factory, received, _provider):
        assert received is claimed
        assert tracker.commits == 1
        assert not tracker.transaction_open

    monkeypatch.setattr(run_diagnosis_worker, "claim_diagnosis_job", fake_claim)
    monkeypatch.setattr(run_diagnosis_worker, "process_diagnosis_job", fake_process)

    worked = await run_diagnosis_worker.run_worker_once(
        FakeSessionFactory(tracker), object(), "worker-1"
    )

    assert worked is True


@pytest.mark.asyncio
async def test_diagnosis_provider_runs_before_result_transaction(monkeypatch):
    """Opening the result transaction before Provider completion must make this fail."""

    tracker = Tracker()
    claimed = ClaimedDiagnosisJob(
        job_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        standard_answer_id=uuid.uuid4(),
        generated_answer_id=None,
        attempts=1,
        max_attempts=3,
        lease_owner="worker-1",
        input_snapshot={"equation": "2(x+1)=10", "is_correct": False, "solution_steps": ["2(x+1)=10", "x+1=10"], "knowledge_point_code": "equation_equivalence"},
    )
    order = []

    async def fake_diagnose(_input, _provider):
        assert not tracker.transaction_open
        order.append("provider_finished")
        return object()

    async def fake_persist(_factory, _job, _result):
        assert order == ["provider_finished"]
        assert not tracker.transaction_open
        order.append("result_transaction")

    monkeypatch.setattr(diagnosis_service, "diagnose_answer", fake_diagnose)
    monkeypatch.setattr(diagnosis_service, "persist_diagnosis_result", fake_persist)

    await diagnosis_service.process_diagnosis_job(
        FakeSessionFactory(tracker), claimed, object()
    )

    assert order == ["provider_finished", "result_transaction"]


@pytest.mark.asyncio
async def test_generation_worker_commits_claim_before_pipeline(monkeypatch):
    """Keeping the generation claim transaction open during model work must fail."""

    tracker = Tracker()
    claimed = ClaimedGenerationJob(
        job_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source_question_id=uuid.uuid4(),
        target_difficulty="DIFF_MEDIUM",
        lease_owner="worker-1",
    )

    async def fake_claim(_db, _worker_id):
        assert tracker.transaction_open
        return claimed

    async def fake_process(_factory, received, _pipeline):
        assert received is claimed
        assert tracker.commits == 1
        assert not tracker.transaction_open

    monkeypatch.setattr(run_generation_worker, "claim_next_generation_job", fake_claim)
    monkeypatch.setattr(run_generation_worker, "process_claimed_generation_job", fake_process)

    worked = await run_generation_worker.run_worker_once(
        FakeSessionFactory(tracker), object(), "worker-1"
    )

    assert worked is True


@pytest.mark.asyncio
async def test_generation_pipeline_runs_after_snapshot_session_closes(monkeypatch):
    """Passing a live database transaction into Generator—Reviewer must make this fail."""

    tracker = Tracker()
    claimed = ClaimedGenerationJob(
        job_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source_question_id=uuid.uuid4(),
        target_difficulty="DIFF_MEDIUM",
        lease_owner="worker-1",
        target_knowledge_point_code="normalize_coefficient",
        target_misconception_code="coefficient_normalization_error",
        policy_version="adaptive-policy-v1",
    )
    context = GenerationJobContext(
        job=claimed,
        batch_id=uuid.uuid4(),
        age_group_code="AGE_13_15",
        subject_code="SUBJ_MATH",
        course_topic="一元一次方程",
        question_type="FILL_BLANK",
    )
    order = []

    async def fake_load(_factory, _job):
        order.append("snapshot_closed")
        return context

    async def fake_persist(_factory, _context, _questions):
        assert order == ["snapshot_closed", "provider_finished"]
        order.append("result_transaction")

    class Pipeline:
        async def generate(self, _request, _user_id, db, adaptive_context=None):
            assert db is None
            assert not tracker.transaction_open
            assert adaptive_context.target_knowledge_point_code == "normalize_coefficient"
            assert adaptive_context.target_misconception_code == "coefficient_normalization_error"
            assert adaptive_context.policy_version == "adaptive-policy-v1"
            assert adaptive_context.parent_question_id == str(claimed.source_question_id)
            order.append("provider_finished")
            return type("Result", (), {"questions": [{"question_body": "q"}]})()

    monkeypatch.setattr(generation_service, "load_generation_job_context", fake_load)
    monkeypatch.setattr(generation_service, "persist_generation_result", fake_persist)

    await generation_service.process_claimed_generation_job(
        FakeSessionFactory(tracker), claimed, Pipeline()
    )

    assert order == ["snapshot_closed", "provider_finished", "result_transaction"]


@pytest.mark.asyncio
async def test_synchronous_generation_finishes_provider_before_save_transaction(monkeypatch):
    tracker = Tracker()
    order = []

    class Db:
        def begin_nested(self):
            return TransactionContext(tracker)

    class Pipeline:
        async def generate(self, _request, _user_id, db):
            assert db is None
            assert not tracker.transaction_open
            order.append("provider_finished")
            return object()

    class SaveTool:
        def __init__(self, _request):
            pass

        async def save_batch(self, _db, _result, _user_id):
            assert tracker.transaction_open
            assert order == ["provider_finished"]
            order.append("saved")
            return object()

    monkeypatch.setattr(generation_service, "QuestionSaveTool", SaveTool)

    await generation_service.generate_reviewed_batch(
        Db(), uuid.uuid4(), object(), Pipeline()
    )

    assert order == ["provider_finished", "saved"]


@pytest.mark.asyncio
async def test_generation_result_persists_adaptive_codes_and_policy(monkeypatch):
    user_id = uuid.uuid4()
    claimed = ClaimedGenerationJob(
        job_id=uuid.uuid4(),
        user_id=user_id,
        source_question_id=uuid.uuid4(),
        target_difficulty="DIFF_MEDIUM",
        lease_owner="worker-1",
        target_knowledge_point_code="normalize_coefficient",
        target_misconception_code="coefficient_normalization_error",
        policy_version="adaptive-policy-v1",
    )
    context = GenerationJobContext(
        job=claimed,
        batch_id=uuid.uuid4(),
        age_group_code="AGE_13_15",
        subject_code="SUBJ_MATH",
        course_topic="一元一次方程",
        question_type="FILL_BLANK",
    )
    job = GenerationJob(
        id=claimed.job_id,
        user_id=user_id,
        source_question_id=claimed.source_question_id,
        target_difficulty=claimed.target_difficulty,
        idempotency_key="test-adaptive-result",
        status="running",
        lease_owner=claimed.lease_owner,
    )
    question = GeneratedQuestion(
        id=uuid.uuid4(),
        batch_id=context.batch_id,
        user_id=user_id,
        subject_code="SUBJ_MATH",
        course_topic="一元一次方程",
        difficulty_level="DIFF_MEDIUM",
        question_type="FILL_BLANK",
        question_body="2x=8",
        correct_answer="x=4",
        explanation="两边同时除以 2",
        knowledge_tags=[],
        source_prompt="safe-summary",
    )

    class Result:
        def scalar_one_or_none(self):
            return job

    class Session(FakeSession):
        async def execute(self, _statement):
            return Result()

        async def flush(self):
            pass

    async def fake_save(*_args, **_kwargs):
        return [question]

    monkeypatch.setattr(generation_service, "save_generated_questions", fake_save)
    await generation_service.persist_generation_result(
        lambda: Session(Tracker()), context, [{"question_body": "2x=8"}]
    )

    assert question.parent_question_id == claimed.source_question_id
    assert question.target_knowledge_point_code == "normalize_coefficient"
    assert question.target_misconception_code == "coefficient_normalization_error"
    assert question.generation_policy_version == "adaptive-policy-v1"
    assert question.knowledge_tags == [
        "normalize_coefficient",
        "coefficient_normalization_error",
    ]
    assert job.status == "succeeded"


@pytest.mark.asyncio
async def test_generation_failure_does_not_persist_provider_exception_text(monkeypatch):
    claimed = ClaimedGenerationJob(
        job_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source_question_id=uuid.uuid4(),
        target_difficulty="DIFF_MEDIUM",
        lease_owner="worker-1",
    )
    context = GenerationJobContext(
        job=claimed,
        batch_id=uuid.uuid4(),
        age_group_code="AGE_13_15",
        subject_code="SUBJ_MATH",
        course_topic="一元一次方程",
        question_type="FILL_BLANK",
    )
    recorded = []

    async def fake_load(_factory, _job):
        return context

    async def fake_mark(_factory, _job, reason):
        recorded.append(reason)

    class Pipeline:
        async def generate(self, _request, _user_id, _db):
            raise ValueError("provider-secret-payload")

    monkeypatch.setattr(generation_service, "load_generation_job_context", fake_load)
    monkeypatch.setattr(generation_service, "_mark_generation_attempt", fake_mark)

    await generation_service.process_claimed_generation_job(
        object(), claimed, Pipeline()
    )

    assert recorded == ["generation_or_review_failed"]
