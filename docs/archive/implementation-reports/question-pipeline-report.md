# Task 2 Implementer Report

## Scope

Implemented the standalone two-layer question pipeline. It calls only the
question-generation and question-review prompts, retries a rejected batch at
most twice, and returns the revised structured questions together with the
structured review result.

## TDD evidence

- RED: `docker compose exec -T backend pytest tests/test_question_pipeline.py -q`
  initially failed with `ModuleNotFoundError: No module named
  'app.ai.question_pipeline'` after rebuilding the test image.
- GREEN: the same command completed with `1 passed in 0.05s` after the minimal
  implementation. The focused test supplies generation, rejection, revised
  generation, and approval responses; it asserts the revised questions, the
  review result, the four provider calls, and propagation of revision notes.

## Changed files

- `backend/app/ai/question_pipeline.py`: standalone `QuestionPipeline`, result
  types, safe Chinese errors, JSON parsing, and the three-attempt loop.
- `backend/app/ai/prompts/question_review.py`: review-agent JSON prompt.
- `backend/app/ai/prompts/question_generation.py`: optional review revision
  notes in the existing generation prompt.
- `backend/app/ai/__init__.py`: exports for the independent pipeline types.
- `backend/tests/test_question_pipeline.py`: focused fake-provider TDD test.

## Verification and deployment

- `docker compose up -d --build` completed successfully.
- `docker compose exec -T backend pytest tests/test_question_pipeline.py -q`
  completed with `1 passed in 0.03s`.
- `docker compose exec -T backend python -m compileall -q app` completed with
  exit code 0.
- `docker compose ps` showed backend, frontend, PostgreSQL, and Redis healthy.
- Backend logs showed successful startup, database and Redis connections, and
  `GET /health` returning 200; no new errors were present.
- `git diff --check` completed with no whitespace errors.

## Commit

- Message: `feat(ai): add two-layer question pipeline`
- Only Task 2 files are staged for this commit.

## Concerns

- The pipeline is deliberately not wired into an API endpoint because the Task
  2 brief specifies only the pipeline contract. Existing Harness and
  `prompts_2` orchestration are not imported or called.
