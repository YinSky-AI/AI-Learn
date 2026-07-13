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

interface CourseCardProps {
  course: Course;
  className?: string;
  variant?: "default" | "compact" | "horizontal";
}

export function CourseCard({ course, className, variant = "default" }: CourseCardProps) {
  const subjectBg = getSubjectBgClass(course.subject);
  const courseUrl = `/learning/${course.slug || course.id}`;

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
            {/* 信息 */}
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

            {/* 进度条 */}
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
