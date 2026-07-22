/**
 * 学习状态管理 - Zustand Store
 *
 * 功能说明：
 * - 管理课程列表、课程详情、课时、AI 对话等学习相关状态
 * - 支持从后端 API 获取数据，失败时 fallback 到 Mock 数据
 * - 已登录用户合并后端学习进度，未登录用户使用本地存储
 * - AI 对话使用 SSE 流式响应，支持实时显示内容
 * - 课时完成后自动同步到后端（已登录）和本地存储（所有用户）
 */

import { create } from "zustand";
import type { Course, CourseFilter, Lesson, ChatMessage, Subject, DifficultyLevel, AgeGroup, QuizQuestion, QuizAnswer, QuizResult } from "@/types";
import apiClient, { API_BASE_URL_FOR_CLIENT, TokenManager } from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import {
  mapQuizQuestion,
  type QuizQuestionPayload,
} from "@/components/learning/quiz-question-mapper";
import {
  getAllLocalCourseProgress,
  getLocalChatHistory,
  saveLocalCourseProgress,
  saveLocalChatHistory,
  clearLocalChatHistory,
} from "@/lib/local-storage";

/**
 * 将后端 API 返回的课程字段映射为前端 Course 类型
 * @param apiCourse - 后端返回的原始课程对象
 * @returns 前端 Course 对象
 */
function mapApiCourse(apiCourse: any): Course {
  const id = apiCourse.id ?? apiCourse.slug ?? "";
  return {
    id,
    slug: apiCourse.slug ?? id,
    title: apiCourse.title ?? "",
    description: apiCourse.description ?? "",
    coverImage: apiCourse.image_url ?? apiCourse.coverImage ?? "/covers/default.jpg",
    subject: apiCourse.subject ?? "math",
    difficulty: apiCourse.difficulty ?? "beginner",
    ageGroup: apiCourse.age_group ?? apiCourse.ageGroup ?? "06-09",
    duration: apiCourse.duration ?? 0,
    totalLessons: apiCourse.total_lessons ?? apiCourse.totalLessons ?? 0,
    completedLessons: apiCourse.completed_lessons ?? apiCourse.completedLessons ?? 0,
    progress: apiCourse.progress ?? 0,
    rating: apiCourse.rating ?? 4.0,
    enrollCount: apiCourse.enroll_count ?? apiCourse.enrollCount ?? 0,
    tags: Array.isArray(apiCourse.tags) ? apiCourse.tags : [],
    teacher: apiCourse.teacher ?? { id: "teacher-0", name: "AI学堂", avatar: "/avatars/default.jpg" },
    createdAt: apiCourse.created_at ?? apiCourse.createdAt ?? new Date().toISOString(),
    updatedAt: apiCourse.updated_at ?? apiCourse.updatedAt ?? new Date().toISOString(),
  };
}

/**
 * 将后端 API 返回的课时字段映射为前端 Lesson 类型
 * @param apiLesson - 后端返回的原始课时对象
 * @returns 前端 Lesson 对象
 */
function mapApiLesson(apiLesson: any): Lesson {
  return {
    id: apiLesson.id ?? "",
    courseId: apiLesson.course_id ?? apiLesson.courseId ?? "",
    title: apiLesson.title ?? "",
    description: apiLesson.description ?? "",
    order: apiLesson.order ?? 0,
    type: apiLesson.type ?? "text",
    duration: apiLesson.duration ?? 0,
    content: apiLesson.content ?? "",
    completed: apiLesson.completed ?? false,
    resources: apiLesson.resources ?? [],
    knowledgeNodeId: apiLesson.knowledge_node_id ?? apiLesson.knowledgeNodeId ?? undefined,
  };
}

/** 学习状态接口 */
interface LearningState {
  /** 课程列表 */
  courses: Course[];
  /** 当前课程 */
  currentCourse: Course | null;
  /** 当前课时列表 */
  currentLessons: Lesson[];
  /** 当前活跃课时 */
  currentLesson: Lesson | null;
  /** 继续学习的课程 */
  continueLearning: Course[];
  /** 推荐课程 */
  recommendedCourses: Course[];
  /** 筛选条件 */
  filter: CourseFilter;
  /** AI 对话历史 */
  chatMessages: ChatMessage[];
  /** 是否正在加载 */
  isLoading: boolean;
  /** 是否 AI 正在回复 */
  isAIResponding: boolean;
  tutorStatus: "idle" | "streaming" | "ready" | "unavailable";
  journeyStatus: "loading" | "ready" | "empty" | "error" | "offline";
  /** 总页数 */
  totalPages: number;
  /** 当前页 */
  currentPage: number;
  /** 测验题目列表 */
  quizQuestions: QuizQuestion[];
  /** 用户测验答案 */
  quizAnswers: QuizAnswer[];
  /** 测验结果 */
  quizResult: QuizResult | null;
  /** 测验是否正在加载 */
  isQuizLoading: boolean;

