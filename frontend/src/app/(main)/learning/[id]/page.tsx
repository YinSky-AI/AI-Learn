/**
 * 课程详情与学习页面
 *
 * 功能说明：
 * - 展示课程信息、课时大纲、当前课时内容
 * - 课程大纲支持点击切换课时
 * - AI 学习助手面板（SSE 流式对话）
 * - 未登录用户提示登录
 * - 完成所有课时后显示祝贺界面
 * - 支持 Markdown 内容渲染
 */

"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { MainLayout } from "@/components/layout/main-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { useLearningStore } from "@/stores/learning-store";
import { useAuthStore } from "@/stores/auth-store";
import { getSubjectBgClass, getSubjectColorClass, formatDuration } from "@/lib/utils";
import { SUBJECT_LABELS, DIFFICULTY_LABELS } from "@/types";
import {
  Play,
  CheckCircle2,
  Circle,
  Send,
  Clock,
  BookOpen,
  Star,
  Users,
  MessageSquare,
  Bot,
  Lightbulb,
  ChevronRight,
  Video,
  FileText,
  Gamepad2,
  HelpCircle,
  PartyPopper,
  Lock,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { LoadingSkeleton } from "@/components/common/loading-skeleton";
import { MarkdownRenderer } from "@/components/common/markdown-renderer";

/**
 * 课程详情与学习页面组件
 * @returns 课程学习界面
 */
export default function LearningPage() {
  const params = useParams();
  const courseId = params.id as string;

  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [loginPrompt, setLoginPrompt] = useState(false);

  // 从学习 store 获取课程详情和课时数据
  const {
    currentCourse: course,
    currentLessons: lessons,
    currentLesson,
    chatMessages,
    isAIResponding,
    isLoading,
    fetchCourseDetail,
    setCurrentLesson,
    sendAIMessage,
    startLearning,
  } = useLearningStore();

  // 根据课程 ID 加载课程详情
  useEffect(() => {
    if (courseId) {
      fetchCourseDetail(courseId);
    }
  }, [courseId, fetchCourseDetail]);

  // 加载中或课程不存在时显示骨架屏
  if (isLoading || !course) {
    return (
      <MainLayout>
        <LoadingSkeleton type="detail" />
      </MainLayout>
    );
  }

  // 判断所有课时是否已完成
  const allCompleted = lessons.length > 0 && lessons.every((l) => l.completed);

  // 计算已完成课时数和总进度
  const completedCount = lessons.filter((l) => l.completed).length;
  const progress = Math.round((completedCount / lessons.length) * 100);

  /**
   * 根据课时类型返回对应图标
   * @param type - 课时类型
   * @returns 对应的 Lucide 图标组件
   */
  const lessonTypeIcon = (type: string) => {
    switch (type) {
      case "video":
        return <Video className="h-4 w-4" />;
      case "text":
        return <FileText className="h-4 w-4" />;
      case "interactive":
        return <HelpCircle className="h-4 w-4" />;
      case "quiz":
        return <BookOpen className="h-4 w-4" />;
      case "game":
        return <Gamepad2 className="h-4 w-4" />;
      default:
        return <BookOpen className="h-4 w-4" />;
    }
  };

  return (
    <MainLayout>
      <div className="grid gap-6 lg:grid-cols-3 mb-16 md:mb-0">
        {/* 左侧：课程内容 */}
        <div className="lg:col-span-2 space-y-6">
          {/* 课程信息 */}
          <Card className="shadow-card">
            <div className={cn("h-40 rounded-t-card-md", getSubjectBgClass(course.subject))}>
              <div className="flex h-full items-center px-6">
                <div>
                  <Badge className={cn("mb-2", getSubjectColorClass(course.subject))}>
                    {SUBJECT_LABELS[course.subject]}
                  </Badge>
                  <h1 className="text-2xl font-bold text-gray-900">{course.title}</h1>
                  <div className="mt-2 flex items-center gap-4 text-sm text-brand-gray">
                    <span className="flex items-center gap-1">
                      <Clock className="h-4 w-4" />
                      {formatDuration(course.duration)}
                    </span>
                    <span className="flex items-center gap-1">
                      <Star className="h-4 w-4 text-amber-400" />
                      {course.rating.toFixed(1)}
                    </span>
                    <span className="flex items-center gap-1">
                      <Users className="h-4 w-4" />
                      {course.enrollCount}人学习
                    </span>
                  </div>
                </div>
              </div>
            </div>
            <CardContent className="p-6">
              <p className="text-sm text-gray-600">{course.description}</p>
              <div className="mt-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-brand-gray">
                    学习进度 {completedCount}/{lessons.length} 课时
                  </span>
                  <span className="font-medium text-brand-blue">{progress}%</span>
                </div>
                <Progress value={progress} className="mt-2 h-2" />
              </div>
            </CardContent>
          </Card>

          {/* 当前课时内容 */}
          {currentLesson ? (
            <Card className="shadow-card">
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <div className="flex items-center gap-2">
                  <span className="text-brand-gray">
                    第 {currentLesson.order} 课时
                  </span>
                  <ChevronRight className="h-4 w-4 text-brand-gray" />
                  <CardTitle className="text-lg">{currentLesson.title}</CardTitle>
                </div>
                <Badge variant="secondary" className="gap-1">
                  {lessonTypeIcon(currentLesson.type)}
                  {currentLesson.type === "video" ? "视频" : currentLesson.type === "text" ? "文本" : currentLesson.type === "interactive" ? "互动" : currentLesson.type === "quiz" ? "测验" : "游戏"}
                </Badge>
              </CardHeader>
              <CardContent className="p-6 pt-0">
                {/* 内容区域 */}
                <div className="rounded-xl bg-gray-50 p-6">
                  <div className="max-w-none">
                    <MarkdownRenderer content={currentLesson.content} />
                  </div>
                  <div className="mt-6 flex flex-col items-center">
                    {loginPrompt && (
                      <div className="mb-3 flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-700">
                        <Lock className="h-4 w-4 shrink-0" />
                        <span>请先登录后再开始学习</span>
                        <Link href="/login" className="ml-1 font-medium text-brand-blue hover:underline">
                          去登录
                        </Link>
                      </div>
                    )}
                    <Button className="mt-2" onClick={() => {
                      if (!isAuthenticated) {
                        setLoginPrompt(true);
                        return;
                      }
                      setLoginPrompt(false);
                      startLearning();
                    }}>
                      <Play className="mr-2 h-4 w-4" />
                      开始学习
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : allCompleted ? (
            <Card className="shadow-card">
              <CardContent className="p-8">
                <div className="flex flex-col items-center justify-center text-center">
                  <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-green/10">
                    <PartyPopper className="h-8 w-8 text-brand-green" />
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    恭喜完成全部课程!
                  </h3>
                  <p className="mt-2 text-sm text-brand-gray">
                    你已完成本课程全部 {lessons.length} 个课时，继续加油！
                  </p>
                  <Badge className="mt-4" variant="secondary">
                    <CheckCircle2 className="mr-1 h-3 w-3 text-brand-green" />
                    完成率 {progress}%
                  </Badge>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </div>

        {/* 右侧：课程大纲 + AI面板 */}
        <div className="space-y-6">
          {/* 课程大纲 */}
          <Card className="shadow-card">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">课程大纲</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[300px]">
                <div className="px-4 pb-2">
                  {lessons.map((lesson) => (
                    <button
                      key={lesson.id}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors",
                        currentLesson?.id === lesson.id
                          ? "bg-blue-50"
                          : "hover:bg-gray-50",
                      )}
                      onClick={() => setCurrentLesson(lesson)}
                    >
                      {/* 完成状态 */}
                      {lesson.completed ? (
                        <CheckCircle2 className="h-5 w-5 shrink-0 text-brand-green" />
                      ) : currentLesson?.id === lesson.id ? (
                        <Circle className="h-5 w-5 shrink-0 text-brand-blue" />
                      ) : (
                        <Circle className="h-5 w-5 shrink-0 text-gray-300" />
                      )}

                      {/* 课时信息 */}
                      <div className="flex-1 overflow-hidden">
                        <p
                          className={cn(
                            "truncate text-sm font-medium",
                            lesson.completed
                              ? "text-brand-gray line-through"
                              : "text-gray-900",
                          )}
                        >
                          {lesson.title}
                        </p>
                        <p className="text-xs text-brand-gray">
                          {lesson.duration}分钟
                        </p>
                      </div>

                      {/* 类型图标 */}
                      <span className="text-brand-gray">{lessonTypeIcon(lesson.type)}</span>
                    </button>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          {/* AI 助手面板 */}
          <Card className="shadow-card">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-100">
                  <Bot className="h-4 w-4 text-purple-600" />
                </div>
                <CardTitle className="text-base">AI 学习助手</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {/* 对话区域 */}
              <ScrollArea className="h-[250px] px-4">
                <div className="space-y-3 py-2">
                  {/* 初始提示 */}
                  {chatMessages.length === 0 && (
                    <div className="flex gap-2">
                      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-purple-100">
                        <Bot className="h-3 w-3 text-purple-600" />
                      </div>
                      <div className="rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-700">
                        你好！我是你的AI学习助手，在学习过程中有任何问题都可以问我。
                      </div>
                    </div>
                  )}

                  {/* 消息列表 */}
                  <AnimatePresence>
                    {chatMessages.map((msg) => (
                      <motion.div
                        key={msg.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className={cn(
                          "flex gap-2",
                          msg.role === "user" && "flex-row-reverse",
                        )}
                      >
                        {msg.role === "assistant" ? (
                          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-purple-100">
                            <Bot className="h-3 w-3 text-purple-600" />
                          </div>
                        ) : (
                          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-blue">
                            <span className="text-xs text-white">我</span>
                          </div>
                        )}
                        <div
                          className={cn(
                            "max-w-[80%] rounded-lg px-3 py-2 text-sm",
                            msg.role === "user"
                              ? "bg-brand-blue text-white"
                              : "bg-gray-50 text-gray-700",
                          )}
                        >
                          <MarkdownRenderer content={msg.content} />
                        </div>
                      </motion.div>
                    ))}
                  </AnimatePresence>

                  {/* AI正在输入 */}
                  {isAIResponding && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="flex gap-2"
                    >
                      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-purple-100">
                        <Bot className="h-3 w-3 text-purple-600" />
                      </div>
                      <div className="rounded-lg bg-gray-50 px-3 py-2 text-sm text-brand-gray">
                        正在思考中...
                      </div>
                    </motion.div>
                  )}
                </div>
              </ScrollArea>

              <Separator />

              {/* 输入框 */}
              <div className="flex items-center gap-2 p-3">
                <Input
                  placeholder={isAuthenticated ? "向AI助手提问..." : "登录后即可使用AI助手"}
                  className="flex-1"
                  disabled={!isAuthenticated}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && e.currentTarget.value.trim() && isAuthenticated) {
                      sendAIMessage(e.currentTarget.value.trim());
                      e.currentTarget.value = "";
                    }
                  }}
                />
                <Button
                  size="icon"
                  onClick={() => {
                    const input = document.querySelector(
                      isAuthenticated
                        ? 'input[placeholder="向AI助手提问..."]'
                        : 'input[placeholder="登录后即可使用AI助手"]',
                    ) as HTMLInputElement;
                    if (input?.value.trim() && isAuthenticated) {
                      sendAIMessage(input.value.trim());
                      input.value = "";
                    }
                  }}
                  disabled={isAIResponding || !isAuthenticated}
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>

              {/* 快捷问题 */}
              <div className="flex flex-wrap gap-1.5 px-3 pb-3">
                {[
                  "解释这个知识点",
                  "给我出个练习题",
                  "学习建议",
                ].map((suggestion) => (
                  <Button
                    key={suggestion}
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-brand-gray hover:text-brand-blue"
                    disabled={!isAuthenticated}
                    onClick={() => isAuthenticated && sendAIMessage(suggestion)}
                  >
                    <Lightbulb className="mr-1 h-3 w-3" />
                    {suggestion}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </MainLayout>
  );
}
