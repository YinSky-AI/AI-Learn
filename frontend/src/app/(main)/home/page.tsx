/**
 * 首页（仪表盘）
 *
 * 功能说明：
 * - 展示用户欢迎语、学习统计数据
 * - 搜索课程入口（支持回车跳转探索页）
 * - 继续学习课程列表和推荐课程
 * - 学习进度环形图、成就展示
 * - 使用 framer-motion 实现入场动画
 * - 已登录用户显示个性化数据，未登录显示默认数据
 */

"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { MainLayout } from "@/components/layout/main-layout";
import { StatCard } from "@/components/common/stat-card";
import { CourseCard } from "@/components/common/course-card";
import { LoadingSkeleton } from "@/components/common/loading-skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ProgressRing } from "@/components/common/progress-ring";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { useAuthStore } from "@/stores/auth-store";
import { useLearningStore } from "@/stores/learning-store";
import { getMockCourses, getWelcomeMessage } from "@/lib/content";
import {
  Clock,
  Flame,
  Star,
  Trophy,
  Zap,
  BookOpen,
  Target,
  TrendingUp,
  Search,
} from "lucide-react";
import { motion } from "framer-motion";

/**
 * 首页组件
 * @returns 仪表盘页面
 */
export default function HomePage() {
  const router = useRouter();
  const [searchValue, setSearchValue] = useState("");

  // 从认证 store 获取用户信息和统计
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const stats = useAuthStore((s) => s.stats);
  const fetchUserStats = useAuthStore((s) => s.fetchUserStats);

  // 从学习 store 获取课程列表
  const courses = useLearningStore((s) => s.courses);
  const isLoading = useLearningStore((s) => s.isLoading);
  const fetchCourses = useLearningStore((s) => s.fetchCourses);

  // 页面加载时获取课程列表和用户统计
  useEffect(() => {
    fetchCourses({ pageSize: 8 });
    if (isAuthenticated) {
      fetchUserStats();
    }
  }, [fetchCourses, isAuthenticated, fetchUserStats]);

  // 根据登录状态生成欢迎语
  const welcomeMessage = isAuthenticated
    ? getWelcomeMessage(user?.nickname || "同学")
    : "欢迎来到AI学堂";

  // 有进度但未完成的课程（继续学习）
  const continueCourses = isAuthenticated
    ? courses.filter((c) => c.progress > 0 && c.progress < 100).slice(0, 4)
    : [];

  // 推荐课程（排除已在继续学习的课程）
  const recommendedCourses = courses
    .filter((c) => !continueCourses.some((cc) => cc.id === c.id))
    .slice(0, 4);

  // 容器动画配置：子元素依次入场
  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1 },
    },
  };

  // 子元素动画配置：从下方淡入
  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 },
  };

  return (
    <MainLayout>
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="space-y-6"
      >
        {/* 欢迎横幅 */}
        <motion.div variants={item}>
          <Card className="overflow-hidden border-0 bg-gradient-to-r from-brand-blue to-blue-600 shadow-card">
            <CardContent className="p-6 text-white">
              <h1 className="text-xl font-bold lg:text-2xl">{welcomeMessage}</h1>
              <p className="mt-1 text-sm text-blue-100">
                每天坚持学习，成为更好的自己
              </p>
              <div className="mt-4 flex items-center gap-2 rounded-lg bg-white/20 backdrop-blur-sm px-3 py-2 lg:max-w-xs">
                <Search className="h-4 w-4 shrink-0 text-white/70" />
                <input
                  type="text"
                  placeholder="搜索课程、知识点..."
                  value={searchValue}
                  onChange={(e) => setSearchValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && searchValue.trim()) {
                      router.push(`/explore?keyword=${encodeURIComponent(searchValue.trim())}`);
                    }
                  }}
                  className="w-full border-none bg-transparent text-sm text-white placeholder-white/60 outline-none"
                />
              </div>
              <div className="mt-4 flex gap-4">
                <div className="rounded-lg bg-white/20 px-4 py-2 backdrop-blur-sm">
                  <p className="text-2xl font-bold">{isAuthenticated ? stats?.streak_days ?? 0 : "--"}</p>
                  <p className="text-xs text-blue-100">{isAuthenticated ? "连续学习天数" : "连续学习天数"}</p>
                </div>
                <div className="rounded-lg bg-white/20 px-4 py-2 backdrop-blur-sm">
                  <p className="text-2xl font-bold">{isAuthenticated ? (stats?.total_score ?? 0).toLocaleString() : "--"}</p>
                  <p className="text-xs text-blue-100">累计经验值</p>
                </div>
                <div className="rounded-lg bg-white/20 px-4 py-2 backdrop-blur-sm">
                  <p className="text-2xl font-bold">{isAuthenticated ? stats?.total_completed_lessons ?? 0 : "--"}</p>
                  <p className="text-xs text-blue-100">已完成课时</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* 统计卡片 */}
        <motion.div variants={item} className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard
            label="今日学习"
            value={isAuthenticated ? `${stats?.today_study_minutes ?? 0}分钟` : "0分钟"}
            icon={<Clock className="h-6 w-6" />}
            color="blue"
          />
          <StatCard
            label="本周学习"
            value={isAuthenticated ? `${stats?.week_study_hours ?? 0}小时` : "0小时"}
            icon={<TrendingUp className="h-6 w-6" />}
            trend={isAuthenticated ? { value: 12, isUp: true } : undefined}
            color="green"
          />
          <StatCard
            label="连续打卡"
            value={isAuthenticated ? `${stats?.streak_days ?? 0}天` : "0天"}
            icon={<Flame className="h-6 w-6" />}
            color="orange"
          />
          <StatCard
            label="获得经验"
            value={isAuthenticated ? `${(stats?.total_score ?? 0).toLocaleString()} XP` : "0 XP"}
            icon={<Zap className="h-6 w-6" />}
            trend={isAuthenticated ? { value: 8, isUp: true } : undefined}
            color="purple"
          />
        </motion.div>

        {/* 学习进度 + 继续学习 */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* 学习进度环 */}
          <motion.div variants={item}>
            <Card className="shadow-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">学习进度</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col items-center">
                <ProgressRing progress={isAuthenticated ? stats?.overall_progress ?? 0 : 0} size={120} strokeWidth={8}>
                  <span className="text-2xl font-bold text-gray-900">{isAuthenticated ? `${stats?.overall_progress ?? 0}%` : "0%"}</span>
                  <span className="text-xs text-brand-gray">总体进度</span>
                </ProgressRing>
                <div className="mt-4 grid w-full grid-cols-2 gap-3">
                  <div className="rounded-lg bg-blue-50 p-3 text-center">
                    <BookOpen className="mx-auto h-4 w-4 text-brand-blue" />
                    <p className="mt-1 text-sm font-semibold text-gray-900">{isAuthenticated ? `${stats?.in_progress_courses ?? 0}门` : "0门"}</p>
                    <p className="text-xs text-brand-gray">进行中</p>
                  </div>
                  <div className="rounded-lg bg-green-50 p-3 text-center">
                    <Trophy className="mx-auto h-4 w-4 text-brand-green" />
                    <p className="mt-1 text-sm font-semibold text-gray-900">{isAuthenticated ? `${stats?.completed_courses ?? 0}门` : "0门"}</p>
                    <p className="text-xs text-brand-gray">已完成</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* 继续学习 */}
          <motion.div variants={item} className="lg:col-span-2">
            <Card className="shadow-card">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-base">继续学习</CardTitle>
                <Badge
                  variant="secondary"
                  className="cursor-pointer hover:bg-gray-200 transition-colors"
                  onClick={() => router.push("/learning")}
                >
                  查看全部
                </Badge>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <LoadingSkeleton type="list" count={3} />
                ) : continueCourses.length > 0 ? (
                  <div className="space-y-3">
                    {continueCourses.map((course) => (
                      <CourseCard
                        key={course.id}
                        course={course}
                        variant="horizontal"
                      />
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center py-8">
                    <p className="text-sm text-brand-gray">暂无正在学习的课程，去探索页看看吧</p>
                    <button
                      onClick={() => router.push("/explore")}
                      className="mt-3 rounded-lg bg-brand-blue px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                    >
                      去探索课程
                    </button>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* 成就 + 推荐课程 */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* 近期成就 - 仅已登录用户显示 */}
          {isAuthenticated && (
            <motion.div variants={item}>
              <Card className="shadow-card">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">近期成就</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {(stats?.streak_days ?? 0) >= 7 ? (
                    <div className="flex items-center gap-3 rounded-xl bg-amber-50 p-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100">
                        <Flame className="h-5 w-5 text-brand-orange" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-900">连续学习7天</p>
                        <p className="text-xs text-brand-gray">坚持就是胜利</p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-3 rounded-xl bg-gray-50 p-3 opacity-40">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-200">
                        <Flame className="h-5 w-5 text-gray-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-500">连续学习7天</p>
                        <p className="text-xs text-gray-400">还需坚持{Math.max(0, 7 - (stats?.streak_days ?? 0))}天</p>
                      </div>
                    </div>
                  )}

                  {(stats?.completed_courses ?? 0) >= 1 ? (
                    <div className="flex items-center gap-3 rounded-xl bg-green-50 p-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-green-100">
                        <Trophy className="h-5 w-5 text-brand-green" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-900">完成首门课程</p>
                        <p className="text-xs text-brand-gray">好的开始是成功的一半</p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-3 rounded-xl bg-gray-50 p-3 opacity-40">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-200">
                        <Trophy className="h-5 w-5 text-gray-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-500">完成首门课程</p>
                        <p className="text-xs text-gray-400">完成你的第一门课程来解锁</p>
                      </div>
                    </div>
                  )}

                  {(stats?.total_score ?? 0) >= 100 ? (
                    <div className="flex items-center gap-3 rounded-xl bg-blue-50 p-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100">
                        <Star className="h-5 w-5 text-brand-blue" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-900">获得100经验</p>
                        <p className="text-xs text-brand-gray">学习达人</p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-3 rounded-xl bg-gray-50 p-3 opacity-40">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-200">
                        <Star className="h-5 w-5 text-gray-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-500">获得100经验</p>
                        <p className="text-xs text-gray-400">还差{Math.max(0, 100 - (stats?.total_score ?? 0))}经验</p>
                      </div>
                    </div>
                  )}

                  {(stats?.total_completed_lessons ?? 0) >= 5 ? (
                    <div className="flex items-center gap-3 rounded-xl bg-purple-50 p-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-100">
                        <Target className="h-5 w-5 text-purple-500" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-900">数学新星</p>
                        <p className="text-xs text-brand-gray">完成5节数学课</p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-3 rounded-xl bg-gray-50 p-3 opacity-40">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-200">
                        <Target className="h-5 w-5 text-gray-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-500">数学新星</p>
                        <p className="text-xs text-gray-400">还需完成{Math.max(0, 5 - (stats?.total_completed_lessons ?? 0))}节课</p>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          )}

          {/* 推荐课程 */}
          <motion.div variants={item} className={isAuthenticated ? "lg:col-span-2" : "lg:col-span-3"}>
            <Card className="shadow-card">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-base">推荐课程</CardTitle>
                <a href="/explore" className="text-sm font-medium text-brand-blue hover:underline">
                  查看更多
                </a>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <LoadingSkeleton type="course-card" count={4} />
                ) : (
                  <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
                    {recommendedCourses.map((course) => (
                      <CourseCard key={course.id} course={course} />
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </motion.div>
    </MainLayout>
  );
}
