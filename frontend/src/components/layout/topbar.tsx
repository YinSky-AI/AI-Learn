"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search, Bell, MessageSquare, Menu, LogOut, User, ChevronDown } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useAuthStore } from "@/stores/auth-store";
import { cn } from "@/lib/utils";

interface TopbarProps {
  onMenuClick?: () => void;
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const router = useRouter();
  const [searchValue, setSearchValue] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭下拉菜单
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    if (dropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [dropdownOpen]);

  const handleLogout = () => {
    setDropdownOpen(false);
    logout();
  };

  return (
    <header className="sticky top-0 z-20 flex h-topbar items-center justify-between border-b border-gray-100 bg-white/80 px-6 backdrop-blur-sm">
      {/* 左侧：菜单按钮（移动端）+ 搜索框 */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={onMenuClick}
        >
          <Menu className="h-5 w-5" />
        </Button>

        <div className="relative hidden sm:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-gray" />
          <Input
            placeholder="搜索课程、知识点..."
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && searchValue.trim()) {
                router.push(`/explore?keyword=${encodeURIComponent(searchValue.trim())}`);
              }
            }}
            className="w-64 pl-9 lg:w-80"
          />
        </div>
      </div>

      {/* 右侧：通知 + 消息 + 头像 */}
      <div className="flex items-center gap-2">
        {/* 搜索按钮（移动端） */}
        <Button variant="ghost" size="icon" className="sm:hidden">
          <Search className="h-5 w-5 text-gray-500" />
        </Button>

        {/* 通知 */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="h-5 w-5 text-gray-500" />
              <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-brand-red" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>通知</TooltipContent>
        </Tooltip>

        {/* 消息 */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="relative">
              <MessageSquare className="h-5 w-5 text-gray-500" />
              <Badge className="absolute -right-0.5 -top-0.5 h-4 w-4 items-center justify-center rounded-full p-0 text-[10px]">
                3
              </Badge>
            </Button>
          </TooltipTrigger>
          <TooltipContent>消息</TooltipContent>
        </Tooltip>

        {/* 头像（已登录：下拉菜单；未登录：跳转登录） */}
        {user ? (
          <div className="relative ml-2" ref={dropdownRef}>
            <button
              className="flex items-center gap-2 rounded-lg px-1.5 py-1 transition-colors hover:bg-gray-100"
              onClick={() => setDropdownOpen(!dropdownOpen)}
            >
              <Avatar className="h-8 w-8">
                <AvatarImage src={user?.avatar || "/avatars/default.svg"} />
                <AvatarFallback className="bg-brand-blue text-xs text-white">
                  {user?.nickname?.charAt(0) || "U"}
                </AvatarFallback>
              </Avatar>
              <span className="hidden text-sm font-medium text-gray-700 lg:block">
                {user?.nickname}
              </span>
              <ChevronDown className={cn(
                "hidden h-3.5 w-3.5 text-gray-400 transition-transform lg:block",
                dropdownOpen && "rotate-180",
              )} />
            </button>

            {/* 下拉菜单 */}
            {dropdownOpen && (
              <div className="absolute right-0 top-full mt-1 w-40 rounded-lg border border-gray-100 bg-white py-1 shadow-lg">
                <Link
                  href="/profile"
                  className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  onClick={() => setDropdownOpen(false)}
                >
                  <User className="h-4 w-4 text-gray-400" />
                  个人中心
                </Link>
                <button
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                  onClick={handleLogout}
                >
                  <LogOut className="h-4 w-4" />
                  退出登录
                </button>
              </div>
            )}
          </div>
        ) : (
          <Link href="/login" className="ml-2 flex items-center gap-2">
            <Avatar className="h-8 w-8">
              <AvatarFallback className="bg-gray-200 text-xs text-gray-500">
                U
              </AvatarFallback>
            </Avatar>
            <span className="hidden text-sm font-medium text-gray-700 lg:block hover:text-brand-blue">
              未登录
            </span>
          </Link>
        )}
      </div>
    </header>
  );
}