/**
 * 知识探索页面
 *
 * 功能说明：
 * - 课程列表展示，支持学科、难度、年龄组筛选和排序
 * - 搜索框防抖处理（500ms）
 * - 支持从 URL 查询参数同步关键词筛选
 * - 使用 Suspense 处理 useSearchParams 的客户端 hydration
 * - 空状态和加载骨架屏展示
 */

"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { useSearchParams } from "next/navigation";
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

import { Suspense } from "react";

/**
 * 探索页面内容主体组件
 * @returns 课程列表与筛选区域
 */
function ExplorePageContent() {
  const searchParams = useSearchParams();
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

  // 搜索框防抖：本地输入状态
  const [searchInput, setSearchInput] = useState(filter.keyword || "");
  const debounceTimer = useRef<NodeJS.Timeout>();

  // 初始化时同步搜索框值（URL 参数或筛选状态变更时）
  useEffect(() => {
    setSearchInput(filter.keyword || "");
  }, [filter.keyword]);

  /**
   * 处理关键词变更（防抖 500ms）
   * @param value - 输入的关键词
   */
  const handleKeywordChange = useCallback((value: string) => {
    setSearchInput(value);
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      setFilter({ keyword: value });
    }, 500);
  }, [setFilter]);

  // 组件卸载时清除定时器，避免内存泄漏
  useEffect(() => {
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, []);

  // 监听 URL 查询参数变化，同步筛选条件
  useEffect(() => {
    const keyword = searchParams.get("keyword");
    if (keyword) {
      setFilter({ keyword });
    } else {
      fetchCourses();
    }
  }, [searchParams, fetchCourses, setFilter]);

  // 各筛选条件变更处理器
  const handleSubjectChange = (value?: Subject) => setFilter({ subject: value });
  const handleDifficultyChange = (value?: DifficultyLevel) => setFilter({ difficulty: value });
  const handleAgeGroupChange = (value?: AgeGroup) => setFilter({ ageGroup: value });
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
          keyword={searchInput}
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

export default function ExplorePage() {
  return (
    <Suspense fallback={<MainLayout><LoadingSkeleton /></MainLayout>}>
      <ExplorePageContent />
    </Suspense>
  );
}
