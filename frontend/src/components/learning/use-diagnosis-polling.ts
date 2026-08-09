"use client";

import { useEffect, useRef, useState } from "react";
import apiClient from "@/lib/api-client";
import type { DiagnosisJobResponse } from "@/types/api";
import { pollDiagnosis } from "./diagnosis-polling.mjs";
import type { DiagnosisViewResult } from "./diagnosis-result";

export function useDiagnosisPolling(jobId: string | null, questionId: string) {
  const [result, setResult] = useState<DiagnosisViewResult | null>(null);
  const activeKeyRef = useRef("");

  useEffect(() => {
    if (!jobId) {
      setResult(null);
      return;
    }
    const key = `${jobId}:${questionId}`;
    activeKeyRef.current = key;
    const controller = new AbortController();
    setResult({ job_id: jobId, state: "pending", message: "诊断处理中" });

    void pollDiagnosis({
      jobId,
      questionId,
      signal: controller.signal,
      request: (currentJobId: string, signal: AbortSignal) =>
        apiClient.get<DiagnosisJobResponse>(
          `/v1/adaptive/diagnoses/${currentJobId}`,
          undefined,
          { signal },
        ),
      isCurrent: () => activeKeyRef.current === key,
    }).then((nextResult: DiagnosisViewResult) => {
      if (nextResult.state !== "cancelled" && nextResult.state !== "stale" && activeKeyRef.current === key) {
        setResult(nextResult);
      }
    });

    return () => {
      controller.abort();
      if (activeKeyRef.current === key) activeKeyRef.current = "";
    };
  }, [jobId, questionId]);

  return result;
}
