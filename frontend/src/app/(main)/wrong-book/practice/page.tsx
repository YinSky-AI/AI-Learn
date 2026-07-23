"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, ChevronRight, RotateCcw } from "lucide-react";
import { MainLayout } from "@/components/layout/main-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import apiClient, { TokenManager } from "@/lib/api-client";
import {
  createWrongBookPracticeController,
  normalizeMultiAnswer,
} from "./practice-retry-state.mjs";

type PracticeQuestion = {
  id: string;
  question_text: string;
  question_type: "CHOICE" | "MULTIPLE_CHOICE" | "FILL_BLANK";
  options?: Array<{ key: string; value: string }>;
  subject?: string;
  difficulty?: string;
};
type PracticeResult = { is_correct: boolean; correct_answer: string; explanation?: string };

export default function WrongBookPracticePage() {
  return (
    <MainLayout>
      <Suspense fallback={<main className="mx-auto max-w-xl px-4 py-16 text-center"><p className="text-sm text-gray-500">正在加载错题…</p></main>}>
        <WrongBookPracticeContent />
      </Suspense>
    </MainLayout>
  );
}

function WrongBookPracticeContent() {
  const searchParams = useSearchParams();
  const subject = searchParams.get("subject");
  const [questions, setQuestions] = useState<PracticeQuestion[]>([]);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [selectedOptions, setSelectedOptions] = useState<Set<string>>(new Set());
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState<PracticeResult | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const practiceControllerRef = useRef(createWrongBookPracticeController());
  const question = questions[index];

  useEffect(() => {
    const loadGeneration = practiceControllerRef.current.beginLoad();
    const abortController = new AbortController();
    setQuestions([]);
    setIndex(0);
    setAnswer("");
    setSelectedOptions(new Set());
    setSubmitted(false);
    setResult(null);
    setAuthRequired(false);
    setLoadError("");
    setSubmitError("");
    setIsSubmitting(false);
    void (async () => {
      setLoading(true);
      const token = TokenManager.getAccessToken();
      if (!token || TokenManager.isTokenExpired(token)) {
        if (practiceControllerRef.current.isCurrent(loadGeneration)) {
          setAuthRequired(true);
          setLoading(false);
        }
        return;
      }
      try {
        const data = await apiClient.get<{ questions: PracticeQuestion[] }>(`/v1/wrong-book/practice?count=5${subject ? `&subject=${encodeURIComponent(subject)}` : ""}`, undefined, { signal: abortController.signal });
        if (!practiceControllerRef.current.isCurrent(loadGeneration) || abortController.signal.aborted) return;
        setQuestions(data.questions);
      } catch (cause: unknown) {
        if (!practiceControllerRef.current.isCurrent(loadGeneration) || abortController.signal.aborted) return;
        if ((cause as { code?: number }).code === 401) setAuthRequired(true);
        else setLoadError("错题练习暂时无法加载，请稍后重试。");
      } finally {
        if (practiceControllerRef.current.isCurrent(loadGeneration) && !abortController.signal.aborted) setLoading(false);
      }
    })();
    return () => abortController.abort();
  }, [subject]);

  const isMultiSelect = question?.question_type === "MULTIPLE_CHOICE";
  const canonicalAnswer = isMultiSelect ? normalizeMultiAnswer(selectedOptions) : answer.trim();

  function handleOptionChange(key: string) {
    if (submitted || isSubmitting || practiceControllerRef.current.guard.isSubmitting() || !question) return;
    setSubmitError("");
    if (question.question_type === "MULTIPLE_CHOICE") {
      setSelectedOptions((previous) => {
        const next = new Set(previous);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        setAnswer(normalizeMultiAnswer(next));
        return next;
      });
      return;
    }
    setAnswer(key);
  }

  function handleFillChange(value: string) {
    if (submitted || isSubmitting || practiceControllerRef.current.guard.isSubmitting()) return;
    setSubmitError("");
    setAnswer(value);
  }

  async function submit() {
    if (!question || !canonicalAnswer || !practiceControllerRef.current.guard.begin()) return;
    const nextAttempt = practiceControllerRef.current.prepare(question.id, canonicalAnswer);
    setIsSubmitting(true);
    setSubmitError("");
    try {
      setResult(await apiClient.post<PracticeResult>("/v1/wrong-book/practice/answer", {
        attempt_id: nextAttempt.attemptId,
        question_id: question.id,
        user_answer: nextAttempt.userAnswer,
      }));
      setSubmitted(true);
    } catch (cause: unknown) {
      if ((cause as { code?: number }).code === 401) setAuthRequired(true);
      else {
        setSubmitError(practiceControllerRef.current.fail().error);
      }
    } finally {
      practiceControllerRef.current.guard.end();
      setIsSubmitting(false);
    }
  }

  function moveToNextQuestion() {
    setIndex((previous) => (previous + 1 < questions.length ? previous + 1 : 0));
    setAnswer("");
    setSelectedOptions(new Set());
    setSubmitted(false);
    setResult(null);
    practiceControllerRef.current.resetQuestion();
    setSubmitError("");
  }

  if (loading) return <main className="mx-auto max-w-xl px-4 py-16 text-center"><div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-brand-blue border-t-transparent" /><p className="mt-3 text-sm text-gray-500">正在加载错题…</p></main>;
  if (authRequired) return <main className="mx-auto max-w-xl px-4 py-16 text-center"><h1 className="text-xl font-bold">登录后开始错题重练</h1><Button asChild className="mt-5"><Link href="/login">去登录</Link></Button></main>;
  if (loadError) return <main className="mx-auto max-w-xl px-4 py-16 text-center"><p className="text-sm text-rose-700">{loadError}</p><Button asChild variant="outline" className="mt-5"><Link href="/wrong-book">返回错题本</Link></Button></main>;
  if (!question) return <main className="mx-auto max-w-xl px-4 py-16 text-center"><CheckCircle2 className="mx-auto h-12 w-12 text-emerald-500" /><h1 className="mt-4 text-xl font-bold">当前没有可重练的错题</h1><Button asChild className="mt-5"><Link href="/wrong-book">返回错题本</Link></Button></main>;

  const typeLabel = question.question_type === "CHOICE" ? "单选题" : question.question_type === "MULTIPLE_CHOICE" ? "多选题" : "填空题";
  return <main className="mx-auto max-w-2xl space-y-5 px-4 py-8"><Link href="/wrong-book" className="text-sm text-brand-blue">← 返回错题本</Link><div className="flex justify-between"><Badge variant="outline">{question.subject || "错题练习"}</Badge><span className="text-sm text-gray-500">第 {index + 1} / {questions.length} 题</span></div><article className="rounded-2xl border bg-white p-6 shadow-sm"><Badge variant="secondary">{typeLabel}</Badge><h1 className="mt-3 text-lg font-semibold leading-7">{question.question_text}</h1><div className="mt-5 space-y-2">{question.question_type === "FILL_BLANK" ? <input className="w-full rounded-lg border p-3" value={answer} disabled={submitted || isSubmitting} onChange={(event) => handleFillChange(event.target.value)} placeholder="请输入答案" /> : question.options?.map((option) => { const selected = isMultiSelect ? selectedOptions.has(option.key) : answer === option.key; return <label key={option.key} className={`flex w-full items-center gap-3 rounded-xl border p-3 text-left ${selected ? "border-brand-blue bg-blue-50" : "border-gray-200"} ${submitted || isSubmitting ? "cursor-default opacity-70" : "cursor-pointer"}`}><input type={isMultiSelect ? "checkbox" : "radio"} name={`wrong-book-${question.id}`} checked={selected} disabled={submitted || isSubmitting} onChange={() => handleOptionChange(option.key)} />{option.key}. {option.value}</label>; })}</div>{submitError && <p role="alert" className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{submitError}</p>}{submitted && result && <p className={`mt-4 rounded-lg p-3 text-sm ${result.is_correct ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"}`}>{result.is_correct ? "回答正确，继续保持！" : `再想一想，正确答案是：${result.correct_answer}`}{result.explanation ? ` ${result.explanation}` : ""}</p>}<div className="mt-6 flex justify-end gap-2">{!submitted ? <Button disabled={!canonicalAnswer || isSubmitting} onClick={() => void submit()}>{isSubmitting ? "正在提交..." : submitError ? "重试提交" : "提交答案"}</Button> : <Button onClick={moveToNextQuestion}>{index + 1 < questions.length ? <>下一题<ChevronRight className="ml-1 h-4 w-4" /></> : <><RotateCcw className="mr-1 h-4 w-4" />再练一次</>}</Button>}</div></article></main>;
}
