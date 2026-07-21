"use client";

import { useEffect, useState } from "react";
import { Crown, Flame, Medal, Trophy } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import apiClient from "@/lib/api-client";

type Kind = "daily" | "total" | "streak";
type Entry = {
  rank: number;
  user_id: string;
  nickname: string;
  avatar_url?: string;
  value: number;
  is_me: boolean;
  correct_count?: number;
  time_spent_seconds?: number;
};
type Leaderboard = { items: Entry[]; me?: Entry | null; message: string };

const tabs: Array<{ key: Kind; label: string }> = [
  { key: "daily", label: "每日挑战" },
  { key: "total", label: "总积分" },
  { key: "streak", label: "连续学习" },
];

function errorMessage(error: unknown) {
  return error && typeof error === "object" && "message" in error
    ? String(error.message)
    : "排行榜暂时无法加载";
}

export default function LeaderboardPage() {
  const [kind, setKind] = useState<Kind>("daily");
  const [data, setData] = useState<Leaderboard>({ items: [], message: "" });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiClient
      .get<Leaderboard>(`/v1/challenge/leaderboard/${kind}`)
      .then(setData)
      .catch((error) => setData({ items: [], message: errorMessage(error) }))
      .finally(() => setLoading(false));
  }, [kind]);

  const meInTop = data.items.some((item) => item.is_me);
  const unit = kind === "streak" ? "天" : "分";

  return (
    <div className="mx-auto max-w-3xl space-y-5 pb-8">
      <section className="rounded-3xl bg-gradient-to-r from-amber-400 via-orange-500 to-rose-500 p-7 text-white shadow-lg">
        <div className="flex items-center gap-3">
          <span className="rounded-2xl bg-white/20 p-3"><Trophy className="h-8 w-8" /></span>
          <div><h1 className="text-2xl font-bold">学习排行榜</h1><p className="mt-1 text-orange-50">坚持、速度和正确率都值得被看见。</p></div>
        </div>
      </section>

      <div className="flex gap-2 overflow-x-auto pb-1">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setKind(tab.key)}
            className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium transition ${kind === tab.key ? "bg-blue-600 text-white shadow-sm" : "bg-white text-gray-600 hover:bg-gray-50"}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <section aria-busy={loading} className="overflow-hidden rounded-2xl border bg-white shadow-sm">
        {loading ? (
          <p className="p-10 text-center text-sm text-gray-500">正在加载排行榜…</p>
        ) : data.items.length ? (
          data.items.map((item) => <RankRow key={item.user_id} item={item} unit={unit} />)
        ) : (
          <p className="p-10 text-center text-gray-500">{data.message || "暂无上榜记录，快来成为第一位挑战者吧"}</p>
        )}
      </section>

      {!loading && data.me && !meInTop && (
        <section className="rounded-2xl border-2 border-blue-200 bg-blue-50 p-2">
          <p className="px-3 pt-2 text-xs font-medium text-blue-700">我的排名</p>
          <RankRow item={data.me} unit={unit} standalone />
        </section>
      )}
    </div>
  );
}

function RankRow({ item, unit, standalone = false }: { item: Entry; unit: string; standalone?: boolean }) {
  const podium = [
    "bg-gradient-to-r from-amber-50 to-yellow-50 text-amber-700",
    "bg-gradient-to-r from-slate-50 to-gray-50 text-slate-600",
    "bg-gradient-to-r from-orange-50 to-amber-50 text-orange-700",
  ][item.rank - 1];
  return (
    <div className={`flex items-center gap-3 p-4 ${standalone ? "rounded-xl" : "border-b last:border-0"} ${item.is_me ? "ring-1 ring-inset ring-blue-200 bg-blue-50" : podium || ""}`}>
      <span className="flex w-9 shrink-0 justify-center font-bold">
        {item.rank === 1 ? <Crown className="h-6 w-6 text-amber-500" /> : item.rank <= 3 ? <Medal className={item.rank === 2 ? "h-6 w-6 text-slate-400" : "h-6 w-6 text-orange-500"} /> : `#${item.rank}`}
      </span>
      <Avatar className="h-10 w-10"><AvatarImage src={item.avatar_url} /><AvatarFallback>{item.nickname.slice(0, 1)}</AvatarFallback></Avatar>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-gray-900">{item.nickname}{item.is_me ? "（我）" : ""}</p>
        {item.correct_count !== undefined && <p className="text-xs text-gray-500">答对 {item.correct_count} 题 · {item.time_spent_seconds} 秒</p>}
      </div>
      <span className="flex items-center gap-1 font-bold text-blue-600">{unit === "天" && <Flame className="h-4 w-4 text-orange-500" />}{item.value}{unit}</span>
    </div>
  );
}
