import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { pollDiagnosis } from "../src/components/learning/diagnosis-polling.mjs";

const page = readFileSync(new URL("../src/app/(main)/ai-questions/page.tsx", import.meta.url), "utf8");
const hook = readFileSync(new URL("../src/components/learning/use-diagnosis-polling.ts", import.meta.url), "utf8");
const stepInput = readFileSync(new URL("../src/components/learning/solution-steps-input.tsx", import.meta.url), "utf8");
const diagnosisResult = readFileSync(new URL("../src/components/learning/diagnosis-result.tsx", import.meta.url), "utf8");
const apiClient = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("diagnosis polling advances from pending to success at one-second intervals", async () => {
  const responses = [
    { job_id: "job-1", state: "pending", message: "处理中" },
    { job_id: "job-1", state: "succeeded", diagnosis: { status: "diagnosed" } },
  ];
  const delays = [];
  const result = await pollDiagnosis({
    jobId: "job-1",
    questionId: "q-1",
    request: async () => responses.shift(),
    sleep: async (milliseconds) => delays.push(milliseconds),
    isCurrent: (jobId, questionId) => jobId === "job-1" && questionId === "q-1",
  });

  assert.equal(result.state, "succeeded");
  assert.deepEqual(delays, [1_000]);
});

test("diagnosis polling stops after ten pending attempts", async () => {
  let calls = 0;
  const result = await pollDiagnosis({
    jobId: "job-timeout",
    questionId: "q-1",
    request: async () => ({ job_id: "job-timeout", state: "pending" }),
    sleep: async () => {},
    isCurrent: () => true,
    onAttempt: () => calls++,
  });

  assert.equal(calls, 10);
  assert.deepEqual(result, {
    job_id: "job-timeout",
    state: "timeout",
    message: "诊断仍在处理中，请稍后查看。",
  });
});

test("diagnosis polling cancels on unmount and rejects stale question results", async () => {
  const controller = new AbortController();
  controller.abort();
  const cancelled = await pollDiagnosis({
    jobId: "job-abort",
    questionId: "q-1",
    signal: controller.signal,
    request: async () => assert.fail("aborted polling must not request"),
    sleep: async () => {},
    isCurrent: () => true,
  });
  const stale = await pollDiagnosis({
    jobId: "job-old",
    questionId: "q-old",
    request: async () => ({ job_id: "job-old", state: "succeeded" }),
    sleep: async () => {},
    isCurrent: () => false,
  });

  assert.equal(cancelled.state, "cancelled");
  assert.equal(stale.state, "stale");
});

test("diagnosis polling exposes only a fixed terminal failure and api client owns 401 refresh", async () => {
  const failed = await pollDiagnosis({
    jobId: "job-failed",
    questionId: "q-1",
    request: async () => ({
      job_id: "job-failed",
      state: "failed",
      message: "provider-secret-stack",
    }),
    sleep: async () => {},
    isCurrent: () => true,
  });

  assert.deepEqual(failed, {
    job_id: "job-failed",
    state: "failed",
    message: "诊断暂时未完成，请稍后重试。",
  });
  assert.match(hook, /apiClient\.get<DiagnosisJobResponse>/);
  assert.match(hook, /\/v1\/adaptive\/diagnoses\/jobs\/\$\{currentJobId\}/);
  assert.match(hook, /AbortController/);
  assert.match(apiClient, /AbortSignal\.any\(\[controller\.signal, externalSignal\]\)/);
});

test("adaptive UI renders step input and all three diagnosis states", () => {
  assert.match(stepInput, /MAX_SOLUTION_STEPS\s*=\s*12/);
  assert.match(stepInput, /添加一步/);
  assert.match(stepInput, /删除第/);
  assert.match(diagnosisResult, /正在分析你的解题步骤/);
  assert.match(diagnosisResult, /从第 \{diagnosis\.first_invalid_step\} 步开始/);
  assert.match(diagnosisResult, /现有信息还不足以确定具体错因/);
  assert.match(diagnosisResult, /为什么推荐下一步/);
  assert.match(page, /SolutionStepsInput/);
  assert.match(page, /confidence/);
  assert.match(page, /DiagnosisResult/);
});
