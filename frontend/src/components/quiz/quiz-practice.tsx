/**
 * 测验练习组件 QuizPractice
 *
 * 功能说明：
 * - 支持单选题(CHOICE)、多选题(MULTIPLE_CHOICE)、填空题(FILL_BLANK)
 * - 逐题作答，提交后即时显示对错、正确答案与解析
 * - 全部完成后展示结果统计（正确数、正确率、用时）
 * - 提供"再练一次"和"完成"两种结束动作
 */

"use client";

import React, { useState, useCallback, useMemo, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { AnswerFeedback } from "@/components/learning/answer-feedback";
import { TutorChat } from "@/components/ai/tutor-chat";
import type { GamificationReward } from "@/components/gamification/reward-summary";
import apiClient from "@/lib/api-client";
import { cn } from "@/lib/utils";
import {
  CheckCircle2,
  XCircle,
  ChevronRight,
  RotateCcw,
  Trophy,
  Clock,
  HelpCircle,
  ListChecks,
  AlignLeft,
  PenLine,
} from "lucide-react";

/** 选项结构 */
export interface QuizOption {
  key: string;
  value: string;
}

/** 题目结构 */
export interface QuizQuestion {
  id: string;
  type: "CHOICE" | "MULTIPLE_CHOICE" | "FILL_BLANK";
  body: string;
  options?: QuizOption[];
  knowledgePoints?: string[];
  difficulty?: string;
  subject?: string;
}

/** 组件 Props */
interface QuizPracticeProps {
  questions: QuizQuestion[];
  knowledgeNodeId?: string;
  difficultyLevel: string;
  onComplete: (result: {
    correctCount: number;
    totalCount: number;
    accuracy: number;
    timeSpentSeconds: number;
  }) => void;
}

/** 单题结果 */
interface QuestionResult {
  isCorrect: boolean;
  userAnswer: string;
  correctAnswer: string;
  explanation?: string;
  knowledgePoints?: string[];
  difficulty?: string;
  tutorPrompt?: string;
  gamification?: GamificationReward | null;
}

interface LearningSessionPayload { id: string; }

interface AnswerResultPayload {
  is_correct: boolean;
  correct_answer: string;
  explanation?: string;
  knowledge_point?: string;
  tutor_prompt?: string;
  gamification?: GamificationReward | null;
}

/**
 * 获取题型标签与图标
 */
function getTypeMeta(type: QuizQuestion["type"]) {
  switch (type) {
    case "CHOICE":
      return { label: "单选题", icon: <ListChecks className="h-3.5 w-3.5" /> };
    case "MULTIPLE_CHOICE":
      return { label: "多选题", icon: <AlignLeft className="h-3.5 w-3.5" /> };
    case "FILL_BLANK":
      return { label: "填空题", icon: <PenLine className="h-3.5 w-3.5" /> };
    default:
      return { label: "未知", icon: <HelpCircle className="h-3.5 w-3.5" /> };
  }
}

export default function QuizPractice({
  questions,
  knowledgeNodeId,
  difficultyLevel,
  onComplete,
}: QuizPracticeProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [userAnswer, setUserAnswer] = useState<string>("");
  const [submitted, setSubmitted] = useState(false);
  const [results, setResults] = useState<Record<string, QuestionResult>>({});
  const [showSummary, setShowSummary] = useState(false);
  const [startTime, setStartTime] = useState(() => Date.now());
  const [questionStartedAt, setQuestionStartedAt] = useState(() => Date.now());
  const [selectedOptions, setSelectedOptions] = useState<Set<string>>(new Set());
  const [isTutorOpen, setIsTutorOpen] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFinishing, setIsFinishing] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const totalCount = questions.length;
  const currentQuestion = questions[currentIndex];

  // 题目变化时重置当前题状态
  useEffect(() => {
    setUserAnswer("");
    setSubmitted(false);
    setSelectedOptions(new Set());
    setQuestionStartedAt(Date.now());
    setSubmitError("");
  }, [currentIndex]);

  const progress = useMemo(
    () => (totalCount > 0 ? Math.round(((currentIndex + (submitted ? 1 : 0)) / totalCount) * 100) : 0),
    [currentIndex, submitted, totalCount]
  );

  /** 单选题选择 */
  const handleSingleSelect = useCallback((key: string) => {
    if (submitted) return;
    setUserAnswer(key);
  }, [submitted]);

  /** 多选题切换 */
  const handleMultiToggle = useCallback((key: string) => {
    if (submitted) return;
    setSelectedOptions((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      // 同步到 userAnswer（逗号分隔，按字母排序）
      const sorted = Array.from(next).sort();
      setUserAnswer(sorted.join(","));
      return next;
    });
  }, [submitted]);

  /** 填空题输入 */
  const handleFillInput = useCallback((value: string) => {
    if (submitted) return;
    setUserAnswer(value);
  }, [submitted]);

  /** 提交当前题：会话创建、判题、错题与奖励均由服务端事务完成。 */
  const handleSubmit = useCallback(async () => {
    if (!currentQuestion || !userAnswer.trim() || isSubmitting) return;
    setIsSubmitting(true);
    setSubmitError("");
    try {
      let activeSessionId = sessionId;
      if (!activeSessionId) {
        if (!knowledgeNodeId) throw new Error("该课时未绑定知识点");
        const session = await apiClient.post<LearningSessionPayload>(
          "/v1/learning/sessions",
          { knowledge_node_id: knowledgeNodeId, difficulty_level: difficultyLevel }
        );
        activeSessionId = session.id;
        setSessionId(activeSessionId);
      }

      const answer = await apiClient.post<AnswerResultPayload>(
        `/v1/learning/sessions/${activeSessionId}/answer`,
        {
          question_id: currentQuestion.id,
          answer_id: crypto.randomUUID(),
          user_answer: userAnswer,
          time_spent_seconds: Math.max(0, Math.round((Date.now() - questionStartedAt) / 1000)),
        }
      );
      setResults((previous) => ({
        ...previous,
        [currentQuestion.id]: {
          isCorrect: answer.is_correct,
          userAnswer,
          correctAnswer: answer.correct_answer,
          explanation: answer.explanation,
          knowledgePoints: answer.knowledge_point
            ? [answer.knowledge_point]
            : currentQuestion.knowledgePoints,
          difficulty: currentQuestion.difficulty,
          tutorPrompt: answer.tutor_prompt,
          gamification: answer.gamification,
        },
      }));
      setSubmitted(true);
    } catch {
      setSubmitError("答案提交失败，请稍后重试。");
    } finally {
      setIsSubmitting(false);
    }
  }, [currentQuestion, difficultyLevel, isSubmitting, knowledgeNodeId, questionStartedAt, sessionId, userAnswer]);

  /** 进入下一题 */
  const handleNext = useCallback(() => {
    if (currentIndex < totalCount - 1) {
      setCurrentIndex((prev) => prev + 1);
    } else {
      setShowSummary(true);
    }
  }, [currentIndex, totalCount]);

  const handleExplain = useCallback(() => {
    setIsTutorOpen(true);
  }, []);

  /** 再练一次 */
  const handleRetry = useCallback(async () => {
    setSubmitError("");
    if (sessionId) {
      try {
        await apiClient.post(`/v1/learning/sessions/${sessionId}/complete`, {});
      } catch {
        setSubmitError("本次测验暂时无法结算，请稍后重试。");
        return;
      }
    }
    setCurrentIndex(0);
    setUserAnswer("");
    setSubmitted(false);
    setResults({});
    setShowSummary(false);
    setSelectedOptions(new Set());
    setSessionId(null);
    setStartTime(Date.now());
    setQuestionStartedAt(Date.now());
  }, [sessionId]);

  /** 完成测验 */
  const handleFinish = useCallback(async () => {
    if (isFinishing) return;
    setIsFinishing(true);
    setSubmitError("");
    try {
      if (sessionId) {
        await apiClient.post(`/v1/learning/sessions/${sessionId}/complete`, {});
      }
    const correctCount = Object.values(results).filter((r) => r.isCorrect).length;
    const timeSpentSeconds = Math.round((Date.now() - startTime) / 1000);
    onComplete({
      correctCount,
      totalCount,
      accuracy: totalCount > 0 ? Math.round((correctCount / totalCount) * 100) : 0,
      timeSpentSeconds,
    });
    } catch {
      setSubmitError("本次测验暂时无法结算，请稍后重试。");
    } finally {
      setIsFinishing(false);
    }
  }, [isFinishing, onComplete, results, sessionId, startTime, totalCount]);

  // 无题目保护
  if (!totalCount) {
    return (
      <Card className="shadow-card">
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <HelpCircle className="h-10 w-10 text-gray-300" />
          <p className="mt-3 text-sm text-brand-gray">暂无测验题目</p>
        </CardContent>
      </Card>
    );
  }

  // 结果汇总页
  if (showSummary) {
    const correctCount = Object.values(results).filter((r) => r.isCorrect).length;
    const accuracy = totalCount > 0 ? Math.round((correctCount / totalCount) * 100) : 0;
    const timeSpentSeconds = Math.round((Date.now() - startTime) / 1000);

    return (
      <Card className="shadow-card overflow-hidden">
        <CardHeader className="bg-gradient-to-r from-brand-blue to-blue-500 text-white pb-6">
          <div className="flex items-center gap-2">
            <Trophy className="h-5 w-5" />
            <CardTitle className="text-lg">测验完成</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="p-6 space-y-6">
          {/* 核心数据 */}
          <div className="grid grid-cols-3 gap-4">
            <div className="flex flex-col items-center rounded-xl bg-green-50 p-4">
              <span className="text-2xl font-bold text-green-600">{correctCount}</span>
              <span className="text-xs text-green-700 mt-1">答对题数</span>
            </div>
            <div className="flex flex-col items-center rounded-xl bg-blue-50 p-4">
              <span className="text-2xl font-bold text-brand-blue">{accuracy}%</span>
              <span className="text-xs text-blue-700 mt-1">正确率</span>
            </div>
            <div className="flex flex-col items-center rounded-xl bg-amber-50 p-4">
              <span className="text-2xl font-bold text-amber-600">{timeSpentSeconds}</span>
              <span className="text-xs text-amber-700 mt-1">用时(秒)</span>
            </div>
          </div>

          {/* 每题回顾 */}
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-gray-900">答题回顾</h4>
            <div className="space-y-2 max-h-[240px] overflow-y-auto pr-1">
              {questions.map((q, idx) => {
                const r = results[q.id];
                if (!r) return null;
                return (
                  <div
                    key={q.id}
                    className={cn(
                      "flex items-start gap-3 rounded-lg border p-3 text-sm",
                      r.isCorrect
                        ? "border-green-200 bg-green-50/50"
                        : "border-red-200 bg-red-50/50"
                    )}
                  >
                    {r.isCorrect ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
                    ) : (
                      <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 truncate">
                        {idx + 1}. {q.body}
                      </p>
                      {!r.isCorrect && (
                        <p className="mt-1 text-xs text-red-600">
                          正确答案：{r.correctAnswer} &nbsp;|&nbsp; 你的答案：{r.userAnswer || "未作答"}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 操作按钮 */}
          {submitError && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{submitError}</p>}
          <div className="flex gap-3">
            <Button variant="outline" className="flex-1" disabled={isFinishing} onClick={() => void handleRetry()}>
              <RotateCcw className="mr-2 h-4 w-4" />
              再练一次
            </Button>
            <Button className="flex-1" disabled={isFinishing} onClick={() => void handleFinish()}>
              <CheckCircle2 className="mr-2 h-4 w-4" />
              完成
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const typeMeta = getTypeMeta(currentQuestion.type);
  const currentResult = results[currentQuestion.id];

  return (
    <Card className="shadow-card overflow-hidden">
      {/* 顶部进度 */}
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="gap-1">
              {typeMeta.icon}
              {typeMeta.label}
            </Badge>
            <span className="text-xs text-brand-gray">
              第 {currentIndex + 1} / {totalCount} 题
            </span>
          </div>
          <span className="text-xs font-medium text-brand-blue">{progress}%</span>
        </div>
        <Progress value={progress} className="h-2" />
      </CardHeader>

      <CardContent className="p-6 pt-0 space-y-5">
        {/* 题干 */}
        <AnimatePresence mode="wait">
          <motion.div
            key={currentQuestion.id}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.25 }}
          >
            <h3 className="text-base font-medium text-gray-900 leading-relaxed">
              {currentIndex + 1}. {currentQuestion.body}
            </h3>
          </motion.div>
        </AnimatePresence>

        {/* 选项区域 */}
        <AnimatePresence mode="wait">
          <motion.div
            key={currentQuestion.id + "-options"}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.25, delay: 0.05 }}
            className="space-y-2"
          >
            {currentQuestion.type === "FILL_BLANK" ? (
              <div className="pt-1">
                <Input
                  placeholder="请输入你的答案..."
                  value={userAnswer}
                  onChange={(e) => handleFillInput(e.target.value)}
                  disabled={submitted}
                  className={cn(
                    "h-11",
                    submitted &&
                      (currentResult?.isCorrect
                        ? "border-green-400 focus-visible:ring-green-200"
                        : "border-red-400 focus-visible:ring-red-200")
                  )}
                />
              </div>
            ) : (
              currentQuestion.options?.map((option) => {
                const isSelected =
                  currentQuestion.type === "CHOICE"
                    ? userAnswer === option.key
                    : selectedOptions.has(option.key);

                let statusClass = "";
                if (submitted) {
                  const correctKeys = (currentResult?.correctAnswer || "")
                    .split(/[,，]/)
                    .map((s) => s.trim().toUpperCase());
                  if (correctKeys.includes(option.key.toUpperCase())) {
                    statusClass = "border-green-400 bg-green-50 text-green-700";
                  } else if (isSelected) {
                    statusClass = "border-red-400 bg-red-50 text-red-700";
                  }
                } else if (isSelected) {
                  statusClass = "border-brand-blue bg-blue-50 text-brand-blue";
                }

                return (
                  <button
                    key={option.key}
                    disabled={submitted}
                    onClick={() =>
                      currentQuestion.type === "CHOICE"
                        ? handleSingleSelect(option.key)
                        : handleMultiToggle(option.key)
                    }
                    className={cn(
                      "flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all",
                      "hover:border-gray-300 hover:bg-gray-50",
                      statusClass || "border-gray-200 bg-white text-gray-700",
                      submitted && "cursor-default"
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
                        isSelected && !submitted
                          ? "border-brand-blue bg-brand-blue text-white"
                          : submitted && statusClass.includes("green")
                          ? "border-green-400 bg-green-500 text-white"
                          : submitted && statusClass.includes("red")
                          ? "border-red-400 bg-red-500 text-white"
                          : "border-gray-300 text-gray-500"
                      )}
                    >
                      {option.key}
                    </span>
                    <span className="text-sm">{option.value}</span>
                    {submitted && statusClass.includes("green") && (
                      <CheckCircle2 className="ml-auto h-4 w-4 text-green-500" />
                    )}
                    {submitted && statusClass.includes("red") && (
                      <XCircle className="ml-auto h-4 w-4 text-red-500" />
                    )}
                  </button>
                );
              })
            )}
          </motion.div>
        </AnimatePresence>

        {/* 提交后反馈 */}
        <AnimatePresence>
          {submitted && currentResult && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <AnswerFeedback
                isCorrect={currentResult.isCorrect}
                userAnswer={currentResult.userAnswer}
                question={{
                  id: currentQuestion.id,
                  correctAnswer: currentResult.correctAnswer,
                  explanation: currentResult.explanation,
                  knowledgePoints: currentResult.knowledgePoints,
                  difficulty: currentResult.difficulty,
                }}
                gamification={currentResult.gamification}
                onExplain={handleExplain}
                onNext={handleNext}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* 操作区 */}
        {submitError && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{submitError}</p>}
        <div className="flex items-center justify-between pt-2">
          {!submitted ? (
            <Button
              className="ml-auto"
              disabled={!userAnswer.trim() || isSubmitting}
              onClick={() => void handleSubmit()}
            >
              {isSubmitting ? "正在提交..." : "提交答案"}
            </Button>
          ) : null}
        </div>
      </CardContent>
      {currentResult && (
        <Dialog open={isTutorOpen} onOpenChange={setIsTutorOpen}>
          <DialogContent className="max-w-2xl p-0 sm:max-w-2xl">
            <TutorChat
              topic={currentQuestion.subject}
              isCorrect={currentResult.isCorrect}
              userAnswer={currentResult.userAnswer}
              questionContext={{
                id: currentQuestion.id,
                question_text: currentQuestion.body,
                correct_answer: currentResult.correctAnswer,
                explanation: currentResult.explanation,
                knowledge_points: currentResult.knowledgePoints,
                difficulty: currentResult.difficulty,
                subject: currentQuestion.subject,
              }}
              initialPrompt={currentResult.tutorPrompt || (currentResult.isCorrect ? "我答对了，想进一步理解这道题的思路。" : "我这道题答错了，请带我一步步找出问题。")}
            />
          </DialogContent>
        </Dialog>
      )}
    </Card>
  );
}
