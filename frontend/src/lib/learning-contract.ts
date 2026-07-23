import type { AgeGroup, ContentFormat, Course, DifficultyLevel, Lesson, Subject } from "@/types";

type JsonRecord = Record<string, unknown>;

const subjects = new Set<Subject>(["math", "science", "chinese", "english", "programming", "art", "history"]);
const difficulties = new Set<DifficultyLevel>(["beginner", "intermediate", "advanced"]);
const ageGroups = new Set<AgeGroup>(["06-09", "10-12", "13-15", "16-18"]);
const contentFormats = new Set<ContentFormat>(["video", "text", "interactive", "quiz", "game"]);

const recordOf = (value: unknown): JsonRecord | null => value !== null && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : null;
const stringOf = (value: unknown, fallback = ""): string => typeof value === "string" ? value : fallback;
const numberOf = (value: unknown, fallback = 0): number => typeof value === "number" && Number.isFinite(value) ? value : fallback;
const field = (input: JsonRecord, snake: string, camel: string): unknown => input[snake] ?? input[camel];

export function mapCourseContract(input: unknown): Course | null {
  const course = recordOf(input);
  if (!course) return null;
  const id = stringOf(course.id, stringOf(course.slug));
  const title = stringOf(course.title);
  if (!id || !title) return null;
  const teacher = recordOf(course.teacher);
  const subject = stringOf(course.subject, "math") as Subject;
  const difficulty = stringOf(course.difficulty, "beginner") as DifficultyLevel;
  const ageGroup = stringOf(field(course, "age_group", "ageGroup"), "06-09") as AgeGroup;
  return {
    id, slug: stringOf(course.slug, id), title, description: stringOf(course.description),
    coverImage: stringOf(course.image_url, stringOf(course.coverImage, "/covers/default.jpg")),
    subject: subjects.has(subject) ? subject : "math", difficulty: difficulties.has(difficulty) ? difficulty : "beginner", ageGroup: ageGroups.has(ageGroup) ? ageGroup : "06-09",
    duration: numberOf(course.duration), totalLessons: numberOf(field(course, "total_lessons", "totalLessons")), completedLessons: numberOf(field(course, "completed_lessons", "completedLessons")), progress: numberOf(course.progress), rating: numberOf(course.rating, 4), enrollCount: numberOf(field(course, "enroll_count", "enrollCount")),
    tags: Array.isArray(course.tags) ? course.tags.filter((tag): tag is string => typeof tag === "string") : [],
    teacher: { id: stringOf(teacher?.id, "teacher-0"), name: stringOf(teacher?.name, "AI学堂"), avatar: stringOf(teacher?.avatar, "/avatars/default.jpg") },
    createdAt: stringOf(field(course, "created_at", "createdAt"), new Date().toISOString()), updatedAt: stringOf(field(course, "updated_at", "updatedAt"), new Date().toISOString()),
  };
}

export function mapLessonContract(input: unknown): Lesson | null {
  const lesson = recordOf(input);
  if (!lesson) return null;
  const id = stringOf(lesson.id), courseId = stringOf(field(lesson, "course_id", "courseId")), title = stringOf(lesson.title);
  if (!id || !courseId || !title) return null;
  const type = stringOf(lesson.type, "text") as ContentFormat;
  return { id, courseId, title, description: stringOf(lesson.description), order: numberOf(lesson.order), type: contentFormats.has(type) ? type : "text", duration: numberOf(lesson.duration), content: stringOf(lesson.content), completed: lesson.completed === true, resources: Array.isArray(lesson.resources) ? lesson.resources.filter((resource) => recordOf(resource) !== null) as Lesson["resources"] : [], knowledgeNodeId: stringOf(field(lesson, "knowledge_node_id", "knowledgeNodeId")) || undefined };
}
