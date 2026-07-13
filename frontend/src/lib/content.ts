/* ============================================
   内容获取工具 - Mock 数据 & 内容工具函数
   ============================================ */

import type { Course, Subject, DifficultyLevel, AgeGroup, Lesson } from "@/types";

/** 学科图标映射 */
export const SUBJECT_ICONS: Record<Subject, string> = {
  math: "Calculator",
  science: "FlaskConical",
  chinese: "BookOpen",
  english: "Languages",
  programming: "Code2",
  art: "Palette",
  history: "Landmark",
};

/** 学科列表 */
export const SUBJECT_LIST: Array<{ key: Subject; name: string; icon: string }> = [
  { key: "math", name: "数学", icon: "Calculator" },
  { key: "science", name: "科学", icon: "FlaskConical" },
  { key: "chinese", name: "语文", icon: "BookOpen" },
  { key: "english", name: "英语", icon: "Languages" },
  { key: "programming", name: "编程", icon: "Code2" },
  { key: "art", name: "艺术", icon: "Palette" },
  { key: "history", name: "历史", icon: "Landmark" },
];

/** 难度列表 */
export const DIFFICULTY_LIST: Array<{ key: DifficultyLevel; name: string }> = [
  { key: "beginner", name: "入门" },
  { key: "intermediate", name: "进阶" },
  { key: "advanced", name: "高级" },
];

/** 年龄组列表 */
export const AGE_GROUP_LIST: Array<{ key: AgeGroup; name: string }> = [
  { key: "06-09", name: "6-9岁" },
  { key: "10-12", name: "10-12岁" },
  { key: "13-15", name: "13-15岁" },
  { key: "16-18", name: "16-18岁" },
];

