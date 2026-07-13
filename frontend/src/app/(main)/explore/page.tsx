"use client";

import React, { useEffect } from "react";
import { MainLayout } from "@/components/layout/main-layout";
import { CourseCard } from "@/components/common/course-card";
import { FilterBar } from "@/components/common/filter-bar";
import { LoadingSkeleton } from "@/components/common/loading-skeleton";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { useLearningStore } from "@/stores/learning-store";
import type { Subject, DifficultyLevel, AgeGroup } from "@/types";
import { Compass, SearchX } from "lucide-react";
import { motion } from "framer-motion";

export default function ExplorePage() {
  const {
    courses,
    isLoading,
    filter,
    currentPage,
    totalPages,
    fetchCourses,
    setFilter,
    resetFilter,
  } = useLearningStore();

  useEffect(() => {
    fetchCourses();
  }, [fetchCourses]);

  const handleSubjectChange = (value?: Subject) => setFilter({ subject: value });
  const handleDifficultyChange = (value?: DifficultyLevel) => setFilter({ difficulty: value });
  const handleAgeGroupChange = (value?: AgeGroup) => setFilter({ ageGroup: value });
  const handleKeywordChange = (value: string) => setFilter({ keyword: value });
  const handleSortChange = (value: string) =>
    setFilter({ sortBy: value as "popular" | "newest" | "rating" | "progress" });

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">知识探索</h1>
            <p className="mt-1 text-sm text-brand-gray">
              发现适合你的课程，开启学习之旅
            </p>
          </div>
        </div>

        {/* 筛选栏 */}
        <FilterBar
          subject={filter.subject}
          difficulty={filter.difficulty}
          ageGroup={filter.ageGroup}
          keyword={filter.keyword}
          sortBy={filter.sortBy}
          onSubjectChange={handleSubjectChange}
          onDifficultyChange={handleDifficultyChange}
          onAgeGroupChange={handleAgeGroupChange}
          onKeywordChange={handleKeywordChange}
          onSortChange={handleSortChange}
          onReset={resetFilter}
        />

        {/* 课程列表 */}
        {isLoading ? (
          <LoadingSkeleton type="course-card" count={8} />
        ) : courses.length === 0 ? (
          <EmptyState
            icon={<SearchX className="h-12 w-12" />}
            title="没有找到相关课程"
            description="试试调整筛选条件或搜索其他关键词"
            actionLabel="重置筛选"
            onAction={resetFilter}
          />
        ) : (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
            >
              {courses.map((course) => (
                <CourseCard key={course.id} course={course} />
              ))}
            </motion.div>

            {/* 分页信息 */}
            <div className="flex items-center justify-center gap-2 text-sm text-brand-gray">
              <span>
                第 {currentPage} / {totalPages} 页，共 {courses.length} 门课程
              </span>
            </div>
          </>
        )}
      </div>
    </MainLayout>
  );
}
