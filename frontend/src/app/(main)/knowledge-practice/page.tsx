"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AlertCircle, ArrowLeft, BookOpen, CheckCircle2, RotateCw } from "lucide-react";
import { MainLayout } from "@/components/layout/main-layout";
import { mapQuizQuestion, type QuizQuestionPayload } from "@/components/learning/quiz-question-mapper";
import QuizPractice from "@/components/quiz/quiz-practice";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { apiClient } from "@/lib/api-client";

interface KnowledgePracticePayload {
  graph_node_id: string;
  knowledge_node_id: string;
  name: string;
  subject: string;
  difficulty_level: string;
  questions: QuizQuestionPayload[];
}

interface CompletionResult {
  correctCount: number;
  totalCount: number;
  accuracy: number;
  timeSpentSeconds: number;
}

const SUBJECT_NAMES: Record<string, string> = {
  math: "数学",
  chinese: "语文",
  english: "英语",
};

export default function KnowledgePracticePage() {
  return (
    <Suspense fallback={<PageShell><LoadingState /></PageShell>}>
      <KnowledgePracticeContent />
    </Suspense>
  );
}

function KnowledgePracticeContent() {
  const searchParams = useSearchParams();
  const graphNodeId = searchParams.get("node_id")?.trim() ?? "";
  const requestedName = searchParams.get("name")?.trim() ?? "";
  const subject = searchParams.get("subject")?.trim() ?? "";
  const [practice, setPractice] = useState<KnowledgePracticePayload | null>(null);
  const [completion, setCompletion] = useState<CompletionResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!graphNodeId || !requestedName || !subject) {
      setError("专项练习链接无效，请返回知识图谱重新选择。");
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    setError("");
    setPractice(null);
    setCompletion(null);
    apiClient
      .get<KnowledgePracticePayload>(`/v1/knowledge-graph/${graphNodeId}/practice`, {
        subject,
        name: requestedName,
      })
      .then((data) => active && setPractice(data))
      .catch(() => active && setError("专项练习暂时无法加载，请稍后重试。"))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [graphNodeId, reloadKey, requestedName, subject]);

  const questions = useMemo(
    () =>
      (practice?.questions ?? [])
        .map((question) => mapQuizQuestion(question, SUBJECT_NAMES[subject] ?? subject))
        .filter((question): question is NonNullable<typeof question> => question !== null),
    [practice, subject],
  );

  return (
    <PageShell>
      <header className="space-y-3">
        <Button asChild variant="ghost" className="-ml-3 min-h-[44px]">
          <Link href="/knowledge-graph"><ArrowLeft className="mr-2 h-4 w-4" />返回知识图谱</Link>
        </Button>
        <div>
          <p className="text-sm font-medium text-brand-blue">{SUBJECT_NAMES[subject] ?? "专项"}练习</p>
          <h1 className="mt-1 flex items-center gap-2 text-2xl font-bold text-gray-900">
            <BookOpen className="h-7 w-7 text-brand-blue" />
            {practice?.name || requestedName || "知识点专项练习"}
          </h1>
          <p className="mt-1 text-sm text-brand-gray">答案由服务端判定，完成后会同步更新掌握度、经验和错题记录。</p>
        </div>
      </header>

      {loading ? (
        <LoadingState />
      ) : error ? (
        <Card className="border-rose-100 bg-rose-50 shadow-card">
          <CardContent className="flex min-h-[280px] flex-col items-center justify-center gap-4 text-center">
            <AlertCircle className="h-10 w-10 text-rose-400" />
            <p role="alert" className="text-sm text-rose-700">{error}</p>
            <Button variant="outline" onClick={() => setReloadKey((value) => value + 1)}>
              <RotateCw className="mr-2 h-4 w-4" />重新加载
            </Button>
          </CardContent>
        </Card>
      ) : !practice || questions.length === 0 ? (
        <Card className="shadow-card">
          <CardContent className="flex min-h-[280px] flex-col items-center justify-center gap-4 text-center">
            <BookOpen className="h-10 w-10 text-gray-300" />
            <p className="text-sm text-brand-gray">这个知识点暂时没有可练习的题目。</p>
            <Button asChild variant="outline"><Link href="/knowledge-graph">选择其他知识点</Link></Button>
          </CardContent>
        </Card>
      ) : completion ? (
        <Card className="border-emerald-100 bg-emerald-50 shadow-card">
          <CardContent className="flex min-h-[280px] flex-col items-center justify-center gap-4 p-6 text-center">
            <CheckCircle2 className="h-12 w-12 text-emerald-500" />
            <div>
              <h2 className="text-xl font-bold text-gray-900">专项练习已完成</h2>
              <p className="mt-2 text-sm text-emerald-700">
                答对 {completion.correctCount} / {completion.totalCount} 题，正确率 {completion.accuracy}%
              </p>
            </div>
            <div className="flex w-full max-w-sm flex-col gap-3 sm:flex-row">
              <Button className="flex-1" onClick={() => setReloadKey((value) => value + 1)}>再练一组</Button>
              <Button asChild variant="outline" className="flex-1"><Link href="/knowledge-graph">查看掌握度</Link></Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <QuizPractice
          questions={questions}
          knowledgeNodeId={practice.knowledge_node_id}
          difficultyLevel={practice.difficulty_level}
          onComplete={setCompletion}
        />
      )}
    </PageShell>
  );
}

function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <MainLayout>
      <main className="mx-auto max-w-4xl space-y-6">{children}</main>
    </MainLayout>
  );
}

function LoadingState() {
  return (
    <Card className="shadow-card">
      <CardContent className="flex min-h-[280px] items-center justify-center text-sm text-brand-gray">
        <RotateCw className="mr-2 h-4 w-4 animate-spin" />正在加载专项练习…
      </CardContent>
    </Card>
  );
}
