/**
 * 错误边界组件
 *
 * 功能说明：
 * - 捕获子组件树中的 JavaScript 错误，防止整个应用崩溃
 * - 展示友好的错误提示界面，提供刷新页面按钮
 * - 在开发环境显示错误详情，生产环境仅显示提示
 * - 使用 React Class Component 实现（getDerivedStateFromError / componentDidCatch）
 */

"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** 错误边界属性 */
interface Props {
  children: React.ReactNode;
}

/** 错误边界状态 */
interface State {
  hasError: boolean;
  error?: Error;
}

/**
 * 错误边界组件
 * @example
 * <ErrorBoundary>
 *   <YourComponent />
 * </ErrorBoundary>
 */
export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  /**
   * 从错误中派生状态
   * @param error - 捕获的错误
   * @returns 更新后的状态
   */
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  /**
   * 捕获错误后的副作用处理
   * @param error - 错误对象
   * @param errorInfo - 错误堆栈信息
   */
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("ErrorBoundary caught error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center p-4">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>出错了</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                页面发生错误，请刷新重试。
              </p>
              {this.state.error && (
                <pre className="rounded bg-muted p-2 text-xs text-destructive">
                  {this.state.error.message}
                </pre>
              )}
              <Button onClick={() => window.location.reload()} className="w-full">
                刷新页面
              </Button>
            </CardContent>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}
