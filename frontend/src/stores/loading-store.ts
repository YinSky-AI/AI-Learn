import { create } from "zustand";

interface LoadingState {
  globalLoading: boolean;
  pageLoading: Record<string, boolean>;
  setGlobalLoading: (loading: boolean) => void;
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