  /** 获取课程列表 */
  fetchCourses: (filter?: CourseFilter) => Promise<void>;
  /** 获取课程详情 */
  fetchCourseDetail: (courseId: string) => Promise<void>;
  /** 设置当前课时 */
  setCurrentLesson: (lesson: Lesson | null) => void;
  /** 更新筛选条件 */
  setFilter: (filter: Partial<CourseFilter>) => void;
  /** 重置筛选 */
  resetFilter: () => void;
  /** 发送 AI 消息（SSE 流式） */
  sendAIMessage: (message: string) => Promise<void>;
  /** 标记当前课时完成并切换到下一课时 */
  startLearning: () => Promise<void>;
  /** 报名课程 */
  enrollCourse: (courseId: string) => Promise<void>;
  /** 清空对话历史 */
  clearChat: () => void;
  /** 设置加载状态 */
  setLoading: (loading: boolean) => void;
  /** 获取测验题目 */
  fetchQuizQuestions: (courseId: string, lessonId: string) => Promise<void>;
  /** 设置测验答案 */
  setQuizAnswer: (questionId: string, answer: string | string[]) => void;
  /** 提交测验 */
  submitQuiz: (courseId: string, lessonId: string) => Promise<QuizResult>;
  /** 重置测验状态 */
  resetQuiz: () => void;
}

/** 默认筛选条件 */
const DEFAULT_FILTER: CourseFilter = {
  sortBy: "popular",
  page: 1,
  pageSize: 12,
};

