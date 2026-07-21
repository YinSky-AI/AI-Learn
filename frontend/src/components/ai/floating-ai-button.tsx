"use client";

import dynamic from "next/dynamic";
import { usePathname, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { MessageCircle, Minus, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLearningStore } from "@/stores/learning-store";
import { cn } from "@/lib/utils";
import type { TutorQuestionContext } from "@/types/api";

const TutorChat = dynamic(
  () => import("./tutor-chat").then((module) => module.TutorChat),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-sm text-slate-500">
        AI 辅导老师正在准备…
      </div>
    ),
  },
);

const QUICK_PROMPTS = ["给我讲讲这个知识点", "出一道题考考我", "这个难不难"];
type PanelState = "closed" | "open" | "minimized";

/** 全站可用的 AI 辅导入口；学习页会自动附带当前课程和课时上下文。 */
export function FloatingAIButton() {
  const pathname = usePathname();
  const router = useRouter();
  const currentCourse = useLearningStore((state) => state.currentCourse);
  const currentLesson = useLearningStore((state) => state.currentLesson);
  const [panelState, setPanelState] = useState<PanelState>("closed");

  const isLearningPage = pathname === "/learning" || pathname.startsWith("/learning/");
  const questionContext = useMemo<TutorQuestionContext | undefined>(() => {
    if (!isLearningPage || !currentLesson) return undefined;
    return {
      id: currentLesson.id,
      question_text: [currentLesson.title, currentLesson.description].filter(Boolean).join("："),
      knowledge_points: currentLesson.knowledgeNodeId ? [currentLesson.knowledgeNodeId] : undefined,
      difficulty: currentCourse?.difficulty,
      subject: currentCourse?.subject,
    };
  }, [currentCourse?.difficulty, currentCourse?.subject, currentLesson, isLearningPage]);

  const learningLabel = isLearningPage
    ? [currentCourse?.title, currentLesson?.title].filter(Boolean).join(" · ")
    : "随时提问，四位 AI 导师协同辅导";

  return (
    <>
      {panelState !== "open" && (
        <button
          type="button"
          onClick={() => setPanelState("open")}
          aria-label={panelState === "minimized" ? "恢复 AI 辅导老师" : "打开 AI 辅导老师"}
          className={cn(
            "fixed bottom-20 right-4 z-40 flex min-h-14 items-center justify-center rounded-full bg-gradient-to-r from-blue-600 to-violet-600 text-white shadow-lg transition hover:scale-105 hover:shadow-xl focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-blue-200 active:scale-95 lg:bottom-8 lg:right-8",
            panelState === "minimized" ? "gap-2 px-4" : "h-14 w-14",
          )}
        >
          <MessageCircle className="h-6 w-6" aria-hidden />
          {panelState === "minimized" && <span className="text-sm font-medium">继续对话</span>}
        </button>
      )}

      {panelState !== "closed" && (
        <aside
          role="dialog"
          aria-label="AI 辅导老师对话面板"
          aria-hidden={panelState === "minimized"}
          className={cn(
            "fixed inset-x-3 bottom-20 top-20 z-40 flex flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl lg:bottom-8 lg:left-auto lg:right-8 lg:top-auto lg:h-[min(720px,calc(100vh-4rem))] lg:w-[420px]",
            panelState === "minimized" && "hidden",
          )}
        >
          <header className="flex shrink-0 items-start gap-3 bg-gradient-to-r from-blue-600 to-violet-600 px-4 py-3 text-white">
            <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/15">
              <Sparkles className="h-5 w-5" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <h2 className="font-semibold">AI 辅导老师</h2>
              <p className="truncate text-xs text-white/80" title={learningLabel}>{learningLabel}</p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-9 w-9 shrink-0 text-white hover:bg-white/15 hover:text-white"
              onClick={() => setPanelState("minimized")}
              aria-label="最小化 AI 辅导老师"
            >
              <Minus className="h-4 w-4" aria-hidden />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-9 w-9 shrink-0 text-white hover:bg-white/15 hover:text-white"
              onClick={() => setPanelState("closed")}
              aria-label="关闭 AI 辅导老师"
            >
              <X className="h-4 w-4" aria-hidden />
            </Button>
          </header>

          <div className="min-h-0 flex-1">
            <TutorChat
              topic={isLearningPage ? currentCourse?.subject : undefined}
              questionContext={questionContext}
              courseId={isLearningPage ? currentCourse?.id : undefined}
              lessonId={isLearningPage ? currentLesson?.id : undefined}
              quickPrompts={QUICK_PROMPTS}
              onQuickPrompt={(prompt) => {
                if (!prompt.includes("出一道题")) return false;
                setPanelState("closed");
                router.push("/ai-questions");
                return true;
              }}
              showHeader={false}
              className="h-full rounded-none border-0"
            />
          </div>
        </aside>
      )}
    </>
  );
}
