"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, ChevronRight, RotateCcw } from "lucide-react";
import { MainLayout } from "@/components/layout/main-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import apiClient, { TokenManager } from "@/lib/api-client";

type PracticeQuestion = { id: string; question_text: string; options?: Array<{ key: string; value: string }>; subject?: string; difficulty?: string };
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
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState<PracticeResult | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const question = questions[index];

  useEffect(() => { void (async () => {
    setLoading(true);
    setError("");
    const token = TokenManager.getAccessToken();
    if (!token || TokenManager.isTokenExpired(token)) { setAuthRequired(true); setLoading(false); return; }
    try { const data = await apiClient.get<{ questions: PracticeQuestion[] }>(`/v1/wrong-book/practice?count=5${subject ? `&subject=${encodeURIComponent(subject)}` : ""}`); setQuestions(data.questions); }
    catch (cause: unknown) { if ((cause as { code?: number }).code === 401) setAuthRequired(true); else setError("错题练习暂时无法加载，请稍后重试。"); }
    finally { setLoading(false); }
  })(); }, [subject]);
  async function submit() {
    if (!question || !answer.trim()) return;
    try { setResult(await apiClient.post<PracticeResult>("/v1/wrong-book/practice/answer", { question_id: question.id, user_answer: answer })); setSubmitted(true); }
    catch (cause: unknown) { if ((cause as { code?: number }).code === 401) setAuthRequired(true); else setError("答案提交失败，请稍后重试。"); }
  }
  if (loading) return <main className="mx-auto max-w-xl px-4 py-16 text-center"><div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-brand-blue border-t-transparent" /><p className="mt-3 text-sm text-gray-500">正在加载错题…</p></main>;
  if (authRequired) return <main className="mx-auto max-w-xl px-4 py-16 text-center"><h1 className="text-xl font-bold">登录后开始错题重练</h1><Button asChild className="mt-5"><Link href="/login">去登录</Link></Button></main>;
  if (error) return <main className="mx-auto max-w-xl px-4 py-16 text-center"><p className="text-sm text-rose-700">{error}</p><Button asChild variant="outline" className="mt-5"><Link href="/wrong-book">返回错题本</Link></Button></main>;
  if (!question) return <main className="mx-auto max-w-xl px-4 py-16 text-center"><CheckCircle2 className="mx-auto h-12 w-12 text-emerald-500" /><h1 className="mt-4 text-xl font-bold">当前没有可重练的错题</h1><Button asChild className="mt-5"><Link href="/wrong-book">返回错题本</Link></Button></main>;
  return <main className="mx-auto max-w-2xl space-y-5 px-4 py-8"><Link href="/wrong-book" className="text-sm text-brand-blue">← 返回错题本</Link><div className="flex justify-between"><Badge variant="outline">{question.subject || "错题练习"}</Badge><span className="text-sm text-gray-500">第 {index + 1} / {questions.length} 题</span></div><article className="rounded-2xl border bg-white p-6 shadow-sm"><h1 className="text-lg font-semibold leading-7">{question.question_text}</h1><div className="mt-5 space-y-2">{question.options?.map((option) => <button key={option.key} disabled={submitted} onClick={() => setAnswer(option.key)} className={`w-full rounded-xl border p-3 text-left ${answer === option.key ? "border-brand-blue bg-blue-50" : "border-gray-200"}`}>{option.key}. {option.value}</button>) || <input className="w-full rounded-lg border p-3" value={answer} disabled={submitted} onChange={(event) => setAnswer(event.target.value)} placeholder="请输入答案" />}</div>{submitted && result && <p className={`mt-4 rounded-lg p-3 text-sm ${result.is_correct ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"}`}>{result.is_correct ? "回答正确，继续保持！" : `再想一想，正确答案是：${result.correct_answer}`}{result.explanation ? ` ${result.explanation}` : ""}</p>}<div className="mt-6 flex justify-end gap-2">{!submitted ? <Button disabled={!answer.trim()} onClick={() => void submit()}>提交答案</Button> : <Button onClick={() => { if (index + 1 < questions.length) { setIndex(index + 1); setAnswer(""); setSubmitted(false); setResult(null); } else { setIndex(0); setAnswer(""); setSubmitted(false); setResult(null); } }}>{index + 1 < questions.length ? <>下一题 <ChevronRight className="ml-1 h-4 w-4" /></> : <><RotateCcw className="mr-1 h-4 w-4" />再练一次</>}</Button>}</div></article></main>;
}
