/**
 * 侧边栏组件
 *
 * 功能说明：
 * - 展示 Logo、主导航链接、用户信息和折叠按钮
 * - 支持折叠/展开状态切换
 * - 当前页面高亮显示（带指示器动画）
 * - 已登录用户显示头像、昵称、等级和设置/退出按钮
 * - 未登录用户显示登录入口
 * - 使用 framer-motion 实现折叠/展开的过渡动画
 */

"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  Compass,
  BookOpen,
  NotebookPen,
  TrendingUp,
  Trophy,
  Medal,
  User,
  GraduationCap,
  ChevronLeft,
  ChevronRight,
  Settings,
  LogOut,
  Sparkles,
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { motion } from "framer-motion";

/** 导航项配置 */
const NAV_ITEMS = [
  { label: "首页", href: "/home", icon: Home },
  { label: "探索", href: "/explore", icon: Compass },
  { label: "学习", href: "/learning", icon: BookOpen },
  { label: "AI出题", href: "/ai-questions", icon: Sparkles },
  { label: "错题本", href: "/wrong-book", icon: NotebookPen },
  { label: "每日挑战", href: "/challenge", icon: Trophy },
  { label: "排行榜", href: "/leaderboard", icon: Medal },
  { label: "学习报告", href: "/report", icon: TrendingUp },
  { label: "我的", href: "/profile", icon: User },
];

/** 侧边栏属性 */
interface SidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

/**
 * 侧边栏组件
 * @param collapsed - 是否折叠
 * @param onToggle - 折叠/展开切换回调
 * @returns 侧边栏导航组件
 */
export function Sidebar({ collapsed = false, onToggle }: SidebarProps) {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  return (
    <aside
      className={cn(
        "sticky top-0 z-30 flex h-screen flex-col border-r border-sidebar-border bg-white transition-all duration-300",
        collapsed ? "w-[72px]" : "w-sidebar",
      )}
    >
      {/* Logo 区域 */}
      <div className="flex h-topbar items-center gap-3 border-b border-sidebar-border px-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-blue">
          <GraduationCap className="h-5 w-5 text-white" />
        </div>
        {!collapsed && (
          <motion.span
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            className="text-lg font-bold text-gray-900"
          >
            AI学堂
          </motion.span>
        )}
      </div>

      {/* 导航列表 */}
      <ScrollArea className="flex-1 py-4">
        <nav className="flex flex-col gap-1 px-3">
          {NAV_ITEMS.map((item) => {
            // 判断当前导航项是否激活（精确匹配或子路径匹配）
            const isActive =
              pathname === item.href || pathname.startsWith(item.href + "/");
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-blue-50 text-brand-blue"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                  collapsed && "justify-center px-0",
                )}
              >
                <Icon className={cn("h-5 w-5 shrink-0", isActive && "text-brand-blue")} />
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.05 }}
                  >
                    {item.label}
                  </motion.span>
                )}
                {isActive && !collapsed && (
                  <motion.div
                    layoutId="sidebar-indicator"
                    className="ml-auto h-1.5 w-1.5 rounded-full bg-brand-blue"
                  />
                )}
              </Link>
            );
          })}
        </nav>
      </ScrollArea>

      {/* 底部折叠/展开按钮 */}
      {collapsed ? (
        <div className="flex justify-center px-2 pb-2">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-gray-400 hover:text-gray-600"
            onClick={onToggle}
            title="展开侧栏"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      ) : (
        <div className="px-3 pb-2">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-center text-gray-400 hover:text-gray-600"
            onClick={onToggle}
          >
            <ChevronLeft className="h-4 w-4" />
            <span className="ml-1 text-xs">收起侧栏</span>
          </Button>
        </div>
      )}

      <Separator />

      {/* 底部用户信息 */}
      <div className={cn("flex items-center gap-3 p-4", collapsed && "justify-center px-4 py-3")}>
        {user ? (
          <>
            <Avatar className="h-9 w-9 shrink-0">
              <AvatarImage src={user?.avatar || "/avatars/default.svg"} alt={user?.nickname} />
              <AvatarFallback className="bg-brand-blue text-sm text-white">
                {user?.nickname?.charAt(0) || "U"}
              </AvatarFallback>
            </Avatar>
            {!collapsed && (
              <div className="flex-1 overflow-hidden">
                <p className="truncate text-sm font-medium text-gray-900">
                  {user?.nickname}
                </p>
                <p className="truncate text-xs text-brand-gray">
                  {`Lv.${user.level || 1}`}
                </p>
              </div>
            )}
            {!collapsed && (
              <div className="flex gap-1">
                <Link href="/profile">
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-gray-400">
                    <Settings className="h-4 w-4" />
                  </Button>
                </Link>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-gray-400"
                  onClick={logout}
                >
                  <LogOut className="h-4 w-4" />
                </Button>
              </div>
            )}
          </>
        ) : (
          <Link href="/login" className="flex flex-1 items-center gap-3">
            <Avatar className="h-9 w-9 shrink-0">
              <AvatarFallback className="bg-gray-200 text-sm text-gray-500">
                U
              </AvatarFallback>
            </Avatar>
            {!collapsed && (
              <div className="flex-1 overflow-hidden">
                <p className="truncate text-sm font-medium text-gray-900">
                  未登录
                </p>
                <p className="truncate text-xs text-brand-gray hover:text-brand-blue">
                  点击登录
                </p>
              </div>
            )}
          </Link>
        )}
      </div>
    </aside>
  );
}
