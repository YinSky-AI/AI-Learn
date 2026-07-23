"use client";

import { FormEvent, useState } from "react";
import { CheckCircle2, Loader2, Sparkles, XCircle } from "lucide-react";
import { MainLayout } from "@/components/layout/main-layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import apiClient from "@/lib/api-client";

type GeneratedQuestion = {
  id: string;
  question_body: string;
  question_type: string;
  difficulty_level: string;
  options?: Array<{ key: string; value: string }>;
  quality_status: string;
  knowledge_tags?: string[];
};

type GenerateResult = {
  batch_id: string;
  status: string;
  total_generated: number;
  questions: GeneratedQuestion[];
};

type GeneratedPracticeSubmitResult = {
  submission_id: string;
  batch_id: string;
  total_count: number;
  correct_count: number;
  accuracy_rate: number;
  time_spent_seconds: number;
  results: Array<{
    question_id: string;
    is_correct: boolean;
    correct_answer: string;
    explanation?: string | null;
  }>;
  gamification: Record<string, unknown>;
};

type PracticeSubmissionState = "answering" | "submitting" | "submitted" | "error";

const SUBJECTS = [
  ["SUBJ_MATH", "数学"], ["SUBJ_CHINESE", "语文"], ["SUBJ_ENGLISH", "英语"],
  ["SUBJ_SCIENCE", "科学"], ["SUBJ_PHYSICS", "物理"], ["SUBJ_CHEMISTRY", "化学"],
  ["SUBJ_PROGRAMMING", "编程"], ["SUBJ_HISTORY", "历史"], ["SUBJ_GEOGRAPHY", "地理"],
];

function getQuestionTypeLabel(questionType: string): string {
  switch (questionType) {
    case "CHOICE":
      return "单选题";
    case "MULTIPLE_CHOICE":
      return "多选题";
    case "FILL_BLANK":
      return "填空题";
    default:
      return "练习题";
  }
}

function getErrorMessage(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string" && message.includes("aborted")) {
      return "AI 出题等待超时，请稍后重试。";
    }
  }
  return "AI 出题暂时没有完成，请稍后再试。";
}

function getSubmissionErrorMessage(error: unknown): string {
  const detail = error && typeof error === "object" ? error as { code?: unknown; message?: unknown; name?: unknown } : {};
  const code = typeof detail.code === "number" ? detail.code : Number(detail.code);
  const message = typeof detail.message === "string" ? detail.message.toLowerCase() : "";

  if (detail.name === "AbortError" || message.includes("abort") || message.includes("timeout")) {
    return "提交超时，请稍后重试。";
  }
  if (code === 401 || code === 403) {
    return "登录状态已失效，请重新登录后提交。";
  }
  if (code === 409 || code === 422 || message.includes("review") || message.includes("validation")) {
    return "题目审核或答案校验未通过，请重新出题后再试。";
  }
  if (code === 502 || code === 503 || message.includes("provider") || message.includes("unavailable")) {
    return "出题服务暂时不可用，请稍后再试。";
  }
  return "答案提交失败，请稍后重试。";
}

