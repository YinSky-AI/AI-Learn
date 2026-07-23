export function normalizeMultiAnswer(keys) {
  return [...new Set(keys)].sort().join(",");
}

export function createWrongBookAttempt(questionId, userAnswer, createId = () => crypto.randomUUID()) {
  return { attemptId: createId(), questionId, userAnswer };
}

export function reuseWrongBookAttempt(previous, questionId, userAnswer, createId = () => crypto.randomUUID()) {
  if (
    previous &&
    previous.questionId === questionId &&
    previous.userAnswer === userAnswer
  ) {
    return previous;
  }
  return createWrongBookAttempt(questionId, userAnswer, createId);
}

export function createWrongBookRetryState(createId = () => crypto.randomUUID()) {
  let attempt = null;
  let error = "";
  return {
    prepare(questionId, userAnswer) {
      attempt = reuseWrongBookAttempt(attempt, questionId, userAnswer, createId);
      error = "";
      return attempt;
    },
    fail() {
      error = "答案提交失败，请稍后重试。";
      return { attempt, error };
    },
    reset() {
      attempt = null;
      error = "";
    },
  };
}

export function createSubmitGuard() {
  let submitting = false;
  return {
    begin() {
      if (submitting) return false;
      submitting = true;
      return true;
    },
    end() {
      submitting = false;
    },
    isSubmitting() {
      return submitting;
    },
  };
}

export function createWrongBookPracticeController(createId = () => crypto.randomUUID()) {
  const retry = createWrongBookRetryState(createId);
  const guard = createSubmitGuard();
  let loadGeneration = 0;
  return {
    guard,
    beginLoad() {
      loadGeneration += 1;
      retry.reset();
      guard.end();
      return loadGeneration;
    },
    isCurrent(generation) {
      return generation === loadGeneration;
    },
    prepare(questionId, userAnswer) {
      return retry.prepare(questionId, userAnswer);
    },
    fail() {
      return retry.fail();
    },
    resetQuestion() {
      retry.reset();
      guard.end();
    },
  };
}
