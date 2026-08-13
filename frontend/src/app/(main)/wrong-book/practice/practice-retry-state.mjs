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

export function createPracticeResetState() {
  return {
    questions: [],
    index: 0,
    answer: "",
    selectedOptionKeys: [],
    submitted: false,
    result: null,
    authRequired: false,
    loadError: "",
    submitError: "",
    loading: true,
    isSubmitting: false,
  };
}

export function createWrongBookPracticeController(createId = () => crypto.randomUUID()) {
  const retry = createWrongBookRetryState(createId);
  const guard = createSubmitGuard();
  let loadGeneration = 0;
  let interactionGeneration = 0;
  let submissionGeneration = 0;
  let activeSubmissionGeneration = 0;

  function invalidateInteraction() {
    interactionGeneration += 1;
    activeSubmissionGeneration = 0;
    retry.reset();
    guard.end();
  }

  function isCurrentSubmission(token) {
    return Boolean(
      token &&
      token.loadGeneration === loadGeneration &&
      token.interactionGeneration === interactionGeneration &&
      token.submissionGeneration === activeSubmissionGeneration
    );
  }

  return {
    guard,
    beginLoad() {
      loadGeneration += 1;
      invalidateInteraction();
      return {
        token: loadGeneration,
        resetState: createPracticeResetState(),
      };
    },
    invalidate() {
      loadGeneration += 1;
      invalidateInteraction();
    },
    isCurrent(generation) {
      return generation === loadGeneration;
    },
    async runLoad(token, request, callbacks) {
      try {
        const data = await request();
        if (this.isCurrent(token)) callbacks.onSuccess?.(data);
      } catch (error) {
        if (this.isCurrent(token)) callbacks.onError?.(error);
      } finally {
        if (this.isCurrent(token)) callbacks.onFinally?.();
      }
    },
    beginSubmit(loadToken, questionId) {
      if (!this.isCurrent(loadToken) || !guard.begin()) return null;
      submissionGeneration += 1;
      activeSubmissionGeneration = submissionGeneration;
      return {
        loadGeneration,
        interactionGeneration,
        submissionGeneration,
        questionId,
      };
    },
    async runSubmit(token, request, callbacks) {
      try {
        const data = await request();
        if (isCurrentSubmission(token)) callbacks.onSuccess?.(data);
      } catch (error) {
        if (isCurrentSubmission(token)) callbacks.onError?.(error);
      } finally {
        if (isCurrentSubmission(token)) {
          guard.end();
          callbacks.onFinally?.();
        }
      }
    },
    prepare(questionId, userAnswer) {
      return retry.prepare(questionId, userAnswer);
    },
    fail() {
      return retry.fail();
    },
    resetQuestion() {
      invalidateInteraction();
    },
  };
}
