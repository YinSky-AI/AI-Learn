"use client";

import React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface EmptyStateProps {
  /** 图标 */
  icon?: React.ReactNode;
  /** 标题 */
  title: string;
  /** 描述 */
  description?: string;
  /** 操作按钮文字 */
  actionLabel?: string;
  /** 操作回调 */
  onAction?: () => void;
  /** 跳转链接（与 onAction 二选一） */
  href?: string;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  href,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-card-md border border-dashed border-gray-200 bg-white py-16 px-8",
        className,
      )}
    >
      {/* 图标 */}
      {icon && (
        <div className="mb-4 text-gray-300">{icon}</div>
      )}

      {/* 标题 */}
      <h3 className="text-base font-semibold text-gray-700">{title}</h3>

      {/* 描述 */}
      {description && (
        <p className="mt-1 max-w-sm text-center text-sm text-brand-gray">{description}</p>
      )}

      {/* 操作按钮 */}
      {actionLabel && (href ? (
        <Link href={href}>
          <Button className="mt-6">{actionLabel}</Button>
        </Link>
      ) : onAction ? (
        <Button className="mt-6" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null)}
    </div>
  );
}
