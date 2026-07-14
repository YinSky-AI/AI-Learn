/**
 * 课程卡片组件
 *
 * 功能说明：
 * - 展示课程封面（学科色块）、标题、时长、评分、难度标签
 * - 支持三种变体：默认（纵向）、compact（紧凑）、horizontal（横向）
 * - 显示学习进度条和已完成课时数
 * - 悬停时带浮起动画效果（framer-motion）
 * - 点击跳转课程详情页
 */

"use client";

import React from "react";
import Link from "next/link";
import { Clock, Star, Users } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn, formatDuration, getSubjectBgClass, getDifficultyColor } from "@/lib/utils";
import { SUBJECT_LABELS, DIFFICULTY_LABELS } from "@/types";
import type { Course } from "@/types";
import { motion } from "framer-motion";

/** 课程卡片属性 */
interface CourseCardProps {
  course: Course;
  className?: string;
  variant?: "default" | "compact" | "horizontal";
}

/**
 * 课程卡片组件
 * @param course - 课程数据
 * @param className - 额外类名
 * @param variant - 卡片变体（default / compact / horizontal）
 * @returns 课程卡片
 */
export function CourseCard({ course, className, variant = "default" }: CourseCardProps) {
  const subjectBg = getSubjectBgClass(course.subject);
  const courseUrl = `/learning/${course.slug || course.id}`;

  // 横向布局（用于继续学习列表）
  if (variant === "horizontal") {
    return (
      <Link href={courseUrl}>
        <Card
          className={cn(
            "group cursor-pointer transition-all hover:shadow-card-hover",
            className,
          )}
        >
          <CardContent className="flex gap-4 p-4">
            {/* 学科色块 */}
            <div
              className={cn(
                "flex h-20 w-20 shrink-0 items-center justify-center rounded-xl",
                subjectBg,
              )}
            >
              <span className="text-lg font-bold text-gray-700">
                {SUBJECT_LABELS[course.subject]}
              </span>
            </div>
            {/* 课程信息 */}
            <div className="flex-1 overflow-hidden">
              <h3 className="truncate text-sm font-semibold text-gray-900 group-hover:text-brand-blue">
                {course.title}
              </h3>
              <div className="mt-1 flex items-center gap-3 text-xs text-brand-gray">
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {formatDuration(course.duration)}
                </span>
                <span className="flex items-center gap-1">
                  <Users className="h-3 w-3" />
                  {course.enrollCount}人
                </span>
              </div>
              <div className="mt-2">
                <Progress value={course.progress} className="h-1.5" />
                <p className="mt-0.5 text-right text-xs text-brand-gray">
                  {course.progress}%
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </Link>
    );
  }

  // 默认/紧凑布局（纵向卡片）
  return (
    <Link href={courseUrl}>
      <motion.div
        whileHover={{ y: -4 }}
        transition={{ duration: 0.2 }}
      >
        <Card
          className={cn(
            "group cursor-pointer overflow-hidden transition-all hover:shadow-card-hover",
            className,
          )}
        >
          {/* 顶部学科色块 */}
          <div className={cn("relative h-32", subjectBg)}>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-2xl font-bold text-gray-600/60">
                {SUBJECT_LABELS[course.subject]}
              </span>
            </div>
            {/* 难度标签 */}
            <Badge
              className={cn("absolute right-3 top-3", getDifficultyColor(course.difficulty))}
            >
              {DIFFICULTY_LABELS[course.difficulty]}
            </Badge>
          </div>

          <CardContent className={cn("p-4", variant === "compact" && "p-3")}>
            {/* 标题 */}
            <h3
              className={cn(
                "font-semibold text-gray-900 group-hover:text-brand-blue",
                variant === "compact" ? "text-sm" : "text-base",
              )}
            >
              {course.title}
            </h3>

            {/* 标签信息 */}
            <div className="mt-2 flex items-center gap-2 text-xs text-brand-gray">
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatDuration(course.duration)}
              </span>
              <span className="flex items-center gap-1">
                <Star className="h-3 w-3 text-amber-400" />
                {course.rating.toFixed(1)}
              </span>
            </div>

            {/* 进度条（仅在有进度时显示） */}
            {course.progress > 0 && (
              <div className="mt-3">
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="text-brand-gray">
                    {course.completedLessons}/{course.totalLessons} 课时
                  </span>
                  <span className="font-medium text-brand-blue">{course.progress}%</span>
                </div>
                <Progress value={course.progress} className="h-1.5" />
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </Link>
  );
}
