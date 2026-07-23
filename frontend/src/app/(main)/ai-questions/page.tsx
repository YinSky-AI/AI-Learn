"use client";

import { FormEvent, useState } from "react";
import { CheckCircle2, Loader2, Sparkles } from "lucide-react";
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

const SUBJECTS = [
  ["SUBJ_MATH", "数学"], ["SUBJ_CHINESE", "语文"], ["SUBJ_ENGLISH", "英语"],
  ["SUBJ_SCIENCE", "科学"], ["SUBJ_PHYSICS", "物理"], ["SUBJ_CHEMISTRY", "化学"],
  ["SUBJ_PROGRAMMING", "编程"], ["SUBJ_HISTORY", "历史"], ["SUBJ_GEOGRAPHY", "地理"],
];

function getErrorMessage(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return "AI 出题暂时没有完成，请稍后再试。";
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

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!topic.trim() || loading) return;
    setLoading(true);
    setError("");
    setQuestions([]);
    setAnswers({});
    try {
      const result = await apiClient.post<GenerateResult>("/v1/questions/generate", {
        age_group_code: ageGroup,
        subject_code: subject,
        course_topic: topic.trim(),
        difficulty_level: difficulty,
        question_types: [questionType],
        question_count: count,
        learning_goal: `围绕${topic.trim()}进行适龄练习`,
      });
      setQuestions(result.questions || []);
      setBatchId(result.batch_id);
      if (!result.questions?.length) setError("题目已经生成，但没有通过审题，请调整主题后再试。");
    } catch (cause) {
      setError(getErrorMessage(cause));
    } finally {
      setLoading(false);
    }
  }

  function selectOption(question: GeneratedQuestion, key: string) {
    if (question.question_type !== "MULTIPLE_CHOICE") {
      setAnswers((current) => ({ ...current, [question.id]: key }));
      return;
    }
    const selected = new Set((answers[question.id] || "").split(",").filter(Boolean));
    selected.has(key) ? selected.delete(key) : selected.add(key);
    setAnswers((current) => ({
      ...current,
      [question.id]: Array.from(selected).sort().join(","),
    }));
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
            <input value={topic} onChange={(event) => setTopic(event.target.value)} maxLength={200} required placeholder="例如：小学分数加法" className="mt-2 min-h-11 w-full rounded-lg border border-gray-300 px-3 outline-none focus:border-brand-blue focus:ring-2 focus:ring-blue-100" />
          </label>
          <label className="text-sm font-medium text-gray-800">学科
            <select value={subject} onChange={(event) => setSubject(event.target.value)} className="mt-2 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3">
              {SUBJECTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-gray-800">年龄段
            <select value={ageGroup} onChange={(event) => setAgeGroup(event.target.value)} className="mt-2 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3">
              <option value="AGE_06_08">6–8 岁</option><option value="AGE_09_11">9–11 岁</option><option value="AGE_12_14">12–14 岁</option><option value="AGE_15_18">15–18 岁</option>
            </select>
          </label>
          <label className="text-sm font-medium text-gray-800">难度
            <select value={difficulty} onChange={(event) => setDifficulty(event.target.value)} className="mt-2 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3">
              <option value="DIFF_EASY">简单</option><option value="DIFF_MEDIUM">中等</option><option value="DIFF_HARD">困难</option>
            </select>
          </label>
          <label className="text-sm font-medium text-gray-800">题型
            <select value={questionType} onChange={(event) => setQuestionType(event.target.value)} className="mt-2 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3">
              <option value="CHOICE">单选题</option><option value="MULTIPLE_CHOICE">多选题</option><option value="FILL_BLANK">填空题</option>
            </select>
          </label>
          <label className="text-sm font-medium text-gray-800">题目数量
            <select value={count} onChange={(event) => setCount(Number(event.target.value))} className="mt-2 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3">
              {[1, 2, 3, 5].map((value) => <option key={value} value={value}>{value} 道</option>)}
            </select>
          </label>
          <div className="flex items-end">
            <Button type="submit" disabled={loading || !topic.trim()} className="min-h-11 w-full">
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
              return (
                <article key={question.id} className="rounded-2xl border bg-white p-5 shadow-sm">
                  <div className="flex flex-wrap gap-2"><Badge>第 {index + 1} 题</Badge><Badge variant="outline">{question.question_type}</Badge><Badge variant="outline">审题已通过</Badge></div>
                  <h3 className="mt-4 text-base font-semibold leading-7 text-gray-900">{question.question_body}</h3>
                  {question.options?.length ? (
                    <div className="mt-4 grid gap-2 sm:grid-cols-2">
                      {question.options.map((option) => (
                        <button
                          key={option.key}
                          type="button"
                          aria-pressed={selected.has(option.key)}
                          onClick={() => selectOption(question, option.key)}
                          className={`rounded-lg border p-3 text-left text-sm transition ${selected.has(option.key) ? "border-brand-blue bg-blue-50 text-blue-800" : "bg-gray-50 hover:bg-gray-100"}`}
                        >
                          <span className="mr-2 font-semibold text-brand-blue">{option.key}.</span>{option.value}
                        </button>
                      ))}
                    </div>
                  ) : question.question_type === "FILL_BLANK" ? (
                    <label className="mt-4 block text-sm text-gray-600">
                      填空 1
                      <input
                        className="mt-2 min-h-11 w-full rounded-lg border border-gray-300 px-3 outline-none focus:border-brand-blue focus:ring-2 focus:ring-blue-100"
                        value={answers[question.id] || ""}
                        onChange={(event) => setAnswers((current) => ({ ...current, [question.id]: event.target.value }))}
                        placeholder="请输入这一空的答案"
                        maxLength={500}
                      />
                    </label>
                  ) : null}
                  {question.knowledge_tags?.length ? <div className="mt-4 flex flex-wrap gap-2">{question.knowledge_tags.map((tag) => <Badge key={tag} variant="secondary">{tag}</Badge>)}</div> : null}
                </article>
              );
            })}
          </section>
        )}
      </main>
    </MainLayout>
  );
}
