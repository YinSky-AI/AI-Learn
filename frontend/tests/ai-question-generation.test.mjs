import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(
  new URL("../src/app/(main)/ai-questions/page.tsx", import.meta.url),
  "utf8",
);
const floating = readFileSync(new URL("../src/components/ai/floating-ai-button.tsx", import.meta.url), "utf8");
const tutor = readFileSync(new URL("../src/components/ai/tutor-chat.tsx", import.meta.url), "utf8");

test("AI question page calls the two-agent generation API", () => {
  assert.match(page, /apiClient\.post<GenerateResult>\("\/v1\/questions\/generate"/);
  assert.match(page, /出题 Agent/);
  assert.match(page, /审题 Agent/);
  assert.match(page, /course_topic/);
  assert.match(page, /question_types/);
});

test("global AI question shortcut routes to the two-agent page", () => {
  assert.match(floating, /router\.push\("\/ai-questions"\)/);
  assert.match(floating, /onQuickPrompt=/);
  assert.match(tutor, /onQuickPrompt\?\.\(prompt\)/);
});

test("AI question page only renders the public question contract", () => {
  assert.match(page, /question_body/);
  assert.match(page, /quality_status/);
  assert.doesNotMatch(page, /correct_answer|explanation/);
});
