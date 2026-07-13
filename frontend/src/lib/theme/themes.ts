/* ============================================
   年龄分级主题系统 - 4套年龄主题配置
   ============================================ */

import type { AgeGroup, AgeThemeMap } from "./types";

/** 6-9岁主题：活泼可爱，大字号，丰富色彩 */
const AGE_06_09: AgeThemeMap["06-09"] = {
  ageGroup: "06-09",
  label: "6-9岁",
  description: "适合小学低年级，活泼有趣的视觉风格",
  primary: "#FF6B6B",
  secondary: "#4ECDC4",
  accent: "#FFE66D",
  background: "#FFF5F5",
  cardBg: "#FFFFFF",
  text: "#2D3436",
  textSecondary: "#636E72",
  success: "#00B894",
  warning: "#FDCB6E",
  error: "#E17055",
  borderRadius: "20px",
  fontScale: 1.2,
  spacingScale: 1.1,
  enableAnimation: true,
  aiPersona: {
    name: "小智同学",
    avatar: "/avatars/ai-cute.svg",
    tone: "亲切活泼",
    description: "一个可爱的小伙伴，用简单有趣的方式帮你学习新知识",
  },
};

/** 10-12岁主题：清新明快，标准字号 */
const AGE_10_12: AgeThemeMap["10-12"] = {
  ageGroup: "10-12",
  label: "10-12岁",
  description: "适合小学高年级，清新明快的视觉风格",
  primary: "#2563EB",
  secondary: "#10B981",
  accent: "#F59E0B",
  background: "#F0F9FF",
  cardBg: "#FFFFFF",
  text: "#1E293B",
  textSecondary: "#64748B",
  success: "#10B981",
  warning: "#F59E0B",
  error: "#EF4444",
  borderRadius: "16px",
  fontScale: 1.1,
  spacingScale: 1.0,
  enableAnimation: true,
  aiPersona: {
    name: "学习助手",
    avatar: "/avatars/ai-friendly.svg",
    tone: "鼓励引导",
    description: "一个知识渊博又友好的学习伙伴，善于引导你发现答案",
  },
};

/** 13-15岁主题：现代科技感 */
const AGE_13_15: AgeThemeMap["13-15"] = {
  ageGroup: "13-15",
  label: "13-15岁",
  description: "适合初中阶段，现代简约的科技风格",
  primary: "#6366F1",
  secondary: "#EC4899",
  accent: "#14B8A6",
  background: "#EEF2FF",
  cardBg: "#FFFFFF",
  text: "#1E1B4B",
  textSecondary: "#6B7280",
  success: "#10B981",
  warning: "#F59E0B",
  error: "#EF4444",
  borderRadius: "12px",
  fontScale: 1.0,
  spacingScale: 1.0,
  enableAnimation: true,
  aiPersona: {
    name: "知识导师",
    avatar: "/avatars/ai-mentor.svg",
    tone: "专业启发",
    description: "一位专业的知识导师，善于用深入浅出的方式解释复杂概念",
  },
};

/** 16-18岁主题：专业简洁，成人化 */
const AGE_16_18: AgeThemeMap["16-18"] = {
  ageGroup: "16-18",
  label: "16-18岁",
  description: "适合高中阶段，专业简洁的成人化风格",
  primary: "#1E293B",
  secondary: "#2563EB",
  accent: "#6366F1",
  background: "#F8FAFC",
  cardBg: "#FFFFFF",
  text: "#0F172A",
  textSecondary: "#6B7280",
  success: "#10B981",
  warning: "#F59E0B",
  error: "#EF4444",
  borderRadius: "12px",
  fontScale: 1.0,
  spacingScale: 0.9,
  enableAnimation: false,
  aiPersona: {
    name: "学术顾问",
    avatar: "/avatars/ai-professional.svg",
    tone: "严谨专业",
    description: "一位学术顾问，提供专业深入的分析和建议",
  },
};

/** 所有年龄主题映射 */
export const AGE_THEMES: AgeThemeMap = {
  "06-09": AGE_06_09,
  "10-12": AGE_10_12,
  "13-15": AGE_13_15,
  "16-18": AGE_16_18,
};

/** 获取默认主题 */
export function getDefaultTheme(): AgeThemeMap["10-12"] {
  return AGE_10_12;
}

/** 根据年龄获取推荐主题 */
export function getThemeByAge(age: number): AgeThemeMap[keyof AgeThemeMap] {
  if (age >= 6 && age <= 9) return AGE_THEMES["06-09"];
  if (age >= 10 && age <= 12) return AGE_THEMES["10-12"];
  if (age >= 13 && age <= 15) return AGE_THEMES["13-15"];
  return AGE_THEMES["16-18"];
}

/** 根据年龄组标识获取主题 */
export function getThemeByAgeGroup(ageGroup: AgeGroup): AgeThemeMap[keyof AgeThemeMap] {
  return AGE_THEMES[ageGroup] || AGE_THEMES["10-12"];
}
