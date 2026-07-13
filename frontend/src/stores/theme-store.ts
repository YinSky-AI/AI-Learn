/* ============================================
   主题状态管理 - Zustand Store
   ============================================ */

import { create } from "zustand";
import type { AgeGroup } from "@/types";
import type { AgeTheme } from "@/lib/theme/types";
import { getThemeByAgeGroup } from "@/lib/theme/themes";
import { getLocalStorage, setLocalStorage } from "@/lib/utils";

interface ThemeState {
  /** 当前年龄组 */
  ageGroup: AgeGroup;
  /** 当前主题配置 */
  theme: AgeTheme;
  /** 是否初始化完成 */
  initialized: boolean;

  /** 设置年龄组主题 */
  setAgeGroup: (ageGroup: AgeGroup) => void;
  /** 初始化主题 */
  initTheme: () => void;
}

export const useThemeStore = create<ThemeState>((set) => ({
  ageGroup: "10-12",
  theme: getThemeByAgeGroup("10-12"),
  initialized: false,

  setAgeGroup: (ageGroup: AgeGroup) => {
    setLocalStorage("alp_age_group", ageGroup);
    set({
      ageGroup,
      theme: getThemeByAgeGroup(ageGroup),
    });
  },

  initTheme: () => {
    const savedAgeGroup = getLocalStorage<AgeGroup>("alp_age_group", "10-12");
    set({
      ageGroup: savedAgeGroup,
      theme: getThemeByAgeGroup(savedAgeGroup),
      initialized: true,
    });
  },
}));
