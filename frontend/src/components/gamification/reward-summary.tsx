"use client";

import { Sparkles, Trophy } from "lucide-react";

export interface GamificationReward {
  points_earned: number;
  base_points: number;
  streak_bonus: number;
  total_points?: number;
  level: number;
  streak: number;
  leveled_up?: boolean;
  new_achievements?: Array<{ id: string; name: string; description: string; icon: string }>;
}

export function RewardSummary({ reward }: { reward?: GamificationReward | null }) {
  if (!reward) return null;
  return (
    <div aria-live="polite" className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
      <div className="flex items-center gap-2 font-semibold"><Sparkles className="h-4 w-4" />本题获得 {reward.points_earned} XP{reward.streak_bonus > 0 ? `（连对加成 +${reward.streak_bonus}）` : ""}</div>
      <p className="mt-1 text-xs text-amber-800">当前连续答对 {reward.streak} 题 · 等级 {reward.level}</p>
      {reward.leveled_up && <p className="mt-2 flex items-center gap-1 font-medium"><Trophy className="h-4 w-4" />恭喜升级到 Lv.{reward.level}！</p>}
      {reward.new_achievements?.map((achievement) => <p key={achievement.id} className="mt-2 rounded bg-white/70 px-2 py-1 font-medium">{achievement.icon} 解锁成就：{achievement.name}</p>)}
    </div>
  );
}
