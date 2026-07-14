/**
 * 全局加载状态管理 - Zustand Store
 *
 * 功能说明：
 * - 管理全局加载状态（如页面切换、数据请求时的全屏 loading）
 * - 支持按页面维度管理加载状态
 * - 用于需要统一控制 loading 显示/隐藏的场景
 */

import { create } from "zustand";

/** 加载状态接口 */
interface LoadingState {
  /** 全局加载状态 */
  globalLoading: boolean;
  /** 各页面加载状态 */
  pageLoading: Record<string, boolean>;
  /** 设置全局加载状态 */
  setGlobalLoading: (loading: boolean) => void;
  /** 设置指定页面的加载状态 */
  setPageLoading: (page: string, loading: boolean) => void;
}

export const useLoadingStore = create<LoadingState>((set) => ({
  globalLoading: false,
  pageLoading: {},
  setGlobalLoading: (loading) => set({ globalLoading: loading }),
  setPageLoading: (page, loading) =>
    set((state) => ({
      pageLoading: { ...state.pageLoading, [page]: loading },
    })),
}));
