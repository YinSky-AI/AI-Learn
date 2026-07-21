export type FeedbackDifficulty = "beginner" | "intermediate" | "advanced" | string | undefined;

export function getDifficultyMeta(difficulty: FeedbackDifficulty) {
  if (difficulty === "beginner") return { label: "简单", className: "bg-emerald-100 text-emerald-800" };
  if (difficulty === "intermediate") return { label: "中等", className: "bg-amber-100 text-amber-800" };
  if (difficulty === "advanced") return { label: "困难", className: "bg-rose-100 text-rose-800" };
  return { label: "未标注", className: "bg-slate-100 text-slate-700" };
}
