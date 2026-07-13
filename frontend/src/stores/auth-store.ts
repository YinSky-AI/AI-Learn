/* ============================================
   认证状态管理 - Zustand Store
   ============================================ */

import { create } from "zustand";
import type { User, UserProfile, AgeGroup } from "@/types";
import type { LoginRequest, LoginResponse, UserMeResponse, UserStats } from "@/types/api";
import { TokenManager, apiClient } from "@/lib/api-client";

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
  /** 获取当前用户资料 */
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

  register: async (data: Record<string, unknown>) => {
    set({ isLoading: true, error: null });
    try {
      await apiClient.post("/v1/auth/register", data);
      // 注册成功后自动登录（使用 username 作为 email）
      await get().login({
        email: (data.email || data.username) as string,
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
    // 刷新页面以清除所有用户相关的内存状态
    if (typeof window !== "undefined") {
      window.location.href = "/home";
    }
  },

  fetchProfile: async () => {
    try {
      const data = await apiClient.get<UserMeResponse>("/v1/users/me");
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
      // 获取资料失败不强制登出，可能是网络问题
      console.warn("获取用户资料失败:", error);
    }
  },

  fetchUserStats: async () => {
    try {
      const statsData = await apiClient.get<UserStats>("/v1/users/me/stats");
      set({ stats: statsData });
    } catch (error) {
      console.warn("获取用户统计失败:", error);
    }
  },

  clearError: () => set({ error: null }),

  updateUser: (partialUser: Partial<User>) => {
    const currentUser = get().user;
    if (currentUser) {
      set({ user: { ...currentUser, ...partialUser } });
    }
  },
}));
