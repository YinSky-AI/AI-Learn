/* ============================================
   年龄分级主题系统 - 类型定义
   ============================================ */

import type { AgeGroup } from "@/types";
export type { AgeGroup };

/** 单个年龄组主题配置 */
export interface AgeTheme {
  /** 年龄组标识 */
  ageGroup: AgeGroup;
  /** 显示名称 */
  label: string;
  /** 描述 */
  description: string;
  /** 主色 */
  primary: string;
  /** 次色 */
  secondary: string;
  /** 强调色 */
  accent: string;
  /** 背景色 */
  background: string;
  /** 卡片背景色 */
  cardBg: string;
  /** 文字颜色 */
  text: string;
  /** 次文字颜色 */
  textSecondary: string;
  /** 成功色 */
  success: string;
  /** 警告色 */
  warning: string;
  /** 错误色 */
  error: string;
  /** 圆角大小 */
  borderRadius: string;
  /** 字体大小倍率 */
  fontScale: number;
  /** 间距倍率 */
  spacingScale: number;
  /** 动画是否启用 */
  enableAnimation: boolean;
  /** AI助手人设 */
  aiPersona: {
    name: string;
    avatar: string;
    tone: string;
    description: string;
  };
}

/** 主题 Context 类型 */
export interface ThemeContextType {
  /** 当前主题 */
  theme: AgeTheme;
  /** 设置主题 */
  setTheme: (ageGroup: AgeGroup) => void;
  /** 当前年龄组 */
  ageGroup: AgeGroup;
  /** 是否已初始化 */
  initialized: boolean;
}

/** 所有年龄主题映射 */
export type AgeThemeMap = Record<AgeGroup, AgeTheme>;
