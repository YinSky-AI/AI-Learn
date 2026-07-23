# Task 3 Report

## Status

Implemented and verified by targeted automated frontend checks. Visual browser verification is blocked because no in-app browser connection is available in this environment.

## Summary

- Wrong-book practice renders server-provided question types, supports radio single choice, checkbox multi-select with canonical comma-separated answers, and one-answer fill blanks.
- Failed wrong-book submissions preserve the displayed question, answer, attempt ID, and a fixed Chinese retry message. Submission and answer controls are synchronously guarded while a request is active.
- Subject-filter changes start a new load generation and reset every answer/retry state. Load and submit callbacks are accepted only while their production-controller token remains current, so a late response cannot overwrite the new practice set or release a newer submit guard.
- QuizPractice freezes the complete answer request for retry, including answer ID, answer text, and elapsed time; it rotates only after an answer change or question navigation.
- Completion adopts the server-returned session statistics as the authoritative result and leaves completed answers intact when completion must be retried.

## Files Changed

- `frontend/src/app/(main)/wrong-book/practice/page.tsx`
- `frontend/src/app/(main)/wrong-book/practice/practice-retry-state.mjs`
- `frontend/src/components/quiz/quiz-practice.tsx`
- `frontend/src/components/quiz/quiz-retry-state.mjs`
- `frontend/tests/wrong-book-practice.test.mjs`
- `frontend/tests/learning-loop.test.mjs`

## Tests

- `cd frontend; node --test tests/wrong-book-practice.test.mjs tests/learning-loop.test.mjs tests/knowledge-practice-ui.test.mjs` — 19 passing tests, including deferred-promise controller coverage for slow A/B loads, stale submit success/error/finally callbacks, and the complete reset-state contract.
- `cd frontend; npm run typecheck` — passed.
- `cd frontend; npm run build` — passed.
- `git diff --check` — passed.

## Commit(s)

- `fix(practice): make answer retries idempotent`
- `fix(practice): isolate retry state across questions`
- `fix(practice): ignore stale practice responses`

## Concerns

- The in-app browser reports that no browser is available, so an authenticated visual screenshot check could not be captured in this environment.
- The project has React DOM but no installed jsdom, Testing Library, Vitest, or Jest harness. To avoid adding a disproportionate DOM test stack, the page uses `createWrongBookPracticeController` directly and Node tests exercise that production controller; minimal source assertions verify the page wires load generations, reset state, and submission guards. Full DOM/browser interaction coverage remains for Task 4.
- `api-client` replaces caller-provided abort signals with its own timeout signal, so this task intentionally does not rely on `AbortController` or claim network cancellation. Token checks are the correctness boundary for stale responses.
