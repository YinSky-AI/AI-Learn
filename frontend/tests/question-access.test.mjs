import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const mapper = readFileSync(
  new URL("../src/components/learning/quiz-question-mapper.ts", import.meta.url),
  "utf8",
);
const store = readFileSync(
  new URL("../src/stores/learning-store.ts", import.meta.url),
  "utf8",
);

test("public quiz mapper accepts and emits only answer-safe question fields", () => {
  assert.doesNotMatch(mapper, /correct_answer|payload\.explanation/);
  assert.match(mapper, /mapQuizQuestion/);
});

test("learning store builds quiz state through the public brief mapper", () => {
  assert.match(store, /mapQuizQuestion/);
  assert.doesNotMatch(store, /q\.correct_answer|q\.explanation/);
});
