/**
 * 本地存储工具 - 未登录用户数据持久化
 *
 * 功能说明：
 * - 为未登录用户提供课程进度和聊天记录的本地持久化
 * - 使用 localStorage 存储，支持 SSR 安全（判断 window 是否存在）
 * - 课程进度按 courseId 分组存储，避免数据冲突
 * - 所有操作均有 try-catch 保护，防止存储异常导致应用崩溃
 */

import type { ChatMessage } from "@/types";

/** localStorage 存储键名 */
const STORAGE_KEYS = {
  COURSE_PROGRESS: "ai-learn:course-progress",
  CHAT_HISTORY: "ai-learn:chat-history",
  LAST_USER: "ai-learn:last-user",
} as const;

/** 本地课程进度数据结构 */
export interface LocalCourseProgress {
  completedLessonIds: string[];
  lastAccessedAt: string;
}

/**
 * 获取本地课程进度
 * @param courseId - 课程 ID
 * @returns 课程进度数据或 null
 */
export function getLocalCourseProgress(courseId: string): LocalCourseProgress | null {
  if (typeof window === "undefined") return null;
  try {
    const all = JSON.parse(localStorage.getItem(STORAGE_KEYS.COURSE_PROGRESS) || "{}") as Record<string, LocalCourseProgress>;
    return all[courseId] || null;
  } catch {
    return null;
  }
}

/**
 * 保存本地课程进度
 * @param courseId - 课程 ID
 * @param lessonId - 已完成的课时 ID
 */
export function saveLocalCourseProgress(courseId: string, lessonId: string): void {
  if (typeof window === "undefined") return;
  try {
    const all = JSON.parse(localStorage.getItem(STORAGE_KEYS.COURSE_PROGRESS) || "{}") as Record<string, LocalCourseProgress>;
    const existing = all[courseId] || { completedLessonIds: [], lastAccessedAt: new Date().toISOString() };
    if (!existing.completedLessonIds.includes(lessonId)) {
      existing.completedLessonIds.push(lessonId);
    }
    existing.lastAccessedAt = new Date().toISOString();
    all[courseId] = existing;
    localStorage.setItem(STORAGE_KEYS.COURSE_PROGRESS, JSON.stringify(all));
  } catch (e) {
    console.error("保存本地课程进度失败:", e);
  }
}

/**
 * 获取所有本地课程进度
 * @returns 以 courseId 为键的课程进度映射
 */
export function getAllLocalCourseProgress(): Record<string, LocalCourseProgress> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS.COURSE_PROGRESS) || "{}") as Record<string, LocalCourseProgress>;
  } catch {
    return {};
  }
}

/**
 * 清空本地课程进度
 */
export function clearLocalCourseProgress(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEYS.COURSE_PROGRESS);
}

/**
 * 获取本地聊天记录
 * @param courseId - 课程 ID
 * @returns 聊天消息数组
 */
export function getLocalChatHistory(courseId: string): ChatMessage[] {
  if (typeof window === "undefined") return [];
  try {
    const all = JSON.parse(localStorage.getItem(STORAGE_KEYS.CHAT_HISTORY) || "{}") as Record<string, ChatMessage[]>;
    return all[courseId] || [];
  } catch {
    return [];
  }
}

/**
 * 保存本地聊天记录
 * @param courseId - 课程 ID
 * @param messages - 聊天消息数组
 */
export function saveLocalChatHistory(courseId: string, messages: ChatMessage[]): void {
  if (typeof window === "undefined") return;
  try {
    const all = JSON.parse(localStorage.getItem(STORAGE_KEYS.CHAT_HISTORY) || "{}") as Record<string, ChatMessage[]>;
    all[courseId] = messages;
    localStorage.setItem(STORAGE_KEYS.CHAT_HISTORY, JSON.stringify(all));
  } catch (e) {
    console.error("保存本地聊天记录失败:", e);
  }
}

/**
 * 清空本地聊天记录
 */
export function clearLocalChatHistory(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEYS.CHAT_HISTORY);
}
