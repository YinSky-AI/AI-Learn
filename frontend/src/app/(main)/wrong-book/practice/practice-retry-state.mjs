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
