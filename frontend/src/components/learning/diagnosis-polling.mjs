const POLL_INTERVAL_MS = 1_000;
const MAX_ATTEMPTS = 10;

function abortableSleep(milliseconds, signal) {
  return new Promise((resolve) => {
    const timeoutId = setTimeout(resolve, milliseconds);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timeoutId);
        resolve();
      },
      { once: true },
    );
  });
}

function fixedFailure(jobId) {
  return {
    job_id: jobId,
    state: "failed",
    message: "诊断暂时未完成，请稍后重试。",
  };
}

export async function pollDiagnosis({
  jobId,
  questionId,
  request,
  signal,
  sleep = abortableSleep,
  isCurrent = () => true,
  onAttempt = () => {},
}) {
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
    if (signal?.aborted) return { job_id: jobId, state: "cancelled" };
    onAttempt(attempt);

    let response;
    try {
      response = await request(jobId, signal);
    } catch (error) {
      if (signal?.aborted || error?.name === "AbortError") {
        return { job_id: jobId, state: "cancelled" };
      }
      return fixedFailure(jobId);
    }

    if (!isCurrent(jobId, questionId) || response?.job_id !== jobId) {
      return { job_id: jobId, state: "stale" };
    }
    if (response.state === "succeeded") return response;
    if (response.state === "failed") return fixedFailure(jobId);
    if (attempt < MAX_ATTEMPTS) await sleep(POLL_INTERVAL_MS, signal);
  }

  return {
    job_id: jobId,
    state: "timeout",
    message: "诊断仍在处理中，请稍后查看。",
  };
}
