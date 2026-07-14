/**
 * 全局根布局组件
 *
 * 功能说明：
 * - 配置全局字体、元数据、主题和错误边界
 * - 为所有页面提供 ThemeProvider、TooltipProvider 和 AuthInitializer 上下文
 * - 使用 suppressHydrationWarning 避免服务端/客户端主题不一致的警告
 */

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/lib/theme/ThemeProvider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthInitializer } from "@/components/auth-initializer";
import { ErrorBoundary } from "@/components/error-boundary";

/** Inter 字体配置，用于全局文本渲染 */
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

/** 全局页面元数据（SEO） */
export const metadata: Metadata = {
  title: "AI学堂 - 智能学习平台",
  description: "适合6-18岁青少年的AI驱动个性化学习平台",
  keywords: ["AI学习", "青少年教育", "个性化学习", "智能辅导"],
};

/**
 * 根布局组件
 * @param children - 子页面内容
 * @returns 包裹全局上下文后的页面结构
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans antialiased bg-background text-gray-900`}>
        <ErrorBoundary>
          <ThemeProvider>
            <TooltipProvider delayDuration={300}>
              <AuthInitializer />
              {children}
            </TooltipProvider>
          </ThemeProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
