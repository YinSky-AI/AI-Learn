"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { motion } from "framer-motion";

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

const COLOR_MAP = {
  blue: "bg-blue-50 text-brand-blue",
  green: "bg-green-50 text-brand-green",
  orange: "bg-amber-50 text-brand-orange",
  red: "bg-red-50 text-brand-red",
  purple: "bg-purple-50 text-purple-600",
};

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
              <span className="text-2xl font-bold text-gray-900">{value}</span>
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
