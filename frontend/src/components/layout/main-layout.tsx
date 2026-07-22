/**
 * 主布局组件
 *
 * 功能说明：
 * - 组合侧边栏、顶部栏、主内容区和移动端底部导航
 * - 支持侧边栏折叠/展开（桌面端）
 * - 移动端使用 Sheet 抽屉展示侧边栏
 * - 自适应响应式布局
 */

"use client";

import React, { useState } from "react";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { MobileNav } from "./mobile-nav";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { FloatingAIButton } from "@/components/ai/floating-ai-button";
import { cn } from "@/lib/utils";

/** 主布局属性 */
interface MainLayoutProps {
  children: React.ReactNode;
}

/**
 * 主布局组件
 * @param children - 页面主内容
 * @returns 带侧边栏和顶部栏的布局结构
 */
export function MainLayout({ children }: MainLayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-background">
      {/* 桌面端侧边栏 - sticky 定位，占据文档流空间，不遮挡内容 */}
      <div
        className={cn(
          "hidden lg:flex lg:flex-col lg:shrink-0 transition-all duration-300",
          !sidebarCollapsed ? "w-sidebar" : "w-[72px]"
        )}
      >
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        />
      </div>

      {/* 移动端侧边栏（Sheet 抽屉，不遮挡内容） */}
      <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
        <SheetContent side="left" className="w-sidebar p-0">
          <Sidebar collapsed={false} onToggle={() => setMobileNavOpen(false)} />
        </SheetContent>
      </Sheet>

      {/* 主内容区域 - flex-1 自动填充剩余空间 */}
      <div className="flex min-h-screen flex-1 flex-col overflow-hidden">
        <Topbar onMenuClick={() => setMobileNavOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 pb-24 sm:p-6 sm:pb-24 lg:pb-6">{children}</main>
      </div>

      {/* 移动端底部导航 */}
      <div className="lg:hidden">
        <MobileNav />
      </div>

      <FloatingAIButton />
    </div>
  );
}
