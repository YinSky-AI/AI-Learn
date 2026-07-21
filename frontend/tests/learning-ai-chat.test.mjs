import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const store = readFileSync(new URL("../src/stores/learning-store.ts", import.meta.url), "utf8");

test("course AI chat renders the current JSON multi-role tutor response", () => {
  assert.match(store, /response\.headers\.get\(["']content-type["']\)/);
  assert.match(store, /application\/json/);
  assert.match(store, /tutorResponse\.messages/);
  assert.match(store, /tutorResponse\.suggested_next_step/);
});
