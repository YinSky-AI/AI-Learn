/* ============================================
   本地存储工具 - 未登录用户数据持久化
   ============================================ */

import type { ChatMessage } from "@/types";

const STORAGE_KEYS = {
  COURSE_PROGRESS: "ai-learn:course-progress",
  CHAT_HISTORY: "ai-learn:chat-history",
  LAST_USER: "ai-learn:last-user",
} as const;

/** 本地课程进度 */
export interface LocalCourseProgress {
  completedLessonIds: string[];
  lastAccessedAt: string;
}

/** 获取本地课程进度 */
export function getLocalCourseProgress(courseId: string): LocalCourseProgress | null {
  if (typeof window === "undefined") return null;
  try {
    const all = JSON.parse(localStorage.getItem(STORAGE_KEYS.COURSE_PROGRESS) || "{}") as Record<string, LocalCourseProgress>;
    return all[courseId] || null;
  } catch {
    return null;
  }
}

/** 保存本地课程进度 */
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

/** 获取所有本地课程进度 */
export function getAllLocalCourseProgress(): Record<string, LocalCourseProgress> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS.COURSE_PROGRESS) || "{}") as Record<string, LocalCourseProgress>;
  } catch {
    return {};
  }
}

/** 清空本地课程进度 */
export function clearLocalCourseProgress(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEYS.COURSE_PROGRESS);
}

/** 获取本地聊天记录 */
export function getLocalChatHistory(courseId: string): ChatMessage[] {
  if (typeof window === "undefined") return [];
  try {
    const all = JSON.parse(localStorage.getItem(STORAGE_KEYS.CHAT_HISTORY) || "{}") as Record<string, ChatMessage[]>;
    return all[courseId] || [];
  } catch {
    return [];
  }
}

/** 保存本地聊天记录 */
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

/** 清空本地聊天记录 */
export function clearLocalChatHistory(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEYS.CHAT_HISTORY);
}
