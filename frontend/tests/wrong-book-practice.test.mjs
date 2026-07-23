import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  createSubmitGuard,
  createPracticeResetState,
  createWrongBookPracticeController,
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

test("wrong-book rejects an older subject load and resets the previous answered attempt", () => {
  let attemptNumber = 0;
  const controller = createWrongBookPracticeController(() => `attempt-${++attemptNumber}`);
  const subjectA = controller.beginLoad();
  const originalAttempt = controller.prepare("question-a", "A");
  assert.equal(controller.guard.begin(), true);

  const subjectB = controller.beginLoad();
  assert.equal(controller.isCurrent(subjectA.token), false);
  assert.equal(controller.isCurrent(subjectB.token), true);
  assert.equal(controller.guard.isSubmitting(), false);
  assert.notEqual(controller.prepare("question-a", "A").attemptId, originalAttempt.attemptId);
});

test("wrong-book page wires load generations and interaction reset through its production controller", () => {
  assert.match(source, /const controller = practiceControllerRef\.current/);
  assert.match(source, /controller\.beginLoad\(\)/);
  assert.match(source, /controller\.runLoad\(/);
  assert.match(source, /controller\.runSubmit\(/);
  assert.match(source, /controller\.invalidate\(\)/);
  assert.match(source, /controller\.isCurrent\(loadGeneration\)/);
  assert.match(source, /controller\.beginSubmit\(/);
  assert.match(source, /controller\.guard\.isSubmitting\(\)/);
  assert.match(source, /setSubmitted\(false\)/);
  assert.match(source, /setResult\(null\)/);
  assert.doesNotMatch(source, /AbortController/);
});

function createDeferred() {
  let resolve;
  let reject;
  const promise = new Promise((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
}

test("wrong-book load controller ignores a slow A response after B and exposes the complete reset state", async () => {
  const controller = createWrongBookPracticeController();
  const slowA = createDeferred();
  const fastB = createDeferred();
  const applied = [];

  const loadA = controller.beginLoad();
  assert.deepEqual(loadA.resetState, createPracticeResetState());
  const requestA = controller.runLoad(loadA.token, () => slowA.promise, {
    onSuccess: (value) => applied.push(`success:${value}`),
    onFinally: () => applied.push("finally:A"),
  });

  const loadB = controller.beginLoad();
  const requestB = controller.runLoad(loadB.token, () => fastB.promise, {
    onSuccess: (value) => applied.push(`success:${value}`),
    onFinally: () => applied.push("finally:B"),
  });
  fastB.resolve("B");
  await requestB;
  slowA.resolve("A");
  await requestA;

  assert.deepEqual(applied, ["success:B", "finally:B"]);
  assert.deepEqual(loadB.resetState, {
    questions: [], index: 0, answer: "", selectedOptionKeys: [], submitted: false,
    result: null, authRequired: false, loadError: "", submitError: "", loading: true,
    isSubmitting: false,
  });
});

test("wrong-book stale A submission cannot write or release B submission", async () => {
  const controller = createWrongBookPracticeController();
  const slowA = createDeferred();
  const slowB = createDeferred();
  const applied = [];

  const loadA = controller.beginLoad();
  const submitA = controller.beginSubmit(loadA.token, "question-a");
  const requestA = controller.runSubmit(submitA, () => slowA.promise, {
    onSuccess: () => applied.push("success:A"),
    onError: () => applied.push("error:A"),
    onFinally: () => applied.push("finally:A"),
  });

  const loadB = controller.beginLoad();
  const submitB = controller.beginSubmit(loadB.token, "question-b");
  const requestB = controller.runSubmit(submitB, () => slowB.promise, {
    onSuccess: () => applied.push("success:B"),
    onFinally: () => applied.push("finally:B"),
  });

  slowA.reject(new Error("stale A failure"));
  await requestA;
  assert.deepEqual(applied, []);
  assert.equal(controller.guard.isSubmitting(), true);

  slowB.resolve({ is_correct: true });
  await requestB;
  assert.deepEqual(applied, ["success:B", "finally:B"]);
  assert.equal(controller.guard.isSubmitting(), false);
});

test("wrong-book stale successful submit cannot write after a newer load", async () => {
  const controller = createWrongBookPracticeController();
  const slowA = createDeferred();
  const applied = [];

  const loadA = controller.beginLoad();
  const submitA = controller.beginSubmit(loadA.token, "question-a");
  const requestA = controller.runSubmit(submitA, () => slowA.promise, {
    onSuccess: () => applied.push("success:A"),
    onFinally: () => applied.push("finally:A"),
  });

  controller.beginLoad();
  slowA.resolve({ is_correct: true });
  await requestA;

  assert.deepEqual(applied, []);
  assert.equal(controller.guard.isSubmitting(), false);
});
