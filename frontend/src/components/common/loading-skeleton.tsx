"use client";

import React from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface LoadingSkeletonProps {
  /** 骨架屏类型 */
  type?: "course-card" | "list" | "detail" | "dashboard" | "profile";
  /** 重复次数 */
  count?: number;
  className?: string;
}

/** 课程卡片骨架 */
function CourseCardSkeleton() {
  return (
    <div className="overflow-hidden rounded-card-md border border-gray-100 bg-white shadow-card">
      <Skeleton className="h-32 w-full" />
      <div className="p-4 space-y-3">
        <Skeleton className="h-5 w-3/4" />
        <div className="flex gap-3">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-16" />
        </div>
        <Skeleton className="h-1.5 w-full rounded-full" />
      </div>
    </div>
  );
}

/** 列表骨架 */
function ListSkeleton() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 rounded-lg border border-gray-100 bg-white p-4">
          <Skeleton className="h-12 w-12 rounded-lg" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-1/3" />
          </div>
          <Skeleton className="h-8 w-20" />
        </div>
      ))}
    </div>
  );
}

/** 详情页骨架 */
function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-48 w-full rounded-card-md" />
      <div className="grid grid-cols-3 gap-4">
        <Skeleton className="h-20 rounded-card-md" />
        <Skeleton className="h-20 rounded-card-md" />
        <Skeleton className="h-20 rounded-card-md" />
      </div>
      <div className="space-y-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <Skeleton className="h-10 w-10 rounded-full" />
            <Skeleton className="h-4 flex-1" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** 仪表盘骨架 */
function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      {/* 欢迎横幅 */}
      <Skeleton className="h-32 w-full rounded-card-md" />
      {/* 统计卡片 */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 rounded-card-md" />
        ))}
      </div>
      {/* 课程卡片 */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <CourseCardSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}

/** 个人中心骨架 */
function ProfileSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-6">
        <Skeleton className="h-20 w-20 rounded-full" />
        <div className="space-y-3">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-4 w-64" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-24 rounded-card-md" />
        ))}
      </div>
    </div>
  );
}

export function LoadingSkeleton({ type = "course-card", count = 1, className }: LoadingSkeletonProps) {
  const skeletons: Record<string, React.ReactNode> = {
    "course-card": (
      <div className={cn("grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4", className)}>
        {Array.from({ length: count }).map((_, i) => (
          <CourseCardSkeleton key={i} />
        ))}
      </div>
    ),
    list: <div className={className}>{Array.from({ length: count }).map((_, i) => <ListSkeleton key={i} />)}</div>,
    detail: <div className={className}><DetailSkeleton /></div>,
    dashboard: <div className={className}><DashboardSkeleton /></div>,
    profile: <div className={className}><ProfileSkeleton /></div>,
  };

  return <>{skeletons[type] || skeletons["course-card"]}</>;
}
