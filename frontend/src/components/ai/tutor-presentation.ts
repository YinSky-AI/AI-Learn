export type TutorRole = "teacher" | "assistant" | "diagnostician" | "encourager" | "student";

export interface TutorRoleMeta {
  name: string;
  emoji: string;
  className: string;
}

const ROLE_META: Record<TutorRole, Omit<TutorRoleMeta, "name">> = {
  teacher: { emoji: "⭐", className: "border-blue-200 bg-blue-50 text-blue-900" },
  assistant: { emoji: "🧩", className: "border-violet-200 bg-violet-50 text-violet-900" },
  diagnostician: { emoji: "🔎", className: "border-amber-200 bg-amber-50 text-amber-900" },
  encourager: { emoji: "🌞", className: "border-emerald-200 bg-emerald-50 text-emerald-900" },
  student: { emoji: "我", className: "border-slate-200 bg-slate-100 text-slate-900" },
};

export function getTutorRoleMeta(role: TutorRole, name?: string): TutorRoleMeta {
  const meta = ROLE_META[role];
  return { ...meta, name: name || (role === "student" ? "我" : "AI 辅导老师") };
}
