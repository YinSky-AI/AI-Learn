/**
 * 主题状态管理 - Zustand Store
 *
 * 功能说明：
 * - 根据年龄组管理不同的主题配置（颜色、字体、间距等）
 * - 主题配置持久化到 localStorage
 * - 初始化时从 localStorage 恢复上次选择的年龄组
 * - 与 lib/theme 中的主题系统配合使用
 */

import { create } from "zustand";
import type { AgeGroup } from "@/types";
import type { AgeTheme } from "@/lib/theme/types";
import { getThemeByAgeGroup } from "@/lib/theme/themes";
import { getLocalStorage, setLocalStorage } from "@/lib/utils";

/** 主题状态接口 */
interface ThemeState {
  /** 当前年龄组 */
  ageGroup: AgeGroup;
  /** 当前主题配置 */
  theme: AgeTheme;
  /** 是否初始化完成 */
  initialized: boolean;

  /** 设置年龄组主题 */
  setAgeGroup: (ageGroup: AgeGroup) => void;
  /** 初始化主题（从 localStorage 恢复） */
  initTheme: () => void;
}

export const useThemeStore = create<ThemeState>((set) => ({
  ageGroup: "10-12",
  theme: getThemeByAgeGroup("10-12"),
  initialized: false,

  /**
   * 设置年龄组主题并持久化
   * @param ageGroup - 年龄组
   */
  setAgeGroup: (ageGroup: AgeGroup) => {
    setLocalStorage("alp_age_group", ageGroup);
    set({
      ageGroup,
      theme: getThemeByAgeGroup(ageGroup),
    });
  },

  /**
   * 初始化主题
   * 从 localStorage 读取保存的年龄组，应用对应主题
   */
  initTheme: () => {
    const savedAgeGroup = getLocalStorage<AgeGroup>("alp_age_group", "10-12");
    set({
      ageGroup: savedAgeGroup,
      theme: getThemeByAgeGroup(savedAgeGroup),
      initialized: true,
    });
  },
}));
