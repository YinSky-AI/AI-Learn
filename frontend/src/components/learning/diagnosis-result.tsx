import { CheckCircle2, Clock3, Search, TriangleAlert } from "lucide-react";
import type { DiagnosisJobResponse } from "@/types/api";
import { MasteryChange } from "./mastery-change";

export type DiagnosisViewResult = DiagnosisJobResponse | {
  job_id: string;
  state: "timeout" | "cancelled" | "stale";
  message?: string;
};

const ACTION_LABELS: Record<string, string> = {
  ask_diagnostic_question: "补充一个关键步骤",
  review_prerequisite: "先复习前置知识",
  practice_misconception: "练习一道针对当前错因的题",
  practice_same_skill: "继续同知识点变式练习",
  increase_difficulty: "尝试更有挑战的题目",
};

const REASON_LABELS: Record<string, string> = {
  insufficient_evidence: "当前步骤证据不足",
  diagnosed_misconception: "已定位到需要巩固的错因",
  low_mastery: "当前知识点还需要巩固",
  developing_mastery: "继续同级练习有助于稳定掌握",
  high_mastery_recent_success: "近期表现稳定，可以提高难度",
  repeated_misconception: "同类错误近期重复出现",
};

export function DiagnosisResult({ result }: { result: DiagnosisViewResult }) {
  if (result.state === "pending") {
    return <div className="mt-4 flex items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800"><Clock3 className="h-4 w-4 animate-pulse" />正在分析你的解题步骤…</div>;
  }
  if (result.state === "failed" || result.state === "timeout") {
    return <div className="mt-4 flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"><TriangleAlert className="h-4 w-4" />{result.message || "诊断暂时未完成，请稍后查看。"}</div>;
  }
  if (result.state !== "succeeded" || !result.diagnosis) return null;

  const { diagnosis, next_action: nextAction } = result;
  if (diagnosis.status === "not_required") {
    return <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"><p className="flex items-center gap-2 font-semibold"><CheckCircle2 className="h-4 w-4" />本题回答正确，无需错因诊断。</p><MasteryChange mastery={result.mastery} /></div>;
  }

  return (
    <div className="mt-4 rounded-xl border border-violet-200 bg-violet-50 p-4 text-sm text-violet-900">
      {diagnosis.status === "diagnosed" ? (
        <><p className="flex items-center gap-2 font-semibold"><Search className="h-4 w-4" />从第 {diagnosis.first_invalid_step} 步开始，前后等式不再等价</p><p className="mt-2 whitespace-pre-wrap">{diagnosis.evidence}</p></>
      ) : (
        <p className="font-semibold">现有信息还不足以确定具体错因，请再补充一个中间步骤。</p>
      )}
      <MasteryChange mastery={result.mastery} />
      {nextAction && (
        <div className="mt-3 rounded-lg bg-white/80 p-3">
          <p className="font-semibold">为什么推荐下一步</p>
          <p className="mt-1">{ACTION_LABELS[nextAction.action] || "继续针对当前知识点练习"}</p>
          <ul className="mt-1 list-disc pl-5 text-xs text-gray-600">
            {nextAction.reason_codes.map((code) => REASON_LABELS[code]).filter(Boolean).map((label) => <li key={label}>{label}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
