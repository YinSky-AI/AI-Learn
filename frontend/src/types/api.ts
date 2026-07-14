/**
 * AI学习平台 - API 响应类型定义
 *
 * 功能说明：
 * - 定义所有后端 API 的请求和响应 TypeScript 类型
 * - 与后端接口契约保持一致（字段名、数据格式）
 * - 包含通用响应包装、分页、认证、课程、AI 对话等
 */

/** 通用 API 响应包装 */
export interface ApiResponse<T> {
  code: string | number;
  message: string;
  data: T;
  timestamp?: string;
}

/** 分页响应 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

/** API 错误响应 */
export interface ApiError {
  code: number;
  message: string;
  details?: Record<string, string[]>;
}

/** 登录请求 */
export interface LoginRequest {
  username?: string;
  email?: string;
  password: string;
}

/** 注册请求 */
export interface RegisterRequest {
  username: string;
  password: string;
  email: string;
  nickname: string;
  age: number;
  gender: "male" | "female" | "other";
}

/** 登录响应（后端返回 snake_case） */
export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/** /v1/users/me 响应 */
export interface UserMeResponse {
  id: string;
  nickname: string;
  email: string;
  birth_date: string;
  age_group: string;
  avatar_url: string | null;
  total_score: number;
  streak_days: number;
  behavior_profile: unknown;
  last_login_date: string | null;
  created_at: string;
  updated_at: string;
}

/** 用户学习统计响应 */
export interface UserStats {
  total_score: number;
  streak_days: number;
  today_study_minutes: number;
  week_study_hours: number;
  total_completed_lessons: number;
  in_progress_courses: number;
  completed_courses: number;
  overall_progress: number;
}

/** 用户资料响应 */
export interface UserProfileResponse {
  profile: import("./index").UserProfile;
}

/** 课程列表响应 */
export interface CourseListResponse {
  courses: import("./index").Course[];
  total: number;
  page: number;
  totalPages: number;
}

/** 课程详情响应 */
export interface CourseDetailResponse {
  course: import("./index").Course;
  lessons: import("./index").Lesson[];
  recommendedCourses: import("./index").Course[];
}

/** 学习进度响应 */
export interface LearningProgressResponse {
  courseId: string;
  lessonId: string;
  progress: number;
  completedLessons: number;
  totalLessons: number;
  xpEarned: number;
  timeSpent: number;
}

/** AI 对话请求 */
export interface ChatRequest {
  message: string;
  context?: {
    courseId?: string;
    lessonId?: string;
    subject?: string;
  };
  conversationHistory: Array<{
    role: "user" | "assistant";
    content: string;
  }>;
}

/** AI 对话响应 */
export interface ChatResponse {
  reply: string;
  suggestions?: string[];
  relatedResources?: Array<{
    id: string;
    title: string;
    type: string;
  }>;
}

/** 首页仪表盘数据响应 */
export interface DashboardResponse {
  welcomeMessage: string;
  stats: {
    todayMinutes: number;
    weeklyMinutes: number;
    streak: number;
    totalXP: number;
    level: number;
  };
  continueLearning: import("./index").Course[];
  recentAchievements: import("./index").Achievement[];
  recommendedCourses: import("./index").Course[];
  weeklyActivity: Array<{
    date: string;
    minutes: number;
  }>;
}

/** 通知列表响应 */
export interface NotificationResponse {
  id: string;
  title: string;
  content: string;
  type: "system" | "achievement" | "reminder" | "message";
  read: boolean;
  createdAt: string;
}

/** 排行榜响应 */
export interface LeaderboardResponse {
  rankings: Array<{
    rank: number;
    userId: string;
    nickname: string;
    avatar: string;
    xp: number;
    level: number;
    streak: number;
  }>;
}

/** Token 刷新请求 */
export interface RefreshTokenRequest {
  refreshToken: string;
}

/** Token 刷新响应 */
export interface RefreshTokenResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}
