"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Clock3, Medal, Sparkles, Target, Trophy } from "lucide-react";
import { MainLayout } from "@/components/layout/main-layout";
import { Button } from "@/components/ui/button";
import apiClient from "@/lib/api-client";

type PracticeScope = {
  ageGroup: string;
  subject: string;
  topic: string;
  difficulty: string;
  questionType: string;
};

// 未来将用于每日挑战筛选；当前每日挑战仍使用服务端统一题目，保证排行榜公平。
const futurePracticeScope: PracticeScope = {
  ageGroup: "",
  subject: "",
  topic: "",
  difficulty: "",
  questionType: "",
};

type Option = { key: string; value: string };
type Question = {
  id: string;
  position: number;
  question_body: string;
  question_type: string;
  options: Option[];
};
type Challenge = {
  completed: boolean;
  replayed: boolean;
  expired?: boolean;
  time_limit_seconds: number;
  remaining_seconds: number;
  questions?: Question[];
  score?: number;
  base_score?: number;
  bonus_score?: number;
  speed_bonus?: number;
  streak_bonus?: number;
  rank?: number;
  correct_count?: number;
  total_count?: number;
  time_spent_seconds?: number;
};

function errorMessage(error: unknown, fallback: string) {
  if (error && typeof error === "object" && "message" in error) {
    return String(error.message);
  }
  return fallback;
}

export default function ChallengePage() {
  return (
    <MainLayout>
      <ChallengeContent />
    </MainLayout>
  );
}

