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

test("Compose runs durable generation and diagnosis workers without Redis coupling", () => {
  assert.match(
    compose,
    /generation-worker:[\s\S]*?command:\s*\["python",\s*"run_generation_worker\.py"\]/,
  );
  const diagnosisWorker = compose.match(
    /diagnosis-worker:([\s\S]*?)(?=\n\s{2}[a-zA-Z][\w-]*:|\nnetworks:)/,
  );
  assert.ok(diagnosisWorker, "diagnosis-worker service must exist");
  assert.match(
    diagnosisWorker[1],
    /command:\s*\["python",\s*"run_diagnosis_worker\.py"\]/,
  );
  assert.doesNotMatch(diagnosisWorker[1], /redis:/);
  assert.match(diagnosisWorker[1], /postgres:[\s\S]*?condition:\s*service_healthy/);
});
