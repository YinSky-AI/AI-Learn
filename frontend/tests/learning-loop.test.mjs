import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

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