function ChallengeContent() {
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [remaining, setRemaining] = useState(0);
  const submitEventId = useRef("");
  const autoSubmitted = useRef(false);
  const typeInstruction = (question: Question) => {
    if (question.question_type === "MULTIPLE_CHOICE") return "多选题 · 可选择多项";
    if (question.question_type === "FILL_BLANK") return "填空题 · 请填写 1 个空";
    return "单选题 · 请选择 1 项";
  };

  useEffect(() => {
    if (!challenge || challenge.completed) return;
    setRemaining(challenge.remaining_seconds);
    const timer = window.setInterval(
      () => setRemaining((value) => Math.max(0, value - 1)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [challenge]);

  const start = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiClient.post<Challenge>("/v1/challenge/daily/start");
      submitEventId.current = crypto.randomUUID();
      autoSubmitted.current = false;
      setChallenge(data);
      setRemaining(data.remaining_seconds);
    } catch (caught) {
      setError(errorMessage(caught, "今日挑战暂时无法开始"));
    } finally {
      setLoading(false);
    }
  };

  const submit = useCallback(async () => {
    if (!challenge?.questions || loading) return;
    if (!submitEventId.current) submitEventId.current = crypto.randomUUID();
    setLoading(true);
    setError("");
    try {
      const data = await apiClient.post<Challenge>("/v1/challenge/daily/submit", {
        event_id: submitEventId.current,
        answers: challenge.questions.map((question) => ({
          question_id: question.id,
          selected_answer: answers[question.id] || "",
        })),
      });
      setChallenge(data);
    } catch (caught) {
      setError(errorMessage(caught, "提交失败，请稍后重试"));
    } finally {
      setLoading(false);
    }
  }, [answers, challenge, loading]);

  useEffect(() => {
    if (
      remaining !== 0 ||
      !challenge?.questions ||
      challenge.completed ||
      autoSubmitted.current
    ) {
      return;
    }
    autoSubmitted.current = true;
    void submit();
  }, [challenge, remaining, submit]);

  const answeredCount = useMemo(
    () => challenge?.questions?.filter((question) => answers[question.id]).length || 0,
    [answers, challenge],
  );
  const allAnswered = answeredCount === (challenge?.questions?.length || 0);
  const timeProgress = challenge
    ? Math.round((remaining / Math.max(1, challenge.time_limit_seconds)) * 100)
    : 100;

  const selectOption = (question: Question, key: string) => {
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
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6 pb-8">
      <section className="overflow-hidden rounded-3xl bg-gradient-to-br from-blue-600 via-indigo-600 to-violet-600 p-7 text-white shadow-lg">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
          <div className="flex items-center gap-3">
            <span className="rounded-2xl bg-white/15 p-3"><Trophy className="h-8 w-8" /></span>
            <div>
              <h1 className="text-2xl font-bold">挑战与练习</h1>
              <p className="mt-1 text-blue-100">每日挑战计时计分；也可按自己的目标进入 AI 自定义练习。</p>
            </div>
          </div>
          {!challenge && (
            <div className="flex flex-wrap gap-2">
              <Button className="bg-white text-blue-700 hover:bg-blue-50" disabled={loading} onClick={start}>
                {loading ? "准备题目中…" : "每日挑战"}
              </Button>
              <Button variant="outline" className="border-white/50 bg-white/10 text-white hover:bg-white/20 hover:text-white" onClick={() => window.location.assign("/ai-questions")}>
                AI 自定义练习
              </Button>
            </div>
          )}
        </div>
      </section>

      {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {challenge?.completed ? (
        <section className="rounded-2xl border bg-white p-7 shadow-sm">
          <div className="text-center">
            <p className="text-sm text-gray-500">{challenge.expired ? "挑战时间已到" : "今日挑战成绩"}</p>
            <p className="mt-2 text-5xl font-black text-blue-600">{challenge.score ?? 0}</p>
            <p className="mt-3 text-gray-600">
              答对 {challenge.correct_count}/{challenge.total_count} 题 · 用时 {challenge.time_spent_seconds} 秒
            </p>
          </div>
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <ResultCard icon={<Target className="h-5 w-5" />} label="基础分" value={challenge.base_score ?? 0} />
            <ResultCard icon={<Sparkles className="h-5 w-5" />} label="奖励加成" value={challenge.bonus_score ?? 0} />
            <ResultCard icon={<Clock3 className="h-5 w-5" />} label="完成用时" value={`${challenge.time_spent_seconds ?? 0}秒`} />
            <ResultCard icon={<Medal className="h-5 w-5" />} label="今日排名" value={challenge.rank ? `#${challenge.rank}` : "--"} />
          </div>
          <div className="mt-6 flex justify-center">
            <Button variant="outline" onClick={() => window.location.assign("/leaderboard")}>查看排行榜</Button>
          </div>
        </section>
      ) : challenge?.questions ? (
        <section className="space-y-4">
          <div className="sticky top-0 z-10 rounded-xl border bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="font-medium">已作答 {answeredCount}/{challenge.questions.length}</span>
              <span className={`flex items-center gap-1 font-semibold ${remaining <= 30 ? "text-red-600" : "text-orange-600"}`}>
                <Clock3 className="h-4 w-4" />剩余 {remaining} 秒
              </span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-gray-100">
              <div className={`h-full transition-all ${remaining <= 30 ? "bg-red-500" : "bg-blue-600"}`} style={{ width: `${timeProgress}%` }} />
            </div>
          </div>

          {challenge.questions.map((question) => {
            const selected = new Set((answers[question.id] || "").split(",").filter(Boolean));
            return (
              <article key={question.id} className="rounded-2xl border bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium">{question.position}. {question.question_body}</p>
                  <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">{typeInstruction(question)}</span>
                </div>
                {question.options.length ? (
                  <div className="mt-4 grid gap-2">
                    {question.options.map((option) => (
                      <label
                        key={option.key}
                        className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-left text-sm transition ${selected.has(option.key) ? "border-blue-600 bg-blue-50 text-blue-800" : "hover:bg-gray-50"}`}
                      >
                        <input
                          type={question.question_type === "MULTIPLE_CHOICE" ? "checkbox" : "radio"}
                          name={question.id}
                          checked={selected.has(option.key)}
                          onChange={() => selectOption(question, option.key)}
                          aria-label={typeInstruction(question)}
                        />
                        {option.key}. {option.value}
                      </label>
                    ))}
                  </div>
                ) : (
                  <label className="mt-4 block text-sm text-gray-600">
                    填空 1
                    <input
                      className="mt-2 w-full rounded-lg border px-3 py-2 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                      value={answers[question.id] || ""}
                      onChange={(event) => setAnswers((current) => ({ ...current, [question.id]: event.target.value }))}
                      placeholder="请输入这一空的答案"
                      maxLength={500}
                    />
                  </label>
                )}
              </article>
            );
          })}
          <Button className="w-full" disabled={loading || (!allAnswered && remaining > 0)} onClick={() => void submit()}>
            {loading ? "正在提交…" : remaining === 0 ? "结算挑战" : "提交挑战"}
          </Button>
        </section>
      ) : null}
    </div>
  );
}

function ResultCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: number | string }) {
  return (
    <div className="rounded-xl bg-gray-50 p-3 text-center">
      <span className="mx-auto flex w-fit text-blue-600">{icon}</span>
      <p className="mt-1 text-xs text-gray-500">{label}</p>
      <p className="mt-1 font-bold text-gray-900">{value}</p>
    </div>
  );
}
