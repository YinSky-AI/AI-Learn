/* ============================================
   年龄分级主题系统 - ThemeProvider
   ============================================ */

"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { AgeGroup } from "@/types";
import type { ThemeContextType } from "./types";
import { AGE_THEMES, getDefaultTheme, getThemeByAgeGroup } from "./themes";
import { getLocalStorage, setLocalStorage } from "@/lib/utils";

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

interface ThemeProviderProps {
  children: React.ReactNode;
  /** 初始年龄组（可选，优先从 localStorage 读取） */
  initialAgeGroup?: AgeGroup;
}

export function ThemeProvider({ children, initialAgeGroup }: ThemeProviderProps) {
  const [ageGroup, setAgeGroupState] = useState<AgeGroup>("10-12");
  const [initialized, setInitialized] = useState(false);

  // 初始化：从 localStorage 读取或使用传入的初始值
  useEffect(() => {
    const savedAgeGroup = getLocalStorage<AgeGroup>("alp_age_group", initialAgeGroup || "10-12");
    setAgeGroupState(savedAgeGroup);
    setInitialized(true);
  }, [initialAgeGroup]);

  const theme = useMemo(() => {
    return getThemeByAgeGroup(ageGroup);
  }, [ageGroup]);

  const setTheme = useCallback((newAgeGroup: AgeGroup) => {
    setAgeGroupState(newAgeGroup);
    setLocalStorage("alp_age_group", newAgeGroup);
  }, []);

  const contextValue = useMemo<ThemeContextType>(
    () => ({
      theme,
      setTheme,
      ageGroup,
      initialized,
    }),
    [theme, setTheme, ageGroup, initialized],
  );

  return <ThemeContext.Provider value={contextValue}>{children}</ThemeContext.Provider>;
}

/** 使用主题 Hook */
export function useTheme(): ThemeContextType {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error("useTheme 必须在 ThemeProvider 内部使用");
  }
  return context;
}

/** 获取默认导出 */
export default ThemeProvider;
