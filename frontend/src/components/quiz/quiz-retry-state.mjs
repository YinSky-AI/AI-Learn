export function createAnswerRequest(questionId, userAnswer, timeSpentSeconds, createId = () => crypto.randomUUID()) {
  return {
    questionId,
    answerId: createId(),
    userAnswer,
    timeSpentSeconds,
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

export function resolveAnswerRequest(previous, questionId, userAnswer, timeSpentSeconds, createId = () => crypto.randomUUID()) {
  if (
    previous &&
    previous.questionId === questionId &&
    previous.userAnswer === userAnswer
  ) {
    return previous;
  }
  return createAnswerRequest(questionId, userAnswer, timeSpentSeconds, createId);
}

export function serverStatsToCompletionResult(stats) {
  return {
    correctCount: stats.correct_count,
    totalCount: stats.total_questions,
    accuracy: stats.accuracy_rate,
    timeSpentSeconds: stats.total_time_seconds,
  };
}
