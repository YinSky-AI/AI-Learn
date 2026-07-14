/**
 * 错误状态组件
 *
 * 功能说明：
 * - 当数据加载失败时展示的错误界面
 * - 支持自定义错误标题、描述和重试按钮
 * - 提供重试操作回调，方便用户重新加载
 * - 使用红色主题视觉提示
 */

"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { AlertTriangle, RefreshCw } from "lucide-react";

/** 错误状态属性 */
interface ErrorStateProps {
  /** 错误标题 */
  title?: string;
  /** 错误描述 */
  message?: string;
  /** 重试回调 */
  onRetry?: () => void;
  /** 重试按钮文字 */
  retryLabel?: string;
  className?: string;
}

/**
 * 错误状态组件
 * @param title - 错误标题
 * @param message - 错误描述
 * @param onRetry - 重试回调函数
 * @param retryLabel - 重试按钮文字
 * @param className - 额外类名
 * @returns 错误状态展示界面
 */
export function ErrorState({
  title = "出了点问题",
  message = "很抱歉，加载内容时遇到了问题。请稍后再试。",
  onRetry,
  retryLabel = "重试",
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-card-md border border-dashed border-red-200 bg-red-50/50 py-16 px-8",
        className,
      )}
    >
      {/* 错误图标 */}
      <div className="mb-4 rounded-full bg-red-100 p-3">
        <AlertTriangle className="h-6 w-6 text-brand-red" />
      </div>

      {/* 标题 */}
      <h3 className="text-base font-semibold text-gray-700">{title}</h3>

      {/* 描述 */}
      <p className="mt-1 max-w-sm text-center text-sm text-brand-gray">{message}</p>

      {/* 重试按钮 */}
      {onRetry && (
        <Button variant="outline" className="mt-6" onClick={onRetry}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {retryLabel}
        </Button>
      )}
    </div>
  );
}