export const useLearningStore = create<LearningState>((set, get) => ({
  courses: [],
  currentCourse: null,
  currentLessons: [],
  currentLesson: null,
  continueLearning: [],
  recommendedCourses: [],
  filter: DEFAULT_FILTER,
  chatMessages: [],
  isLoading: false,
  isAIResponding: false,
  tutorStatus: "idle",
  journeyStatus: "loading",
  totalPages: 1,
  currentPage: 1,
  quizQuestions: [],
  quizAnswers: [],
  quizResult: null,
  isQuizLoading: false,

  /**
   * 获取课程列表
   * 优先从后端获取，失败时 fallback 到 Mock 数据
   * @param filter - 筛选条件（可选）
   */
  fetchCourses: async (filter?: CourseFilter) => {
    set({ isLoading: true });
    try {
      const currentFilter = filter || get().filter;
      try {
        const data = await apiClient.get<{ items: any[]; total: number; page: number; totalPages: number }>("/v1/courses", {
          page: currentFilter.page || 1,
          page_size: currentFilter.pageSize || 20,
          subject: currentFilter.subject,
          difficulty: currentFilter.difficulty,
          age_group: currentFilter.ageGroup,
          keyword: currentFilter.keyword,
          sort_by: currentFilter.sortBy,
        });
        // 如果后端返回空数据，也 fallback 到 mock
        if (!data.items || data.items.length === 0) {
          throw new Error("Empty response");
        }
        let courses = data.items.map(mapApiCourse);

        // 仅已登录用户合并学习进度（确保数据与账号绑定）
        const { isAuthenticated } = useAuthStore.getState();
        if (isAuthenticated) {
          // 尝试获取用户课程进度（从后端数据库）
          try {
            const userData = await apiClient.get<{ items: any[] }>("/v1/user/courses", {
              page: 1,
              page_size: 100,
            });
            const userCourses = userData.items || [];
            courses = courses.map((course) => {
              const userCourse = userCourses.find(
                (uc) => uc.course_id === course.id || uc.course?.id === course.id
              );
              if (userCourse) {
                return {
                  ...course,
                  completedLessons: userCourse.completed_lessons ?? course.completedLessons,
                  progress: userCourse.progress ?? course.progress,
                };
              }
              return course;
            });
          } catch {
            // 后端获取失败，用 localStorage 补充（已登录用户的本地缓存）
            const localProgress = getAllLocalCourseProgress();
            courses = courses.map((course) => {
              const local = localProgress[course.id];
              if (local && course.totalLessons > 0) {
                const completedCount = local.completedLessonIds.length;
                const progress = Math.round((completedCount / course.totalLessons) * 100);
                return {
                  ...course,
                  completedLessons: completedCount,
                  progress: Math.min(progress, 100),
                };
              }
              return course;
            });
          }
        }
        // 未登录用户：不合并任何进度数据，课程显示 0% 进度

        set({
          courses,
          isLoading: false,
          currentPage: data.page,
          totalPages: data.totalPages,
        });
      } catch {
        // 后端不可用或返回空数据时 fallback 到 mock 数据
        console.warn("后端 API 无数据，使用 mock 数据");
        const { getMockCourses } = await import("@/lib/content");
        let mockCourses = getMockCourses(currentFilter.pageSize || 12);

        // 合并本地存储的学习进度（仅已登录用户）
        const { isAuthenticated: isAuth } = useAuthStore.getState();
        if (isAuth) {
          const localProgress = getAllLocalCourseProgress();
          mockCourses = mockCourses.map((course) => {
            const local = localProgress[course.id];
            if (local && course.totalLessons > 0) {
              const completedCount = local.completedLessonIds.length;
              const progress = Math.round((completedCount / course.totalLessons) * 100);
              return {
                ...course,
                completedLessons: completedCount,
                progress: Math.min(progress, 100),
              };
            }
            return course;
          });
        }

        set({
          courses: mockCourses,
          isLoading: false,
          currentPage: currentFilter.page || 1,
          totalPages: 1,
        });
      }
    } catch (error) {
      console.error("获取课程列表失败:", error);
      set({ isLoading: false });
    }
  },

  /**
   * 获取课程详情
   * 优先从后端获取，失败时 fallback 到 Mock 数据
   * 合并本地存储的课时完成状态和聊天记录
   * @param courseId - 课程 ID
   */
  fetchCourseDetail: async (courseId: string) => {
    set({ isLoading: true });
    try {
      try {
        const data = await apiClient.get<any>("/v1/courses/" + courseId);
        const course = mapApiCourse(data);
        let lessons: Lesson[] = (data.lessons ?? []).map(mapApiLesson);
        // 仅已登录用户合并本地存储的课时完成状态
        const { isAuthenticated } = useAuthStore.getState();
        if (isAuthenticated) {
          const localProgress = getAllLocalCourseProgress();
          const local = localProgress[course.id];
          if (local) {
            // 收集需要同步到后端的课时（已登录且本地完成但后端未完成）
            const lessonsToSync: Lesson[] = [];
            lessons = lessons.map((lesson) => {
              const localCompleted = local.completedLessonIds.includes(lesson.id);
              if (isAuthenticated && localCompleted && !lesson.completed) {
                lessonsToSync.push(lesson);
              }
              return {
                ...lesson,
                // 取并集：后端或本地任一完成，都算完成
                completed: lesson.completed || localCompleted,
              };
            });
            // 同步课程的已完成课时数
            const completedCount = lessons.filter((l) => l.completed).length;
            course.completedLessons = completedCount;
            course.progress = lessons.length > 0 ? Math.round((completedCount / lessons.length) * 100) : 0;

            // 后台串行同步未同步的课时（避免并发触发速率限制）
            if (lessonsToSync.length > 0) {
              (async () => {
                for (const lesson of lessonsToSync) {
                  try {
                    await apiClient.post(`/v1/user/lessons/${lesson.id}/complete`, {
                      time_spent_seconds: lesson.duration * 60,
                    });
                    // 每个课时同步间隔 1 秒，避免触发速率限制
                    await new Promise((resolve) => setTimeout(resolve, 1000));
                  } catch {
                    // 同步失败则停止后续同步（可能已被限流）
                    break;
                  }
                }
                // 同步完成后刷新统计
                useAuthStore.getState().fetchUserStats();
              })();
            }
          }
        }

        // 加载本地聊天记录
        const localChat = getLocalChatHistory(course.id);

        set({
          currentCourse: course,
          currentLessons: lessons,
          currentLesson: lessons.find((l) => !l.completed) || lessons[0] || null,
          chatMessages: localChat,
          isLoading: false,
          journeyStatus: course ? "ready" : "empty",
        });
      } catch {
        // 后端不可用时 fallback 到 mock 数据
        console.warn("后端 API 不可用，使用 mock 数据");
        const { getMockCourseDetail, getMockLessons } = await import("@/lib/content");
        let course = getMockCourseDetail(courseId);
        let lessons = getMockLessons(courseId);
        if (!course) {
          set({ isLoading: false });
          return;
        }

        // 合并本地存储的课时完成状态
        const localProgress = getAllLocalCourseProgress();
        const local = localProgress[course.id];
        if (local) {
          lessons = lessons.map((lesson) => ({
            ...lesson,
            completed: local.completedLessonIds.includes(lesson.id),
          }));
          const completedCount = lessons.filter((l) => l.completed).length;
          course = { ...course, completedLessons: completedCount, progress: lessons.length > 0 ? Math.round((completedCount / lessons.length) * 100) : 0 };
        }

        const localChat = getLocalChatHistory(course.id);

        set({
          currentCourse: course,
          currentLessons: lessons,
          currentLesson: lessons.find((l) => !l.completed) || lessons[0] || null,
          chatMessages: localChat,
          isLoading: false,
          journeyStatus: "offline",
        });
      }
    } catch (error) {
      console.error("获取课程详情失败:", error);
      set({ isLoading: false, journeyStatus: "error" });
    }
  },

  /** 设置当前课时 */
  setCurrentLesson: (lesson) => set({ currentLesson: lesson }),

  /**
   * 更新筛选条件并重新获取课程
   * @param partialFilter - 部分筛选条件
   */
  setFilter: (partialFilter) => {
    const newFilter = { ...get().filter, ...partialFilter, page: 1 };
    set({ filter: newFilter });
    get().fetchCourses(newFilter);
  },

  /** 重置筛选条件 */
  resetFilter: () => {
    set({ filter: DEFAULT_FILTER });
    get().fetchCourses(DEFAULT_FILTER);
  },

  /**
   * 发送 AI 消息（SSE 流式响应）
   * @param message - 用户消息内容
   */
  sendAIMessage: async (message) => {
    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: message,
      timestamp: new Date().toISOString(),
    };

    set((state) => ({
      chatMessages: [...state.chatMessages, userMessage],
      isAIResponding: true,
      tutorStatus: "streaming",
    }));

    // 创建一个空的 AI 消息占位，用于实时更新流式内容
    const aiMessageId = `msg-${Date.now()}-ai`;
    const aiPlaceholder: ChatMessage = {
      id: aiMessageId,
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
    };
    set((state) => ({
      chatMessages: [...state.chatMessages, aiPlaceholder],
    }));

    try {
      // 构建对话上下文
      const state = get();
      const context: Record<string, unknown> = {};
      if (state.currentCourse) {
        context.courseId = state.currentCourse.id;
        context.courseTitle = state.currentCourse.title;
      }
      if (state.currentLesson) {
        context.lessonTitle = state.currentLesson.title;
      }

      const conversationHistory = state.chatMessages
        .slice(-10) // 取最近 10 条消息（不含刚添加的 AI 占位）
        .filter((msg) => msg.id !== aiMessageId)
        .map((msg) => ({
          role: msg.role,
          content: msg.content,
        }));

      // 使用 fetch 获取 SSE 流
      const token = TokenManager.getAccessToken();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const response = await fetch(`${API_BASE_URL_FOR_CLIENT}/v1/ai/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify({ message, context, conversationHistory }),
      });

      if (!response.ok) throw new Error(`请求失败: ${response.status}`);

      // 当前辅导接口返回普通 JSON；保留下面的 SSE 分支以兼容旧部署。
      const contentType = response.headers.get("content-type") ?? "";
      if (contentType.includes("application/json")) {
        type CourseTutorResponse = {
          messages?: Array<{ name?: string; content: string }>;
          suggested_next_step?: string;
        };
        const jsonPayload = (await response.json()) as CourseTutorResponse & {
          data?: CourseTutorResponse;
        };
        const tutorResponse: CourseTutorResponse = jsonPayload.data ?? jsonPayload;
        const replyParts = (tutorResponse.messages ?? []).map(
          (item) => `${item.name || "AI 导师"}：${item.content}`
        );
        if (tutorResponse.suggested_next_step) {
          replyParts.push(`下一步：${tutorResponse.suggested_next_step}`);
        }
        const fullContent = replyParts.join("\n\n");
        if (!fullContent) throw new Error("AI 辅导老师暂时没有返回内容");

        set((state) => ({
          chatMessages: state.chatMessages.map((msg) =>
            msg.id === aiMessageId ? { ...msg, content: fullContent } : msg
          ),
          isAIResponding: false,
          tutorStatus: "ready",
        }));
        const currentState = get();
        if (currentState.currentCourse) {
          saveLocalChatHistory(currentState.currentCourse.id, currentState.chatMessages);
        }
        return;
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullContent = "";

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const text = decoder.decode(value, { stream: true });
          // 解析 SSE 行
          const lines = text.split("\n");
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const jsonStr = line.slice(6);
              if (!jsonStr.trim()) continue;
              try {
                const data = JSON.parse(jsonStr);
                if (data.error) {
                  // 收到错误事件，用错误消息替换当前内容
                  fullContent = data.content;
                  set((state) => ({
                    chatMessages: state.chatMessages.map((msg) =>
                      msg.id === aiMessageId
                        ? { ...msg, content: fullContent }
                        : msg
                    ),
                  }));
                } else if (data.done) {
                  // 流结束事件，使用完整回复（确保最终内容完整）
                  fullContent = data.reply;
                  set((state) => ({
                    chatMessages: state.chatMessages.map((msg) =>
                      msg.id === aiMessageId
                        ? { ...msg, content: fullContent }
                        : msg
                    ),
                  }));
                } else if (data.content) {
                  // 收到内容 chunk，实时更新 AI 消息
                  fullContent += data.content;
                  set((state) => ({
                    chatMessages: state.chatMessages.map((msg) =>
                      msg.id === aiMessageId
                        ? { ...msg, content: fullContent }
                        : msg
                    ),
                  }));
                }
              } catch {
                // JSON 解析失败，跳过该行
              }
            }
          }
        }
      }

      // 最终更新并保存到 localStorage（未登录用户）
      const currentState = get();
      if (currentState.currentCourse) {
        saveLocalChatHistory(currentState.currentCourse.id, currentState.chatMessages);
      }

      set({ isAIResponding: false, tutorStatus: fullContent ? "ready" : "unavailable" });
    } catch (error) {
      console.warn("AI 对话不可用", error instanceof Error ? error.name : "unknown_error");
      const unavailableContent = "AI 辅导服务暂时不可用，请稍后重试。";
      set((state) => ({
        chatMessages: state.chatMessages.map((msg) =>
          msg.id === aiMessageId
            ? { ...msg, content: unavailableContent }
            : msg
        ),
        isAIResponding: false,
        tutorStatus: "unavailable",
      }));

      // 保存到 localStorage
      const currentState = get();
      if (currentState.currentCourse) {
        saveLocalChatHistory(currentState.currentCourse.id, currentState.chatMessages);
      }
    }
  },

  /**
   * 标记当前课时完成并切换到下一课时
   * 同步到后端（已登录）和本地存储（所有用户）
   */
  startLearning: async () => {
    const { currentLesson, currentLessons, currentCourse } = get();
    if (!currentLesson || !currentCourse) return;

    try {
      // 调用后端 API 标记课时完成（已登录用户）
      await apiClient.post(`/v1/user/lessons/${currentLesson.id}/complete`, {
        time_spent_seconds: currentLesson.duration * 60,
      });
    } catch (error) {
      console.warn("后端标记课时完成失败（未登录或网络错误）:", error);
    }

    // 总是保存到 localStorage（前端缓存，确保未登录和已登录用户都有本地备份）
    saveLocalCourseProgress(currentCourse.id, currentLesson.id);

    // 将当前课时标记为已完成，并自动切换到下一个未完成的课时
    const updatedLessons = currentLessons.map((lesson) =>
      lesson.id === currentLesson.id ? { ...lesson, completed: true } : lesson,
    );

    const nextIncompleteLesson = updatedLessons.find((l) => !l.completed);

    // 更新当前课程的进度
    const completedCount = updatedLessons.filter((l) => l.completed).length;
    const progress = updatedLessons.length > 0 ? Math.round((completedCount / updatedLessons.length) * 100) : 0;

    set({
      currentLessons: updatedLessons,
      currentLesson: nextIncompleteLesson || null,
      currentCourse: currentCourse
        ? {
            ...currentCourse,
            completedLessons: completedCount,
            progress,
          }
        : null,
    });

    // 刷新首页学习统计（已登录用户）
    try {
      const { isAuthenticated } = useAuthStore.getState();
      if (isAuthenticated) {
        await useAuthStore.getState().fetchUserStats();
      }
    } catch {
      // 静默失败
    }
  },

  /**
   * 报名课程
   * @param courseId - 课程 ID
   */
  enrollCourse: async (courseId: string) => {
    try {
      await apiClient.post(`/v1/user/courses/${courseId}/enroll`);
      // 报名成功后刷新课程列表或当前课程
      const { currentCourse, fetchCourseDetail } = get();
      if (currentCourse && currentCourse.id === courseId) {
        await fetchCourseDetail(courseId);
      }
    } catch (error) {
      console.error("报名课程失败:", error);
      throw error;
    }
  },

  /** 清空当前课程的对话历史 */
  clearChat: () => {
    const { currentCourse } = get();
    if (currentCourse) {
      saveLocalChatHistory(currentCourse.id, []);
    }
    set({ chatMessages: [] });
  },

  /** 设置加载状态 */
  setLoading: (loading) => set({ isLoading: loading }),

  /**
   * 获取测验题目
   * 调用 GET /v1/courses/{cid}/lessons/{lid}/quiz
   * @param courseId - 课程 ID
   * @param lessonId - 课时 ID
   */
  fetchQuizQuestions: async (courseId: string, lessonId: string) => {
    set({ isQuizLoading: true });
    try {
      const data = await apiClient.get<QuizQuestionPayload[]>(`/v1/courses/${courseId}/lessons/${lessonId}/quiz`);
      const questions: QuizQuestion[] = data
        .map((question) => mapQuizQuestion(question))
        .filter((question): question is NonNullable<typeof question> => question !== null);
      set({ quizQuestions: questions, quizAnswers: [], quizResult: null, isQuizLoading: false });
    } catch (error) {
      console.error("获取测验题目失败:", error);
      set({ isQuizLoading: false });
    }
  },

  /**
   * 设置某道题的答案
   * 若该题已存在答案则覆盖，否则追加
   * @param questionId - 题目 ID
   * @param answer - 用户选择的答案
   */
  setQuizAnswer: (questionId: string, answer: string | string[]) => {
    set((state) => {
      const exists = state.quizAnswers.find((a) => a.questionId === questionId);
      const newAnswers = exists
        ? state.quizAnswers.map((a) => (a.questionId === questionId ? { ...a, answer } : a))
        : [...state.quizAnswers, { questionId, answer }];
      return { quizAnswers: newAnswers };
    });
  },

  /**
   * 提交测验答案
   * @param courseId - 课程 ID
   * @param lessonId - 课时 ID
   * @returns 测验结果
   */
  submitQuiz: async (courseId: string, lessonId: string) => {
    const { quizAnswers } = get();
    try {
      const data = await apiClient.post<any>(`/v1/courses/${courseId}/lessons/${lessonId}/quiz/submit`, {
        answers: quizAnswers,
      });
      const result: QuizResult = {
        score: data.score ?? 0,
        correctCount: data.correct_count ?? data.correctCount ?? 0,
        totalCount: data.total_count ?? data.totalCount ?? 0,
        details: data.details ?? [],
        passed: data.passed ?? false,
      };
      set({ quizResult: result });
      return result;
    } catch (error) {
      console.error("提交测验失败:", error);
      throw error;
    }
  },

  /** 重置测验状态（清空答案与结果） */
  resetQuiz: () => set({ quizAnswers: [], quizResult: null }),
}));

/**
 * 便捷 Hook：获取带筛选功能的课程列表
 * 封装常用筛选条件的设置方法
 */
export function useCourseFilter() {
  const store = useLearningStore();
  return {
    ...store,
    setSubject: (subject?: Subject) => store.setFilter({ subject }),
    setDifficulty: (difficulty?: DifficultyLevel) => store.setFilter({ difficulty }),
    setAgeGroup: (ageGroup?: AgeGroup) => store.setFilter({ ageGroup }),
    setKeyword: (keyword?: string) => store.setFilter({ keyword }),
    setSortBy: (sortBy?: CourseFilter["sortBy"]) => store.setFilter({ sortBy }),
    setPage: (page: number) => store.setFilter({ page }),
  };
}
