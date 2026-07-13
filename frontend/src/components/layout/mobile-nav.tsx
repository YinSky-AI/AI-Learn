"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Compass, BookOpen, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

/** 底部导航项 */
const MOBILE_NAV_ITEMS = [
  { label: "首页", href: "/home", icon: Home },
  { label: "探索", href: "/explore", icon: Compass },
  { label: "学习", href: "/learning", icon: BookOpen },
  { label: "我的", href: "/profile", icon: User },
];

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-30 flex h-16 items-center justify-around border-t border-gray-100 bg-white px-2 pb-[env(safe-area-inset-bottom)]">
      {MOBILE_NAV_ITEMS.map((item) => {
        const isActive =
          pathname === item.href || pathname.startsWith(item.href + "/");
        const Icon = item.icon;

        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex flex-col items-center gap-0.5 px-3 py-1.5 text-xs transition-colors",
              isActive ? "text-brand-blue" : "text-gray-400",
            )}
          >
            <div className="relative">
              <Icon className={cn("h-5 w-5", isActive && "text-brand-blue")} />
              {isActive && (
                <motion.div
                  layoutId="mobile-nav-indicator"
                  className="absolute -bottom-1 left-1/2 h-0.5 w-4 -translate-x-1/2 rounded-full bg-brand-blue"
                />
              )}
            </div>
            <span className={cn(isActive && "font-medium")}>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
