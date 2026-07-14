/**
 * 通用工具函数库
 *
 * 功能说明：
 * - cn: 合并 Tailwind CSS 类名（clsx + tailwind-merge）
 * - formatDuration: 分钟转可读时长
 * - formatDate / formatRelativeTime: 日期格式化
 * - truncateText: 文本截断
 * - generateId: 生成随机 ID
 * - formatNumber: 千分位数字格式化
 * - calcPercentage: 百分比计算
 * - debounce: 防抖函数
 * - getDifficultyColor / getSubjectColorClass / getSubjectBgClass: 颜色映射
 * - isClient / getLocalStorage / setLocalStorage: 客户端安全工具
 */

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * 合并 Tailwind CSS 类名
 * @param inputs - 任意类名值
 * @returns 合并后的类名字符串
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * 格式化时长
 * @param minutes - 分钟数
 * @returns 可读时长（如 "1小时30分钟" 或 "45分钟"）
 */
export function formatDuration(minutes: number): string {
  if (minutes < 60) {
    return `${minutes}分钟`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  if (remainingMinutes === 0) {
    return `${hours}小时`;
  }
  return `${hours}小时${remainingMinutes}分钟`;
}

/**
 * 格式化日期
 * @param dateStr - ISO 日期字符串
 * @param locale - 区域设置（默认 zh-CN）
 * @returns 本地日期字符串
 */
export function formatDate(dateStr: string, locale = "zh-CN"): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString(locale, {
    year: "numeric",
  });
}

/**
 * 格式化相对时间
 * @param dateStr - ISO 日期字符串
 * @returns 相对时间（如 "刚刚"、"5分钟前"、"3天前"）
 */
export function formatRelativeTime(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMinutes < 1) return "刚刚";
  if (diffMinutes < 60) return `${diffMinutes}分钟前`;
  if (diffHours < 24) return `${diffHours}小时前`;
  if (diffDays < 7) return `${diffDays}天前`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}周前`;
  return formatDate(dateStr);
}

/**
 * 截断文本
 * @param text - 原始文本
 * @param maxLength - 最大长度
 * @returns 截断后的文本（带省略号）
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

/**
 * 生成随机 ID
 * @returns 随机字符串 ID
 */
export function generateId(): string {
  return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
}

/**
 * 数值格式化（加千分位）
 * @param num - 数字
 * @returns 格式化后的字符串（如 "1,234"）
 */
export function formatNumber(num: number): string {
  return new Intl.NumberFormat("zh-CN").format(num);
}

/**
 * 计算百分比
 * @param value - 当前值
 * @param total - 总值
 * @returns 百分比整数（0-100）
 */
export function calcPercentage(value: number, total: number): number {
  if (total === 0) return 0;
  return Math.round((value / total) * 100);
}

/**
 * 防抖函数
 * @param fn - 要防抖的函数
 * @param delay - 延迟时间（毫秒）
 * @returns 防抖后的函数
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  fn: T,
  delay: number,
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

/**
 * 获取难度对应的颜色类名
 * @param difficulty - 难度代码（beginner / intermediate / advanced）
 * @returns Tailwind Badge 颜色类名
 */
export function getDifficultyColor(difficulty: string): string {
  switch (difficulty) {
    case "beginner":
      return "text-green-600 bg-green-50";
    case "intermediate":
      return "text-amber-600 bg-amber-50";
    case "advanced":
      return "text-red-600 bg-red-50";
    default:
      return "text-gray-600 bg-gray-50";
  }
}

/**
 * 获取学科对应的颜色类名
 * @param subject - 学科代码
 * @returns Tailwind 文字色和背景色类名
 */
export function getSubjectColorClass(subject: string): string {
  const colorMap: Record<string, string> = {
    math: "bg-subject-math-light text-subject-math",
    science: "bg-subject-science-light text-subject-science",
    chinese: "bg-subject-chinese-light text-subject-chinese",
    english: "bg-subject-english-light text-subject-english",
    programming: "bg-subject-programming-light text-subject-programming",
    art: "bg-subject-art-light text-subject-art",
    history: "bg-subject-history-light text-subject-history",
  };
  return colorMap[subject] || "bg-gray-100 text-gray-600";
}

/**
 * 获取学科色块背景类名
 * @param subject - 学科代码
 * @returns Tailwind 背景色类名
 */
export function getSubjectBgClass(subject: string): string {
  const bgMap: Record<string, string> = {
    math: "bg-subject-math-light",
    science: "bg-subject-science-light",
    chinese: "bg-subject-chinese-light",
    english: "bg-subject-english-light",
    programming: "bg-subject-programming-light",
    art: "bg-subject-art-light",
    history: "bg-subject-history-light",
  };
  return bgMap[subject] || "bg-gray-100";
}

/**
 * 判断是否在客户端（浏览器环境）
 * @returns 是否在浏览器环境
 */
export function isClient(): boolean {
  return typeof window !== "undefined";
}

/**
 * localStorage 安全读取
 * @param key - 存储键
 * @param fallback - 默认值
 * @returns 解析后的值或默认值
 */
export function getLocalStorage<T>(key: string, fallback: T): T {
  if (!isClient()) return fallback;
  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : fallback;
  } catch {
    return fallback;
  }
}

/**
 * localStorage 安全写入
 * @param key - 存储键
 * @param value - 要存储的值
 */
export function setLocalStorage<T>(key: string, value: T): void {
  if (!isClient()) return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    console.warn(`Failed to set localStorage key: ${key}`);
  }
}
