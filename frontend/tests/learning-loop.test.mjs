import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  createSubmitGuard,
  createAnswerRequest,
  resolveAnswerRequest,
  serverStatsToCompletionResult,
} from "../src/components/quiz/quiz-retry-state.mjs";

const quiz = readFileSync(new URL("../src/components/quiz/quiz-practice.tsx", import.meta.url), "utf8");
const page = readFileSync(new URL("../src/app/(main)/learning/[id]/page.tsx", import.meta.url), "utf8");

test("course quiz uses the answer-safe lesson endpoint", () => {
  assert.match(page, /\/v1\/courses\/\$\{course\.id\}\/lessons\/\$\{currentLesson\.id\}\/quiz/);
  assert.doesNotMatch(page, /\/v1\/content\/questions/);
  assert.doesNotMatch(page, /correct_answer:\s*string/);
  assert.doesNotMatch(page, /getMockQuizQuestions|fallback 题目/);
  assert.match(page, /quizLoadError/);
});

test("quiz answers are judged and completed by the learning session API", () => {
  assert.match(quiz, /\/v1\/learning\/sessions["'`]/);
  assert.match(quiz, /\/v1\/learning\/sessions\/\$\{activeSessionId\}\/answer/);
  assert.match(quiz, /\/v1\/learning\/sessions\/\$\{sessionId\}\/complete/);
  assert.doesNotMatch(quiz, /function judgeAnswer/);
  assert.doesNotMatch(quiz, /currentQuestion\.correctAnswer/);
});

test("quiz retry keeps the entire answer request body after a lost response", () => {
  const initial = createAnswerRequest("question-1", "B", 12, () => "answer-1");
  const retry = resolveAnswerRequest(initial, "question-1", "B", 99, () => "answer-2");

  assert.deepEqual(retry, {
    questionId: "question-1",
    answerId: "answer-1",
    userAnswer: "B",
    timeSpentSeconds: 12,
  });
});

test("quiz submission guard blocks a second click until the first request settles", () => {
  const guard = createSubmitGuard();

  assert.equal(guard.begin(), true);
  assert.equal(guard.begin(), false);
  guard.end();
  assert.equal(guard.begin(), true);
});

test("quiz rotates answer events only when the answer changes or navigation switches question", () => {
  const initial = createAnswerRequest("question-1", "A", 8, () => "answer-1");
  const changedAnswer = resolveAnswerRequest(initial, "question-1", "B", 10, () => "answer-2");
  const nextQuestion = resolveAnswerRequest(changedAnswer, "question-2", "C", 3, () => "answer-3");

  assert.equal(changedAnswer.answerId, "answer-2");
  assert.equal(changedAnswer.timeSpentSeconds, 10);
  assert.equal(nextQuestion.answerId, "answer-3");
  assert.equal(nextQuestion.questionId, "question-2");
});

test("quiz completion uses the server statistics instead of local result totals", () => {
  assert.deepEqual(
    serverStatsToCompletionResult({
      correct_count: 3,
      total_questions: 4,
      accuracy_rate: 75,
      total_time_seconds: 42,
    }),
    { correctCount: 3, totalCount: 4, accuracy: 75, timeSpentSeconds: 42 },
  );
});