/** 固定的 12 门课程数据 */
const FIXED_COURSES: Course[] = [
  {
    id: "course-1",
    title: "趣味数学入门",
    description: "适合6-9岁小朋友的趣味数学入门课程，通过趣味互动的方式学习数学知识。",
    coverImage: "/covers/math-0.jpg",
    subject: "math",
    difficulty: "beginner",
    ageGroup: "06-09",
    duration: 45,
    totalLessons: 12,
    completedLessons: 0,
    progress: 0,
    rating: 4.5,
    enrollCount: 328,
    tags: ["math", "beginner"],
    teacher: { id: "teacher-1", name: "王老师", avatar: "/avatars/teacher-1.jpg" },
    createdAt: "2024-01-01T00:00:00.000Z",
    updatedAt: "2024-06-15T00:00:00.000Z",
  },
  {
    id: "course-2",
    title: "探索自然奥秘",
    description: "适合6-9岁小朋友的探索自然奥秘课程，通过趣味互动的方式学习自然知识。",
    coverImage: "/covers/science-1.jpg",
    subject: "science",
    difficulty: "beginner",
    ageGroup: "06-09",
    duration: 38,
    totalLessons: 10,
    completedLessons: 0,
    progress: 0,
    rating: 4.2,
    enrollCount: 256,
    tags: ["science", "beginner"],
    teacher: { id: "teacher-2", name: "李老师", avatar: "/avatars/teacher-2.jpg" },
    createdAt: "2024-01-02T00:00:00.000Z",
    updatedAt: "2024-06-16T00:00:00.000Z",
  },
  {
    id: "course-3",
    title: "阅读理解技巧",
    description: "适合10-12岁小朋友的阅读理解技巧课程，通过趣味互动的方式学习阅读知识。",
    coverImage: "/covers/chinese-2.jpg",
    subject: "chinese",
    difficulty: "intermediate",
    ageGroup: "10-12",
    duration: 62,
    totalLessons: 14,
    completedLessons: 3,
    progress: 21,
    rating: 4.7,
    enrollCount: 412,
    tags: ["chinese", "intermediate"],
    teacher: { id: "teacher-3", name: "张老师", avatar: "/avatars/teacher-3.jpg" },
    createdAt: "2024-01-03T00:00:00.000Z",
    updatedAt: "2024-06-17T00:00:00.000Z",
  },
  {
    id: "course-4",
    title: "英语自然拼读",
    description: "适合6-9岁小朋友的英语自然拼读课程，通过趣味互动的方式学习英语知识。",
    coverImage: "/covers/english-3.jpg",
    subject: "english",
    difficulty: "beginner",
    ageGroup: "06-09",
    duration: 35,
    totalLessons: 10,
    completedLessons: 0,
    progress: 0,
    rating: 4.3,
    enrollCount: 189,
    tags: ["english", "beginner"],
    teacher: { id: "teacher-4", name: "陈老师", avatar: "/avatars/teacher-4.jpg" },
    createdAt: "2024-01-04T00:00:00.000Z",
    updatedAt: "2024-06-18T00:00:00.000Z",
  },
  {
    id: "course-5",
    title: "Scratch编程启蒙",
    description: "适合6-9岁小朋友的Scratch编程启蒙课程，通过趣味互动的方式学习编程知识。",
    coverImage: "/covers/programming-4.jpg",
    subject: "programming",
    difficulty: "beginner",
    ageGroup: "06-09",
    duration: 78,
    totalLessons: 16,
    completedLessons: 0,
    progress: 0,
    rating: 4.8,
    enrollCount: 567,
    tags: ["programming", "beginner"],
    teacher: { id: "teacher-5", name: "刘老师", avatar: "/avatars/teacher-5.jpg" },
    createdAt: "2024-01-05T00:00:00.000Z",
    updatedAt: "2024-06-19T00:00:00.000Z",
  },
  {
    id: "course-6",
    title: "创意绘画课",
    description: "适合6-9岁小朋友的创意绘画课课程，通过趣味互动的方式学习绘画知识。",
    coverImage: "/covers/art-5.jpg",
    subject: "art",
    difficulty: "beginner",
    ageGroup: "06-09",
    duration: 52,
    totalLessons: 12,
    completedLessons: 0,
    progress: 0,
    rating: 4.1,
    enrollCount: 145,
    tags: ["art", "beginner"],
    teacher: { id: "teacher-1", name: "王老师", avatar: "/avatars/teacher-1.jpg" },
    createdAt: "2024-01-06T00:00:00.000Z",
    updatedAt: "2024-06-20T00:00:00.000Z",
  },
  {
    id: "course-7",
    title: "中华上下五千年",
    description: "适合10-12岁小朋友的中华上下五千年课程，通过趣味互动的方式学习历史知识。",
    coverImage: "/covers/history-6.jpg",
    subject: "history",
    difficulty: "intermediate",
    ageGroup: "10-12",
    duration: 95,
    totalLessons: 20,
    completedLessons: 20,
    progress: 100,
    rating: 4.6,
    enrollCount: 378,
    tags: ["history", "intermediate"],
    teacher: { id: "teacher-2", name: "李老师", avatar: "/avatars/teacher-2.jpg" },
    createdAt: "2024-01-07T00:00:00.000Z",
    updatedAt: "2024-06-21T00:00:00.000Z",
  },
  {
    id: "course-8",
    title: "几何图形世界",
    description: "适合10-12岁小朋友的几何图形世界课程，通过趣味互动的方式学习几何知识。",
    coverImage: "/covers/math-7.jpg",
    subject: "math",
    difficulty: "intermediate",
    ageGroup: "10-12",
    duration: 68,
    totalLessons: 14,
    completedLessons: 6,
    progress: 43,
    rating: 4.4,
    enrollCount: 234,
    tags: ["math", "intermediate"],
    teacher: { id: "teacher-3", name: "张老师", avatar: "/avatars/teacher-3.jpg" },
    createdAt: "2024-01-08T00:00:00.000Z",
    updatedAt: "2024-06-22T00:00:00.000Z",
  },
  {
    id: "course-9",
    title: "物理趣味实验",
    description: "适合13-15岁小朋友的物理趣味实验课程，通过趣味互动的方式学习物理知识。",
    coverImage: "/covers/science-8.jpg",
    subject: "science",
    difficulty: "intermediate",
    ageGroup: "13-15",
    duration: 72,
    totalLessons: 12,
    completedLessons: 0,
    progress: 0,
    rating: 4.5,
    enrollCount: 198,
    tags: ["science", "intermediate"],
    teacher: { id: "teacher-4", name: "陈老师", avatar: "/avatars/teacher-4.jpg" },
    createdAt: "2024-01-09T00:00:00.000Z",
    updatedAt: "2024-06-23T00:00:00.000Z",
  },
  {
    id: "course-10",
    title: "日常口语对话",
    description: "适合10-12岁小朋友的日常口语对话课程，通过趣味互动的方式学习英语知识。",
    coverImage: "/covers/english-9.jpg",
    subject: "english",
    difficulty: "intermediate",
    ageGroup: "10-12",
    duration: 58,
    totalLessons: 16,
    completedLessons: 8,
    progress: 50,
    rating: 4.3,
    enrollCount: 312,
    tags: ["english", "intermediate"],
    teacher: { id: "teacher-5", name: "刘老师", avatar: "/avatars/teacher-5.jpg" },
    createdAt: "2024-01-10T00:00:00.000Z",
    updatedAt: "2024-06-24T00:00:00.000Z",
  },
  {
    id: "course-11",
    title: "Python入门之旅",
    description: "适合13-15岁小朋友的Python入门之旅课程，通过趣味互动的方式学习编程知识。",
    coverImage: "/covers/programming-10.jpg",
    subject: "programming",
    difficulty: "intermediate",
    ageGroup: "13-15",
    duration: 88,
    totalLessons: 18,
    completedLessons: 0,
    progress: 0,
    rating: 4.9,
    enrollCount: 623,
    tags: ["programming", "intermediate"],
    teacher: { id: "teacher-1", name: "王老师", avatar: "/avatars/teacher-1.jpg" },
    createdAt: "2024-01-11T00:00:00.000Z",
    updatedAt: "2024-06-25T00:00:00.000Z",
  },
  {
    id: "course-12",
    title: "写作能力提升",
    description: "适合13-15岁小朋友的写作能力提升课程，通过趣味互动的方式学习写作知识。",
    coverImage: "/covers/chinese-11.jpg",
    subject: "chinese",
    difficulty: "advanced",
    ageGroup: "13-15",
    duration: 74,
    totalLessons: 14,
    completedLessons: 14,
    progress: 100,
    rating: 4.6,
    enrollCount: 267,
    tags: ["chinese", "advanced"],
    teacher: { id: "teacher-2", name: "李老师", avatar: "/avatars/teacher-2.jpg" },
    createdAt: "2024-01-12T00:00:00.000Z",
    updatedAt: "2024-06-26T00:00:00.000Z",
  },
];

