"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { MainLayout } from "@/components/layout/main-layout";
import { CourseCard } from "@/components/common/course-card";
import { EmptyState } from "@/components/common/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { motion } from "framer-motion";
import {
  BookOpen,
  CheckCircle2,
  Clock,
  GraduationCap,
  Play,
  Trophy,
  Compass,
} from "lucide-react";
import { cn, getSubjectBgClass } from "@/lib/utils";
import { SUBJECT_LABELS } from "@/types";
import { useLearningStore } from "@/stores/learning-store";

export default function LearningPage() {
  const { courses, isLoading, fetchCourses } = useLearningStore();

  // 页面加载时获取课程列表
  useEffect(() => {
    fetchCourses();
  }, [fetchCourses]);

  // 有进度但未完成的课程（继续学习）
  const inProgressCourses = courses.filter(
    (c) => c.progress > 0 && c.progress < 100
  );
  // 已完成的课程
  const completedCourses = courses.filter((c) => c.progress === 100);
  // 尚未开始的推荐课程
  const notStartedCourses = courses.filter((c) => c.progress === 0);

  // 统计数据
  const totalCourses = courses.length;
  const totalCompleted = completedCourses.length;
  const totalInProgress = inProgressCourses.length;
  const overallProgress =
    totalCourses > 0
      ? Math.round(courses.reduce((sum, c) => sum + c.progress, 0) / totalCourses)
      : 0;

  return (
    <MainLayout>
      <div className="space-y-8">
        {/* 页面标题 */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">我的学习</h1>
          <p className="mt-1 text-sm text-brand-gray">
            管理你的学习进度，继续未完成的内容
          </p>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard
            icon={<BookOpen className="h-5 w-5 text-brand-blue" />}
            label="总课程"
            value={totalCourses}
            bgColor="bg-blue-50"
          />
          <StatCard
            icon={<Play className="h-5 w-5 text-amber-500" />}
            label="学习中"
            value={totalInProgress}
            bgColor="bg-amber-50"
          />
          <StatCard
            icon={<CheckCircle2 className="h-5 w-5 text-brand-green" />}
            label="已完成"
            value={totalCompleted}
            bgColor="bg-green-50"
          />
          <StatCard
            icon={<Trophy className="h-5 w-5 text-purple-500" />}
            label="总进度"
            value={`${overallProgress}%`}
            bgColor="bg-purple-50"
          />
        </div>

        {/* 加载骨架屏 */}
        {isLoading && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-48 w-full rounded-xl" />
            ))}
          </div>
        )}

        {/* 继续学习 */}
        {!isLoading && inProgressCourses.length > 0 && (
          <section>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">
                继续学习
              </h2>
              <span className="text-sm text-brand-gray">
                {inProgressCourses.length} 门课程进行中
              </span>
            </div>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {inProgressCourses.map((course) => (
                <ContinueCourseCard key={course.id} course={course} />
              ))}
            </div>
          </section>
        )}

        {/* 尚未开始 / 推荐课程 */}
        {!isLoading && notStartedCourses.length > 0 && (
          <section>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">
                推荐课程
              </h2>
              <Link href="/explore">
                <Button variant="ghost" size="sm" className="text-brand-blue">
                  <Compass className="mr-1 h-4 w-4" />
                  去探索
                </Button>
              </Link>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {notStartedCourses.slice(0, 8).map((course) => (
                <CourseCard key={course.id} course={course} />
              ))}
            </div>
          </section>
        )}

        {/* 已完成课程 */}
        {!isLoading && completedCourses.length > 0 && (
          <section>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">
                已完成
              </h2>
              <span className="text-sm text-brand-gray">
                {completedCourses.length} 门课程
              </span>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {completedCourses.map((course) => (
                <CourseCard key={course.id} course={course} />
              ))}
            </div>
          </section>
        )}

        {/* 空状态 */}
        {!isLoading && courses.length === 0 && (
          <EmptyState
            icon={<BookOpen className="h-12 w-12" />}
            title="还没有课程"
            description="去探索页面发现适合你的课程，开始学习之旅吧！"
            actionLabel="去探索"
            href="/explore"
          />
        )}
      </div>
    </MainLayout>
  );
}

/** 统计卡片 */
function StatCard({
  icon,
  label,
  value,
  bgColor,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  bgColor: string;
}) {
  return (
    <Card className="shadow-card">
      <CardContent className="flex items-center gap-3 p-4">
        <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl", bgColor)}>
          {icon}
        </div>
        <div>
          <p className="text-lg font-bold text-gray-900">{value}</p>
          <p className="text-xs text-brand-gray">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}

/** 继续学习卡片（横向布局 + 进度） */
function ContinueCourseCard({ course }: { course: import("@/types").Course }) {
  const subjectBg = getSubjectBgClass(course.subject);
  const courseUrl = `/learning/${course.slug || course.id}`;

  return (
    <Link href={courseUrl}>
      <motion.div whileHover={{ y: -2 }} transition={{ duration: 0.2 }}>
        <Card className="group cursor-pointer overflow-hidden transition-all hover:shadow-card-hover">
          <CardContent className="flex gap-4 p-4">
            {/* 学科色块 */}
            <div
              className={cn(
                "flex h-16 w-16 shrink-0 items-center justify-center rounded-xl",
                subjectBg,
              )}
            >
              <span className="text-sm font-bold text-gray-700">
                {SUBJECT_LABELS[course.subject]}
              </span>
            </div>

            {/* 信息 */}
            <div className="flex-1 overflow-hidden">
              <h3 className="truncate text-sm font-semibold text-gray-900 group-hover:text-brand-blue">
                {course.title}
              </h3>
              <div className="mt-1 flex items-center gap-3 text-xs text-brand-gray">
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {course.duration}分钟
                </span>
                <span className="flex items-center gap-1">
                  <GraduationCap className="h-3 w-3" />
                  {course.completedLessons}/{course.totalLessons}课时
                </span>
              </div>
              <div className="mt-2">
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="text-brand-gray">学习进度</span>
                  <span className="font-medium text-brand-blue">{course.progress}%</span>
                </div>
                <Progress value={course.progress} className="h-1.5" />
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </Link>
  );
}
