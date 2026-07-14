/**
 * 课程筛选栏组件
 *
 * 功能说明：
 * - 提供搜索框（可按回车触发搜索）
 * - 学科、难度、年龄组下拉筛选
 * - 排序方式选择（热门、最新、评分、进度）
 * - 重置筛选按钮（仅在存在筛选条件时显示）
 * - 支持隐藏搜索框（showSearch=false）
 */

"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import type { Subject, DifficultyLevel, AgeGroup } from "@/types";
import { SUBJECT_LIST, DIFFICULTY_LIST, AGE_GROUP_LIST } from "@/lib/content";
import { Search, SlidersHorizontal, X } from "lucide-react";

/** 筛选栏属性 */
interface FilterBarProps {
  subject?: Subject;
  difficulty?: DifficultyLevel;
  ageGroup?: AgeGroup;
  keyword?: string;
  sortBy?: string;
  onSubjectChange?: (value: Subject | undefined) => void;
  onDifficultyChange?: (value: DifficultyLevel | undefined) => void;
  onAgeGroupChange?: (value: AgeGroup | undefined) => void;
  onKeywordChange?: (value: string) => void;
  onSortChange?: (value: string) => void;
  onReset?: () => void;
  className?: string;
  showSearch?: boolean;
}

/**
 * 课程筛选栏组件
 * @param props - 筛选条件和回调函数
 * @returns 筛选栏
 */
export function FilterBar({
  subject,
  difficulty,
  ageGroup,
  keyword,
  sortBy,
  onSubjectChange,
  onDifficultyChange,
  onAgeGroupChange,
  onKeywordChange,
  onSortChange,
  onReset,
  className,
  showSearch = true,
}: FilterBarProps) {
  // 是否存在任何筛选条件
  const hasFilters = subject || difficulty || ageGroup || keyword;

  return (
    <div className={cn("flex flex-col gap-3 sm:flex-row sm:items-center", className)}>
      {/* 搜索框 */}
      {showSearch && (
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-gray" />
          <Input
            placeholder="搜索课程..."
            value={keyword || ""}
            onChange={(e) => onKeywordChange?.(e.target.value)}
            className="pl-9"
          />
        </div>
      )}

      {/* 学科筛选 */}
      <Select value={subject || "all"} onValueChange={(v) => onSubjectChange?.(v === "all" ? undefined : v as Subject)}>
        <SelectTrigger className="w-[120px]">
          <SlidersHorizontal className="mr-2 h-4 w-4 text-brand-gray" />
          <SelectValue placeholder="学科" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部学科</SelectItem>
          {SUBJECT_LIST.map((s) => (
            <SelectItem key={s.key} value={s.key}>
              {s.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* 难度筛选 */}
      <Select
        value={difficulty || "all"}
        onValueChange={(v) => onDifficultyChange?.(v === "all" ? undefined : v as DifficultyLevel)}
      >
        <SelectTrigger className="w-[100px]">
          <SelectValue placeholder="难度" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部难度</SelectItem>
          {DIFFICULTY_LIST.map((d) => (
            <SelectItem key={d.key} value={d.key}>
              {d.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* 年龄组筛选 */}
      <Select
        value={ageGroup || "all"}
        onValueChange={(v) => onAgeGroupChange?.(v === "all" ? undefined : v as AgeGroup)}
      >
        <SelectTrigger className="w-[100px]">
          <SelectValue placeholder="年龄" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部年龄</SelectItem>
          {AGE_GROUP_LIST.map((a) => (
            <SelectItem key={a.key} value={a.key}>
              {a.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* 排序 */}
      <Select value={sortBy || "popular"} onValueChange={onSortChange}>
        <SelectTrigger className="w-[110px]">
          <SelectValue placeholder="排序" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="popular">最热门</SelectItem>
          <SelectItem value="newest">最新</SelectItem>
          <SelectItem value="rating">评分最高</SelectItem>
          <SelectItem value="progress">学习进度</SelectItem>
        </SelectContent>
      </Select>

      {/* 重置按钮 */}
      {hasFilters && onReset && (
        <Button variant="ghost" size="sm" onClick={onReset} className="text-brand-gray">
          <X className="mr-1 h-4 w-4" />
          重置
        </Button>
      )}
    </div>
  );
}
