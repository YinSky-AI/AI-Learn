/**
 * 认证状态管理 - Zustand Store
 *
 * 功能说明：
 * - 管理用户登录状态、用户信息、学习统计
 * - 提供登录、注册、登出、获取用户资料等功能
 * - 登出时清空 Token 和本地存储的学习数据，并强制刷新页面
 * - fetchProfile 失败时抛出异常，供 AuthInitializer 判断 Token 是否有效
 */

import { create } from "zustand";
import type { User, UserProfile, AgeGroup } from "@/types";
import type { LoginRequest, LoginResponse, UserMeResponse, UserStats } from "@/types/api";
import { TokenManager, apiClient } from "@/lib/api-client";

/** 认证状态接口 */
interface AuthState {
  /** 用户信息 */
  user: User | null;
  /** 完整用户资料 */
  profile: UserProfile | null;
  /** 是否已认证 */
  isAuthenticated: boolean;
  /** 是否正在加载 */
  isLoading: boolean;
  /** 错误信息 */
  error: string | null;
  /** 用户学习统计 */
  stats: UserStats | null;

  /** 登录 */
  login: (credentials: LoginRequest) => Promise<void>;
  /** 注册 */
  register: (data: Record<string, unknown>) => Promise<void>;
  /** 登出 */
  logout: () => void;
  /** 获取当前用户资料（失败时抛出异常） */
  fetchProfile: () => Promise<void>;
  /** 获取用户学习统计 */
  fetchUserStats: () => Promise<void>;
  /** 清除错误 */
  clearError: () => void;
  /** 更新用户信息（本地） */
  updateUser: (user: Partial<User>) => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  profile: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,
  stats: null,

  /**
   * 用户登录
   * @param credentials - 登录凭据（用户名/密码）
   */
  login: async (credentials: LoginRequest) => {
    set({ isLoading: true, error: null });
    try {
      const response: LoginResponse = await apiClient.post("/v1/auth/login", credentials);
      TokenManager.setTokens(response.access_token, response.refresh_token);
      set({
        isAuthenticated: true,
        isLoading: false,
      });
      // 登录成功后获取完整资料和学习统计
      await get().fetchProfile();
      await get().fetchUserStats();
    } catch (error) {
      const message =
        error && typeof error === "object" && "message" in error
          ? (error as { message: string }).message
          : "登录失败，请检查用户名和密码";
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  /**
   * 用户注册（注册成功后自动登录）
   * @param data - 注册表单数据
   */
  register: async (data: Record<string, unknown>) => {
    set({ isLoading: true, error: null });
    try {
      await apiClient.post("/v1/auth/register", data);
      // 注册成功后自动登录（使用 username 作为 email）
      await get().login({
        username: (data.email || data.username) as string,
        password: data.password as string,
      });
    } catch (error) {
      // 如果已经是登录失败的错误，保留原错误信息
      const currentError = get().error;
      if (!currentError) {
        const message =
          error && typeof error === "object" && "message" in error
            ? (error as { message: string }).message
            : "注册失败，请稍后重试";
        set({ error: message, isLoading: false });
      } else {
        set({ isLoading: false });
      }
      throw error;
    }
  },

  /**
   * 用户登出
   * 清空 Token、localStorage 数据，并重定向到首页
   */
  logout: () => {
    TokenManager.clearTokens();
    // 清空用户相关的 localStorage 数据
    if (typeof window !== "undefined") {
      localStorage.removeItem("ai-learn:course-progress");
      localStorage.removeItem("ai-learn:chat-history");
    }
    set({
      user: null,
      profile: null,
      isAuthenticated: false,
      error: null,
      stats: null,
    });
    // 清空学习 store 的内存状态（防止退出后仍显示上次的学习进度）
    if (typeof window !== "undefined") {
      // 使用 hard reload 确保所有内存状态被清除
      window.location.href = "/home?t=" + Date.now();
    }
  },

  /**
   * 获取当前用户资料
   * 失败时抛出异常，供 AuthInitializer 判断 Token 是否有效
   */
  fetchProfile: async () => {
    try {
      const data = await apiClient.get<UserMeResponse>("/v1/users/me");
      // 将后端 UserMeResponse 映射为前端 User 类型
      const userData: User = {
        id: data.id,
        username: data.email,
        nickname: data.nickname,
        email: data.email,
        avatar: data.avatar_url || "",
        age: 0,
        ageGroup: data.age_group as AgeGroup,
        gender: "other",
        role: "student",
        bio: "",
        interests: [],
        level: 1,
        points: data.total_score,
        streakDays: data.streak_days,
        createdAt: data.created_at,
        updatedAt: data.updated_at,
      };
      set({
        user: userData,
        isAuthenticated: true,
      });
    } catch (error) {
      // 获取资料失败时抛出异常，让调用方决定如何处理
      // AuthInitializer 会据此判断是否清除无效 token
      console.warn("获取用户资料失败:", error);
      throw error;
    }
  },

  /**
   * 获取用户学习统计
   */
  fetchUserStats: async () => {
    try {
      const statsData = await apiClient.get<UserStats>("/v1/users/me/stats");
      set({ stats: statsData });
    } catch (error) {
      console.warn("获取用户统计失败:", error);
    }
  },

  /** 清除错误信息 */
  clearError: () => set({ error: null }),

  /**
   * 更新本地用户信息
   * @param partialUser - 部分用户字段
   */
  updateUser: (partialUser: Partial<User>) => {
    const currentUser = get().user;
    if (currentUser) {
      set({ user: { ...currentUser, ...partialUser } });
    }
  },
}));
