import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const packageJson = JSON.parse(
  readFileSync(new URL("../package.json", import.meta.url), "utf8"),
);

test("frontend exposes stable local and CI verification adapters", () => {
  assert.equal(packageJson.scripts.test, "node --test tests/*.test.mjs");
  assert.equal(packageJson.scripts.typecheck, "tsc --noEmit");
  assert.equal(packageJson.scripts.e2e, "playwright test");
});

test("browser verification keeps failure evidence", () => {
  assert.equal(packageJson.scripts["e2e:report"], "playwright show-report");
  assert.ok(packageJson.devDependencies["@playwright/test"]);
  assert.ok(packageJson.devDependencies["@axe-core/playwright"]);
});

test("browser verification exercises the public gateway", () => {
  const config = readFileSync(new URL("../playwright.config.ts", import.meta.url), "utf8");
  assert.match(config, /PLAYWRIGHT_BASE_URL \|\| "http:\/\/localhost"/);
});

test("frontend build and CI use the supported Node runtime floor", () => {
  const dockerfile = readFileSync(new URL("../Dockerfile", import.meta.url), "utf8");
  assert.match(dockerfile, /FROM node:20-alpine AS deps/);
  assert.match(dockerfile, /FROM node:20-alpine AS builder/);
  assert.match(dockerfile, /FROM node:20-alpine AS runner/);
  assert.equal(packageJson.engines.node, ">=20.19.0");
});

test("repository exposes the same blocking verification entry to local and CI adapters", () => {
  const root = path.resolve(import.meta.dirname, "../..");
  const workflowPath = path.join(root, ".github/workflows/verify.yml");
  assert.equal(existsSync(workflowPath), true, ".github/workflows/verify.yml should exist");

  const makefile = readFileSync(path.join(root, "Makefile"), "utf8");
  const workflow = readFileSync(workflowPath, "utf8");
  assert.match(makefile, /^verify-ci:/m);
  assert.match(makefile, /^docker-smoke:/m);
  assert.match(makefile, /^test-backend-isolated:/m);
  assert.match(workflow, /python scripts\/verify\.py full/);
  assert.match(workflow, /PLAYWRIGHT_BASE_URL:\s*http:\/\/localhost\s*$/m);
  assert.doesNotMatch(workflow, /PLAYWRIGHT_BASE_URL:\s*http:\/\/localhost:3000/);
  assert.doesNotMatch(workflow, /continue-on-error:\s*true/);
});
