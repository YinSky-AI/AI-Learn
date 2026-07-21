import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const client = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("token refresh uses the backend snake-case contract", () => {
  assert.match(client, /JSON\.stringify\(\{\s*refresh_token:/);
});

test("concurrent refresh waiters share a promise that can reject", () => {
  assert.match(client, /refreshPromise:\s*Promise<string>\s*\|\s*null/);
  assert.doesNotMatch(client, /refreshSubscribers/);
});
