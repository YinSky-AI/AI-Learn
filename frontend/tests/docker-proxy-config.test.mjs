import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const dockerfile = readFileSync(new URL("../Dockerfile", import.meta.url), "utf8");
const compose = readFileSync(new URL("../../docker-compose.yml", import.meta.url), "utf8");

test("Docker build injects the backend service URL into Next rewrites", () => {
  assert.match(dockerfile, /ARG API_PROXY_TARGET/);
  assert.match(dockerfile, /ENV API_PROXY_TARGET=\$API_PROXY_TARGET/);
  assert.match(
    compose,
    /frontend:[\s\S]*?build:[\s\S]*?args:[\s\S]*?API_PROXY_TARGET:\s*http:\/\/backend:8000/,
  );
});
