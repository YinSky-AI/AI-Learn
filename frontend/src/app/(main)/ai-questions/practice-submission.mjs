export function normalizeAnswer(answer, questionType) {
  const normalized = String(answer || "").trim();
  if (questionType !== "MULTIPLE_CHOICE") return normalized;

  return Array.from(new Set(normalized.split(",").map((item) => item.trim()).filter(Boolean))).sort().join(",");
}

export function hasNormalizedAnswerChanged(currentAnswer, nextAnswer, questionType) {
  return normalizeAnswer(currentAnswer, questionType) !== normalizeAnswer(nextAnswer, questionType);
}

export function invalidateSubmissionPayload(existingPayload, { isNewBatch = false, currentAnswer = "", nextAnswer = "", questionType = "CHOICE" } = {}) {
  if (isNewBatch || hasNormalizedAnswerChanged(currentAnswer, nextAnswer, questionType)) return null;
  return existingPayload;
}

function allocateQuestionTime({ questions, batchStartedAt, questionChangedAt, submittedAt }) {
  const batchStarted = Math.max(0, Number(batchStartedAt) || 0);
  const submitted = Math.max(batchStarted, Number(submittedAt) || batchStarted);
  const elapsedByQuestionId = Object.fromEntries(questions.map((question) => [question.id, 0]));
  const answeredQuestions = questions
    .map((question, index) => ({
      id: question.id,
      index,
      changedAt: Math.max(batchStarted, Math.min(submitted, Number(questionChangedAt[question.id]) || batchStarted)),
    }))
    .sort((left, right) => left.changedAt - right.changedAt || left.index - right.index);

  let cursor = batchStarted;
  for (const question of answeredQuestions) {
    elapsedByQuestionId[question.id] += question.changedAt - cursor;
    cursor = question.changedAt;
  }
  if (answeredQuestions.length) {
    elapsedByQuestionId[answeredQuestions.at(-1).id] += submitted - cursor;
  }

  let elapsedMilliseconds = 0;
  let convertedSeconds = 0;
  return Object.fromEntries(questions.map((question) => {
    elapsedMilliseconds += elapsedByQuestionId[question.id];
    const totalSeconds = Math.floor(elapsedMilliseconds / 1000);
    const timeSpentSeconds = Math.max(0, totalSeconds - convertedSeconds);
    convertedSeconds = totalSeconds;
    return [question.id, timeSpentSeconds];
  }));
}

export function getOrCreateSubmissionPayload(existingPayload, input) {
  if (existingPayload) return existingPayload;

  const timeSpentByQuestionId = allocateQuestionTime(input);
  return {
    submission_id: input.submissionId,
    answers: input.questions.map((question) => {
      const solutionSteps = (input.solutionSteps?.[question.id] || [])
        .map((step) => String(step).trim())
        .filter(Boolean)
        .slice(0, 12);
      const confidence = input.confidences?.[question.id];
      return {
        question_id: question.id,
        user_answer: normalizeAnswer(input.answers[question.id], question.question_type),
        time_spent_seconds: timeSpentByQuestionId[question.id],
        solution_steps: solutionSteps,
        ...(Number.isInteger(confidence) && confidence >= 1 && confidence <= 5
          ? { confidence }
          : {}),
      };
    }),
  };
}

export function getSubmissionErrorMessage(error) {
  const detail = error && typeof error === "object" ? error : {};
  const code = String(detail.code || "").toUpperCase();
  const message = typeof detail.message === "string" ? detail.message.toLowerCase() : "";

  if (detail.name === "AbortError" || message.includes("abort") || message.includes("timeout")) {
    return "提交超时，请稍后重试。";
  }
  if (code === "401" || code === "403" || code === "HTTP_401" || code === "HTTP_403") {
    return "登录状态已失效，请重新登录后提交。";
  }
  if (code === "409" || code === "422" || code === "HTTP_409" || code === "HTTP_422" || message.includes("review") || message.includes("validation")) {
    return "题目审核或答案校验未通过，请重新出题后再试。";
  }
  if (code === "502" || code === "503" || code === "HTTP_502" || code === "HTTP_503" || message.includes("provider") || message.includes("unavailable")) {
    return "出题服务暂时不可用，请稍后再试。";
  }
  return "答案提交失败，请稍后重试。";
}

export function indexSubmissionResults(results) {
  return Object.fromEntries(results.map((result) => [result.question_id, result]));
}
