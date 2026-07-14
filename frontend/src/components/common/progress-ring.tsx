/**
 * 环形进度条组件
 *
 * 功能说明：
 * - SVG 绘制的圆形进度指示器
 * - 支持自定义尺寸、线宽和颜色
 * - 中间可放置任意内容（百分比、图标等）
 * - 进度变化时带平滑过渡动画
 * - 常用于仪表盘、技能等级等场景
 */

"use client";

import React from "react";
import { cn } from "@/lib/utils";

/** 环形进度条属性 */
interface ProgressRingProps {
  progress: number; // 0-100
  size?: number;
  strokeWidth?: number;
  className?: string;
  children?: React.ReactNode;
  color?: string;
}

/**
 * 环形进度条组件
 * @param progress - 进度百分比（0-100）
 * @param size - 圆环尺寸（默认 80px）
 * @param strokeWidth - 线条宽度（默认 6px）
 * @param className - 额外类名
 * @param children - 圆环中心内容
 * @param color - 进度条颜色（默认 #2563EB）
 * @returns 环形进度条
 */
export function ProgressRing({
  progress,
  size = 80,
  strokeWidth = 6,
  className,
  children,
  color = "#2563EB",
}: ProgressRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (progress / 100) * circumference;

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)}>
      <svg width={size} height={size} className="-rotate-90">
        {/* 背景圆环 */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#E5E7EB"
          strokeWidth={strokeWidth}
        />
        {/* 进度圆环 */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-700 ease-out"
        />
      </svg>
      {/* 中间内容 */}
      {children && (
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {children}
        </div>
      )}
    </div>
  );
}
