import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const challenge = readFileSync(
  new URL("../src/app/(main)/challenge/page.tsx", import.meta.url),
  "utf8",
);

test("daily challenge explains the answer interaction for every question type", () => {
  assert.match(challenge, /单选题.*请选择 1 项/);
  assert.match(challenge, /多选题.*可选择多项/);
  assert.match(challenge, /填空题.*请填写 1 个空/);
});

test("daily challenge reserves a typed filter hook without changing its API contract", () => {
  assert.match(challenge, /PracticeScope/);
  assert.match(challenge, /未来将用于每日挑战筛选/);
  assert.match(challenge, /"\/v1\/challenge\/daily\/start"/);
});
