"use client";

import { CheckCircle2, ChevronRight, Lightbulb, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getDifficultyMeta } from "./answer-feedback-meta";
import { RewardSummary, type GamificationReward } from "@/components/gamification/reward-summary";

export interface FeedbackQuestion {
  id: string;
  correctAnswer: string;
  explanation?: string;
  knowledgePoints?: string[];
  difficulty?: "beginner" | "intermediate" | "advanced" | string;
}

interface AnswerFeedbackProps {
  isCorrect: boolean;
  question: FeedbackQuestion;
  userAnswer: string;
  onExplain: () => void;
  onNext: () => void;
  gamification?: GamificationReward | null;
}

export function AnswerFeedback({ isCorrect, question, userAnswer, onExplain, onNext, gamification }: AnswerFeedbackProps) {
  const difficulty = getDifficultyMeta(question.difficulty);

  return (
    <section
      aria-live="polite"
      className={cn(
        "rounded-xl border-2 p-4 sm:p-5",
        isCorrect ? "border-emerald-200 bg-emerald-50" : "border-rose-200 bg-rose-50",
      )}
    >
      <div className="flex items-start gap-3">
        {isCorrect ? <CheckCircle2 className="mt-0.5 h-7 w-7 text-emerald-600" /> : <XCircle className="mt-0.5 h-7 w-7 text-rose-600" />}
        <div>
          <h3 className={cn("text-lg font-bold", isCorrect ? "text-emerald-800" : "text-rose-800")}>
            {isCorrect ? "答对了！" : "这次还差一点"}
          </h3>
          <p className="text-sm text-gray-700">{isCorrect ? "思路很棒，继续保持。" : "没关系，理解解析后再继续。"}</p>
        </div>
      </div>

      {!isCorrect && (
        <div className="mt-4 rounded-lg bg-white/90 p-3">
          <p className="text-xs font-medium text-gray-600">你的答案：{userAnswer || "未作答"}</p>
          <p className="mt-1 text-sm font-semibold text-emerald-700">正确答案：{question.correctAnswer}</p>
        </div>
      )}

      {question.explanation && (
        <div className="mt-3 rounded-lg bg-white/90 p-3">
          <p className="text-sm font-semibold text-gray-800">解析</p>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-gray-700">{question.explanation}</p>
        </div>
      )}

      <RewardSummary reward={gamification} />

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {question.knowledgePoints?.map((point) => <Badge key={point} variant="subject" className="bg-blue-100 text-blue-800">{point}</Badge>)}
        <Badge className={difficulty.className}>{difficulty.label}</Badge>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <Button variant="outline" onClick={onExplain} className="border-brand-blue text-brand-blue hover:bg-blue-50">
          <Lightbulb className="mr-2 h-4 w-4" />听 AI 讲解
        </Button>
        <Button onClick={onNext}>
          下一题<ChevronRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </section>
  );
}
