/**
 * 统计卡片组件
 *
 * 功能说明：
 * - 展示标签、数值和图标，用于仪表盘数据展示
 * - 支持趋势指示（上升/下降百分比）
 * - 多种预设颜色主题（蓝、绿、橙、红、紫）
 * - 悬停时带轻微放大动画（framer-motion）
 */

"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { motion } from "framer-motion";

/** 统计卡片属性 */
interface StatCardProps {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: {
    value: number;
    isUp: boolean;
  };
  color?: "blue" | "green" | "orange" | "red" | "purple";
  className?: string;
}

/** 颜色主题映射 */
const COLOR_MAP = {
  blue: "bg-blue-50 text-brand-blue",
  green: "bg-green-50 text-brand-green",
  orange: "bg-amber-50 text-brand-orange",
  red: "bg-red-50 text-brand-red",
  purple: "bg-purple-50 text-purple-600",
};

/**
 * 统计卡片组件
 * @param label - 标签文字
 * @param value - 数值
 * @param icon - 图标组件
 * @param trend - 趋势数据（可选）
 * @param color - 颜色主题
 * @param className - 额外类名
 * @returns 统计卡片
 */
export function StatCard({
  label,
  value,
  icon,
  trend,
  color = "blue",
  className,
}: StatCardProps) {
  return (
    <motion.div whileHover={{ scale: 1.02 }} transition={{ duration: 0.2 }}>
      <Card className={cn("shadow-card", className)}>
        <CardContent className="flex items-center gap-4 p-5">
          {/* 图标 */}
          <div
            className={cn(
              "flex h-12 w-12 items-center justify-center rounded-xl",
              COLOR_MAP[color],
            )}
          >
            {icon}
          </div>

          {/* 数据 */}
          <div className="flex-1">
            <p className="text-sm text-brand-gray">{label}</p>
            <div className="mt-0.5 flex items-baseline gap-2">
              <span className="whitespace-nowrap text-2xl font-bold text-gray-900">{value}</span>
              {trend && (
                <span
                  className={cn(
                    "text-xs font-medium",
                    trend.isUp ? "text-brand-green" : "text-brand-red",
                  )}
                >
                  {trend.isUp ? "+" : ""}
                  {trend.value}%
                </span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