/** 生成 Mock 课程数据（固定数据，非随机） */
export function getMockCourses(count: number = 12): Course[] {
  return FIXED_COURSES.slice(0, count);
}

/** 获取固定课程详情 */
export function getMockCourseDetail(courseId: string): Course | undefined {
  return FIXED_COURSES.find((c) => c.id === courseId);
}

/** 固定的课时名称和类型 */
const LESSON_TEMPLATES: Array<{ title: string; type: Lesson["type"] }> = [
  { title: "课程导学", type: "video" },
  { title: "基础概念", type: "text" },
  { title: "核心知识点", type: "video" },
  { title: "实例讲解", type: "interactive" },
  { title: "互动练习", type: "interactive" },
  { title: "知识测验", type: "quiz" },
  { title: "拓展阅读", type: "text" },
  { title: "综合练习", type: "quiz" },
  { title: "项目实践", type: "game" },
  { title: "总结回顾", type: "video" },
  { title: "挑战关卡", type: "game" },
  { title: "课程回顾", type: "text" },
  { title: "期末评估", type: "quiz" },
  { title: "进阶挑战", type: "interactive" },
  { title: "趣味游戏", type: "game" },
  { title: "创意任务", type: "interactive" },
];

/** 生成 Mock 课时数据（固定数据，非随机） */
export function getMockLessons(courseId: string): Lesson[] {
  const course = getMockCourseDetail(courseId);
  const lessonCount = course ? course.totalLessons : 12;

  return Array.from({ length: lessonCount }, (_, i) => {
    const template = LESSON_TEMPLATES[i % LESSON_TEMPLATES.length];
    return {
      id: `lesson-${courseId}-${i + 1}`,
      courseId,
      title: template.title,
      description: `这是${template.title}的学习内容，预计用时${10 + ((i * 3) % 20)}分钟。`,
      order: i + 1,
      type: template.type,
      duration: 10 + ((i * 3) % 20),
      content: ` lesson content...`,
      completed: i < (course?.completedLessons || 0),
      resources: [],
    };
  });
}

/** 获取欢迎语 */
export function getWelcomeMessage(nickname: string): string {
  const hour = new Date().getHours();
  let greeting: string;
  if (hour < 6) greeting = "夜深了";
  else if (hour < 12) greeting = "早上好";
  else if (hour < 14) greeting = "中午好";
  else if (hour < 18) greeting = "下午好";
  else greeting = "晚上好";

  return `${greeting}，${nickname}！今天想学点什么？`;
}

/** 获取星期几的中文名 */
export function getWeekdayName(date: Date): string {
  const days = ["日", "一", "二", "三", "四", "五", "六"];
  return `星期${days[date.getDay()]}`;
}
