import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");
const read = (relativePath) => readFileSync(path.join(root, relativePath), "utf8");

test("global layout mounts a lazy loaded AI tutor", () => {
  const floatingPath = path.join(root, "src/components/ai/floating-ai-button.tsx");
  assert.equal(existsSync(floatingPath), true, "floating AI component should exist");

  const floating = read("src/components/ai/floating-ai-button.tsx");
  const mainLayout = read("src/components/layout/main-layout.tsx");
  assert.match(floating, /dynamic\(.*import\(["']\.\/tutor-chat["']\)/s);
  assert.match(floating, /ssr:\s*false/);
  assert.match(mainLayout, /<FloatingAIButton\s*\/?>/);
});

test("floating AI panel supports open, close and minimise without covering mobile navigation", () => {
  const floating = read("src/components/ai/floating-ai-button.tsx");
  assert.match(floating, /"打开 AI 辅导老师"/);
  assert.match(floating, /aria-label="关闭 AI 辅导老师"/);
  assert.match(floating, /aria-label="最小化 AI 辅导老师"/);
  assert.match(floating, /bottom-20/);
  assert.match(floating, /lg:bottom-8/);
});

test("floating tutor exposes one-click prompts and learning-page context", () => {
  const floating = read("src/components/ai/floating-ai-button.tsx");
  const tutor = read("src/components/ai/tutor-chat.tsx");

  assert.match(floating, /给我讲讲这个知识点/);
  assert.match(floating, /出一道题考考我/);
  assert.match(floating, /这个难不难/);
  assert.match(floating, /useLearningStore/);
  assert.match(floating, /currentCourse/);
  assert.match(floating, /currentLesson/);
  assert.match(tutor, /quickPrompts/);
  assert.match(tutor, /sendMessage\(prompt\)/);
});
