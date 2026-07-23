import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  createSubmitGuard,
  createWrongBookRetryState,
  createWrongBookAttempt,
  normalizeMultiAnswer,
  reuseWrongBookAttempt,
} from "../src/app/(main)/wrong-book/practice/practice-retry-state.mjs";

const source = readFileSync(
  new URL("../src/app/(main)/wrong-book/practice/page.tsx", import.meta.url),
  "utf8",
);

test("wrong-book practice keeps loading separate from the empty state", () => {
  assert.match(source, /const \[loading, setLoading\] = useState\(true\)/);
  assert.match(source, /if \(loading\)/);
  assert.match(source, /正在加载错题/);
});

test("wrong-book practice reads filters through Next search params", () => {
  assert.match(source, /useSearchParams\(\)/);
  assert.match(source, /<Suspense[\s\S]*<WrongBookPracticeContent \/>[\s\S]*<\/Suspense>/);
  assert.doesNotMatch(source, /window\.location\.search/);
});

test("wrong-book multi-select answers are deduplicated and canonically sorted", () => {
  assert.equal(normalizeMultiAnswer(["C", "A", "C", "B"]), "A,B,C");
});

test("wrong-book retry retains the original attempt and answer after a failed request", () => {
  const attempt = createWrongBookAttempt("question-1", "A,B", () => "attempt-1");
  const retry = reuseWrongBookAttempt(attempt, "question-1", "A,B", () => "attempt-2");

  assert.deepEqual(retry, {
    attemptId: "attempt-1",
    questionId: "question-1",
    userAnswer: "A,B",
  });
});

test("wrong-book failure keeps the answered attempt available for the inline retry", () => {
  const retry = createWrongBookRetryState(() => "attempt-1");
  const attempt = retry.prepare("question-1", "B");
  const failed = retry.fail();

  assert.equal(failed.attempt, attempt);
  assert.equal(failed.error, "答案提交失败，请稍后重试。");
  assert.equal(retry.prepare("question-1", "B"), attempt);
});

test("wrong-book submission guard blocks double clicks until the request settles", () => {
  const guard = createSubmitGuard();

  assert.equal(guard.begin(), true);
  assert.equal(guard.begin(), false);
  assert.equal(guard.isSubmitting(), true);
  guard.end();
  assert.equal(guard.isSubmitting(), false);
  assert.equal(guard.begin(), true);
});
