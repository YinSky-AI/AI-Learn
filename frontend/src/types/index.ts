/**
 * AI学习平台 - 全局 TypeScript 类型定义
 *
 * 功能说明：
 * - 定义项目中所有核心数据结构的 TypeScript 类型
 * - 包括用户、课程、课时、学习记录、AI 对话等
 * - 提供学科、难度、年龄组等常量映射
 */

/** 年龄分级（6-9岁、10-12岁、13-15岁、16-18岁） */
export type AgeGroup = "06-09" | "10-12" | "13-15" | "16-18";

/** 学科类型 */
export type Subject =
  | "math"
  | "science"
  | "chinese"
  | "english"
  | "programming"
  | "art"
  | "history";

/** 难度等级 */
export type DifficultyLevel = "beginner" | "intermediate" | "advanced";

/** 内容格式（视频、文本、互动、测验、游戏） */
export type ContentFormat = "video" | "text" | "interactive" | "quiz" | "game";

/** 用户角色 */
export type UserRole = "student" | "parent" | "teacher" | "admin";

/** 性别 */
export type Gender = "male" | "female" | "other";

/* ---------- 学科配置 ---------- */
/** 学科配置接口 */
export interface SubjectConfig {
  key: Subject;
  name: string;
  icon: string;
  color: {
    light: string;
    DEFAULT: string;
    dark: string;
  };
}

/* ---------- 用户相关 ---------- */
/** 用户基础信息 */
export interface User {
  id: string;
  username: string;
  nickname: string;
  email: string;
  avatar: string;
  age: number;
  ageGroup: AgeGroup;
  gender: Gender;
  role: UserRole;
  bio: string;
  interests: Subject[];
  level: number;
  points: number;
  streakDays: number;
  createdAt: string;
  updatedAt: string;
}

/** 完整用户资料（含统计、成就、徽章等） */
export interface UserProfile extends User {
  stats: UserStats;
  achievements: Achievement[];
  badges: Badge[];
  streak: Streak;
  skills: Skill[];
}

/** 用户学习统计 */
export interface UserStats {
  totalLearningTime: number; // 分钟
  completedCourses: number;
  totalCourses: number;
  totalXP: number;
  level: number;
  rank: number;
  weeklyGoal: number;
  weeklyProgress: number;
}

/** 连续学习记录 */
export interface Streak {
  current: number;
  longest: number;
  lastActiveDate: string;
  history: string[]; // 最近30天活跃日期
}

/** 成就 */
export interface Achievement {
  id: string;
  title: string;
  description: string;
  icon: string;
  unlockedAt: string | null;
  progress: number;
  target: number;
  category: string;
}

/** 徽章 */
export interface Badge {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  earnedAt: string | null;
  condition: string;
}

/** 技能 */
export interface Skill {
  name: string;
  subject: Subject;
  level: number;
  progress: number;
  xp: number;
  maxXp: number;
}

/* ---------- 课程相关 ---------- */
/** 课程 */
export interface Course {
  id: string;
  slug?: string;
  title: string;
  description: string;
  coverImage: string;
  subject: Subject;
  difficulty: DifficultyLevel;
  ageGroup: AgeGroup;
  duration: number; // 分钟
  totalLessons: number;
  completedLessons: number;
  progress: number; // 0-100
  rating: number; // 0-5
  enrollCount: number;
  tags: string[];
  teacher: {
    id: string;
    name: string;
    avatar: string;
  };
  createdAt: string;
  updatedAt: string;
}

/** 课时 */
export interface Lesson {
  id: string;
  courseId: string;
  title: string;
  description: string;
  order: number;
  type: ContentFormat;
  duration: number;
  content: string;
  completed: boolean;
  resources: Resource[];
}

/** 资源 */
export interface Resource {
  id: string;
  title: string;
  type: "pdf" | "video" | "link" | "image";
  url: string;
}

/* ---------- 学习记录 ---------- */
/** 学习会话 */
export interface LearningSession {
  id: string;
  userId: string;
  courseId: string;
  lessonId: string;
  startTime: string;
  endTime: string;
  duration: number;
  xpEarned: number;
  completed: boolean;
}

/* ---------- AI 对话 ---------- */
/** 聊天消息 */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  metadata?: {
    lessonId?: string;
    courseId?: string;
  };
}

/** AI 响应 */
export interface AIResponse {
  message: string;
  suggestions?: string[];
  relatedLessons?: Lesson[];
  codeExample?: string;
}

/* ---------- 筛选条件 ---------- */
/** 课程筛选条件 */
export interface CourseFilter {
  subject?: Subject;
  difficulty?: DifficultyLevel;
  ageGroup?: AgeGroup;
  keyword?: string;
  sortBy?: "popular" | "newest" | "rating" | "progress";
  page?: number;
  pageSize?: number;
}

/* ---------- 难度标签映射 ---------- */
/** 难度中文标签 */
export const DIFFICULTY_LABELS: Record<DifficultyLevel, string> = {
  beginner: "入门",
  intermediate: "进阶",
  advanced: "高级",
};

/* ---------- 学科名称映射 ---------- */
/** 学科中文名称 */
export const SUBJECT_LABELS: Record<Subject, string> = {
  math: "数学",
  science: "科学",
  chinese: "语文",
  english: "英语",
  programming: "编程",
  art: "艺术",
  history: "历史",
};

/* ---------- 年龄组映射 ---------- */
/** 年龄组中文标签 */
export const AGE_GROUP_LABELS: Record<AgeGroup, string> = {
  "06-09": "6-9岁",
  "10-12": "10-12岁",
  "13-15": "13-15岁",
  "16-18": "16-18岁",
};