export default function AIQuestionsPage() {
  const [topic, setTopic] = useState("");
  const [subject, setSubject] = useState("SUBJ_MATH");
  const [ageGroup, setAgeGroup] = useState("AGE_09_11");
  const [difficulty, setDifficulty] = useState("DIFF_MEDIUM");
  const [questionType, setQuestionType] = useState("CHOICE");
  const [count, setCount] = useState(1);
  const [questions, setQuestions] = useState<GeneratedQuestion[]>([]);
  const [batchId, setBatchId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [questionStartedAt, setQuestionStartedAt] = useState<Record<string, number>>({});
  const [batchStartedAt, setBatchStartedAt] = useState<number | null>(null);
  const [practiceState, setPracticeState] = useState<PracticeSubmissionState>("answering");
  const [submissionId, setSubmissionId] = useState<string | null>(null);
  const [submissionResult, setSubmissionResult] = useState<GeneratedPracticeSubmitResult | null>(null);

  const isAnswerLocked = practiceState === "submitting" || practiceState === "submitted";
  const answersComplete = questions.length > 0 && questions.every((question) => Boolean(answers[question.id]?.trim()));

  function resetPractice() {
    setQuestions([]);
    setBatchId("");
    setAnswers({});
    setQuestionStartedAt({});
    setBatchStartedAt(null);
    setPracticeState("answering");
    setSubmissionId(null);
    setSubmissionResult(null);
  }

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!topic.trim() || loading || isAnswerLocked) return;
    setLoading(true);
    setError("");
    resetPractice();
    try {
      const result = await apiClient.post<GenerateResult>("/v1/questions/generate", {
        age_group_code: ageGroup,
        subject_code: subject,
        course_topic: topic.trim(),
        difficulty_level: difficulty,
        question_types: [questionType],
        question_count: count,
        learning_goal: `围绕${topic.trim()}进行适龄练习`,
      }, { timeout: 90_000 });
      const startedAt = Date.now();
      const generatedQuestions = result.questions || [];
      setQuestions(generatedQuestions);
      setBatchId(result.batch_id);
      setBatchStartedAt(startedAt);
      setQuestionStartedAt(Object.fromEntries(generatedQuestions.map((question) => [question.id, startedAt])));
      if (!generatedQuestions.length) setError("题目已经生成，但没有通过审题，请调整主题后再试。");
    } catch (cause) {
      setError(getErrorMessage(cause));
    } finally {
      setLoading(false);
    }
  }

  function updateAnswer(questionId: string, answer: string | ((currentAnswer: string) => string)) {
    if (isAnswerLocked) return;
    setAnswers((current) => ({
      ...current,
      [questionId]: typeof answer === "function" ? answer(current[questionId] || "") : answer,
    }));
    setSubmissionId(null);
    setSubmissionResult(null);
    setError("");
    setPracticeState("answering");
  }

  function selectOption(question: GeneratedQuestion, key: string) {
    if (question.question_type !== "MULTIPLE_CHOICE") {
      updateAnswer(question.id, key);
      return;
    }
    updateAnswer(question.id, (currentAnswer) => {
      const selected = new Set(currentAnswer.split(",").filter(Boolean));
      selected.has(key) ? selected.delete(key) : selected.add(key);
      return Array.from(selected).sort().join(",");
    });
  }

  async function submitAnswers() {
    if (!batchId || !answersComplete || isAnswerLocked) return;
    const activeSubmissionId = submissionId || crypto.randomUUID();
    if (!submissionId) setSubmissionId(activeSubmissionId);
    setPracticeState("submitting");
    setError("");
    const submittedAt = Date.now();
    try {
      const result = await apiClient.post<GeneratedPracticeSubmitResult>(
        `/v1/questions/batches/${batchId}/submit`,
        {
          submission_id: activeSubmissionId,
          answers: questions.map((question) => ({
            question_id: question.id,
            user_answer: answers[question.id].trim(),
            time_spent_seconds: Math.max(0, Math.round((submittedAt - (questionStartedAt[question.id] || batchStartedAt || submittedAt)) / 1000)),
          })),
        },
      );
      setSubmissionResult(result);
      setPracticeState("submitted");
    } catch (cause) {
      setPracticeState("error");
      setError(getSubmissionErrorMessage(cause));
    }
  }

  return (
    <MainLayout>
      <main className="mx-auto max-w-5xl space-y-6 pb-20 md:pb-8">
        <section className="rounded-2xl bg-gradient-to-r from-blue-600 to-violet-600 p-6 text-white shadow-lg">
          <div className="flex items-start gap-3">
            <Sparkles className="mt-1 h-7 w-7" aria-hidden />
            <div>
              <h1 className="text-2xl font-bold">AI 智能出题</h1>
              <p className="mt-2 text-sm leading-6 text-white/85">
                出题 Agent 先生成结构化题目，审题 Agent 再检查答案、难度、适龄性与完整性；只有审核通过的题目才会展示。
              </p>
            </div>
          </div>
        </section>

        <form onSubmit={generate} className="grid gap-4 rounded-2xl border bg-white p-5 shadow-sm sm:grid-cols-2">
          <label className="sm:col-span-2 text-sm font-medium text-gray-800">
            想练习的主题
            <input value={topic} onChange={(event) => setTopic(event.target.value)} disabled={loading || isAnswerLocked} maxLength={200} required placeholder="例如：小学分数加法" className="mt-2 min-h-11 w-full rounded-lg border border-gray-300 px-3 outline-none focus:border-brand-blue focus:ring-2 focus:ring-blue-100" />
          </label>
          <label className="text-sm font-medium text-gray-800">学科
            <select value={subject} onChange={(event) => setSubject(event.target.value)} disabled={loading || isAnswerLocked} className="mt-2 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3">
              {SUBJECTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-gray-800">年龄段
            <select value={ageGroup} onChange={(event) => setAgeGroup(event.target.value)} disabled={loading || isAnswerLocked} className="mt-2 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3">
              <option value="AGE_06_08">6–8 岁</option><option value="AGE_09_11">9–11 岁</option><option value="AGE_12_14">12–14 岁</option><option value="AGE_15_18">15–18 岁</option>
            </select>
          </label>
          <label className="text-sm font-medium text-gray-800">难度
            <select value={difficulty} onChange={(event) => setDifficulty(event.target.value)} disabled={loading || isAnswerLocked} className="mt-2 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3">
              <option value="DIFF_EASY">简单</option><option value="DIFF_MEDIUM">中等</option><option value="DIFF_HARD">困难</option>
            </select>
          </label>
          <label className="text-sm font-medium text-gray-800">题型
            <select value={questionType} onChange={(event) => setQuestionType(event.target.value)} disabled={loading || isAnswerLocked} className="mt-2 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3">
              <option value="CHOICE">单选题</option><option value="MULTIPLE_CHOICE">多选题</option><option value="FILL_BLANK">填空题</option>
            </select>
          </label>
          <label className="text-sm font-medium text-gray-800">题目数量
            <select value={count} onChange={(event) => setCount(Number(event.target.value))} disabled={loading || isAnswerLocked} className="mt-2 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3">
              {[1, 2, 3, 5].map((value) => <option key={value} value={value}>{value} 道</option>)}
            </select>
          </label>
          <div className="flex items-end">
            <Button type="submit" disabled={loading || isAnswerLocked || !topic.trim()} className="min-h-11 w-full">
              {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />两位 Agent 正在协作…</> : <><Sparkles className="mr-2 h-4 w-4" />开始出题</>}
            </Button>
          </div>
        </form>

        {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</p>}

        {questions.length > 0 && (
          <section aria-live="polite" className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-bold text-gray-900">审核通过的题目</h2>
              <span className="flex items-center gap-1 text-xs text-emerald-700"><CheckCircle2 className="h-4 w-4" />共 {questions.length} 道 · 批次 {batchId.slice(0, 8)}</span>
            </div>
            {questions.map((question, index) => {
              const selected = new Set((answers[question.id] || "").split(",").filter(Boolean));
              const result = submissionResult?.results.find((item) => item.question_id === question.id);
              return (
                <article key={question.id} className="rounded-2xl border bg-white p-5 shadow-sm">
                  <div className="flex flex-wrap gap-2"><Badge>第 {index + 1} 题</Badge><Badge variant="outline">{getQuestionTypeLabel(question.question_type)}</Badge><Badge variant="outline">审题已通过</Badge></div>
                  <h3 className="mt-4 text-base font-semibold leading-7 text-gray-900">{question.question_body}</h3>
                  {question.question_type === "FILL_BLANK" ? (
                    <label className="mt-4 block text-sm text-gray-600">
                      填空 1
                      <input className="mt-2 min-h-11 w-full rounded-lg border border-gray-300 px-3 outline-none focus:border-brand-blue focus:ring-2 focus:ring-blue-100" value={answers[question.id] || ""} onChange={(event) => updateAnswer(question.id, event.target.value)} disabled={isAnswerLocked} placeholder="请输入这一空的答案" maxLength={500} />
                    </label>
                  ) : question.options?.length ? (
                    <div className="mt-4 grid gap-2 sm:grid-cols-2">
                      {question.options.map((option) => (
                        <button key={option.key} type="button" aria-pressed={selected.has(option.key)} disabled={isAnswerLocked} onClick={() => selectOption(question, option.key)} className={`rounded-lg border p-3 text-left text-sm transition ${selected.has(option.key) ? "border-brand-blue bg-blue-50 text-blue-800" : "bg-gray-50 hover:bg-gray-100"} ${isAnswerLocked ? "cursor-not-allowed opacity-80" : ""}`}>
                          <span className="mr-2 font-semibold text-brand-blue">{option.key}.</span>{option.value}
                        </button>
                      ))}
                    </div>
                  ) : null}
                  {result && (
                    <div className={`mt-4 rounded-xl border p-4 text-sm ${result.is_correct ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-rose-200 bg-rose-50 text-rose-800"}`}>
                      <p className="flex items-center gap-2 font-semibold">{result.is_correct ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}服务端判定：{result.is_correct ? "回答正确" : "回答错误"}</p>
                      <p className="mt-2">正确答案：{result.correct_answer}</p>
                      {result.explanation && <p className="mt-2">解析：{result.explanation}</p>}
                    </div>
                  )}
                  {question.knowledge_tags?.length ? <div className="mt-4 flex flex-wrap gap-2">{question.knowledge_tags.map((tag) => <Badge key={tag} variant="secondary">{tag}</Badge>)}</div> : null}
                </article>
              );
            })}
            {submissionResult ? (
              <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-sm text-emerald-900">
                <h3 className="font-bold">本次练习结果</h3>
                <div className="mt-3 grid gap-2 sm:grid-cols-4"><span>总题数：{submissionResult.total_count}</span><span>正确数：{submissionResult.correct_count}</span><span>正确率：{Math.round(submissionResult.accuracy_rate * 100)}%</span><span>用时：{submissionResult.time_spent_seconds} 秒</span></div>
                <Button type="button" variant="outline" className="mt-4" onClick={resetPractice}>重新出题</Button>
              </section>
            ) : (
              <div className="rounded-2xl border bg-white p-5">
                {!answersComplete && <p className="mb-3 text-sm text-gray-600">请完成全部题目后再提交。</p>}
                <Button type="button" disabled={!answersComplete || practiceState === "submitting"} onClick={() => void submitAnswers()} className="min-h-11 w-full">
                  {practiceState === "submitting" ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />正在提交答案…</> : "提交全部答案"}
                </Button>
              </div>
            )}
          </section>
        )}
      </main>
    </MainLayout>
  );
}
