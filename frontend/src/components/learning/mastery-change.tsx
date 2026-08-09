import type { MasteryChangeResponse } from "@/types/api";

export function MasteryChange({ mastery }: { mastery?: MasteryChangeResponse }) {
  if (mastery?.before == null || mastery.after == null) return null;
  const before = Math.round(mastery.before * 100);
  const after = Math.round(mastery.after * 100);
  const delta = after - before;

  return (
    <div className="mt-3 rounded-lg bg-white/80 p-3 text-sm text-gray-700">
      <p className="font-semibold text-gray-800">知识点掌握度</p>
      <p className="mt-1">{before}% → {after}% <span className={delta >= 0 ? "text-emerald-700" : "text-amber-700"}>({delta >= 0 ? "+" : ""}{delta}%)</span></p>
    </div>
  );
}
