"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, Award, BarChart3, BookOpen, Clock3, Target, TrendingUp } from "lucide-react";
import { MainLayout } from "@/components/layout/main-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { apiClient } from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";

type Report = {
  overview: { total_answered: number; correct_rate: number; study_days: number; total_time_minutes: number };
  subject_mastery: Array<{ subject: string; level: number; total: number; correct: number }>;
  weak_points: Array<{ point: string; level: number; total: number; suggestion: string }>;
  strong_points: Array<{ point: string; level: number; total: number }>;
  daily_trend: Array<{ date: string; answered: number; correct: number }>;
  knowledge_heatmap: Record<string, number>;
};

const PERIODS = [7, 30, 90] as const;

export default function LearningReportPage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const [days, setDays] = useState<(typeof PERIODS)[number]>(30);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    apiClient
      .get<Report>("/v1/user/behavior/report", { days })
      .then((data) => active && setReport(data))
      .catch(() => active && setError("学习报告暂时无法加载，请稍后重试。"))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [days, isAuthenticated]);

  if (!isAuthenticated) {
    return <MainLayout><EmptyState title="登录后查看学习报告" action="去登录" href="/login" /></MainLayout>;
  }
  if (loading) {
    return <MainLayout><div className="flex min-h-[50vh] items-center justify-center text-sm text-brand-gray">正在生成学习报告…</div></MainLayout>;
  }
  if (error || !report) {
    return <MainLayout><EmptyState title={error || "暂无学习报告"} action="重新加载" href="/report" /></MainLayout>;
  }

  const maxAnswered = Math.max(...report.daily_trend.map((item) => item.answered), 1);
  const heatmapEntries = Object.entries(report.knowledge_heatmap);
  return (
    <MainLayout>
      <main className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900"><TrendingUp className="h-7 w-7 text-brand-blue" />学习报告</h1>
            <p className="mt-1 text-sm text-brand-gray">用每一次答题记录，发现自己的进步与下一步重点。</p>
          </div>
          <div className="flex rounded-lg border border-gray-200 bg-white p-1" role="tablist" aria-label="报告时间范围">
            {PERIODS.map((period) => <Button key={period} size="sm" variant={days === period ? "default" : "ghost"} onClick={() => setDays(period)}>{period} 天</Button>)}
          </div>
        </header>

        <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Metric icon={BookOpen} label="答题总数" value={`${report.overview.total_answered}`} />
          <Metric icon={Target} label="正确率" value={`${Math.round(report.overview.correct_rate * 100)}%`} color="text-emerald-600" />
          <Metric icon={Clock3} label="学习天数" value={`${report.overview.study_days} 天`} color="text-blue-600" />
          <Metric icon={Award} label="累计时长" value={`${Math.round(report.overview.total_time_minutes)} 分钟`} color="text-violet-600" />
        </section>

        <section className="grid gap-6 lg:grid-cols-2">
          <Card className="shadow-card"><CardHeader><CardTitle className="text-lg">学科掌握度</CardTitle></CardHeader><CardContent className="space-y-4">
            {report.subject_mastery.length ? report.subject_mastery.map((item) => <div key={item.subject}><div className="mb-1 flex justify-between text-sm"><span>{item.subject}</span><span className="text-brand-gray">{Math.round(item.level * 100)}% · {item.correct}/{item.total}</span></div><Progress value={item.level * 100} /></div>) : <NoData text="完成一次答题后，这里会展示各学科掌握度。" />}
          </CardContent></Card>
          <Card className="shadow-card"><CardHeader><CardTitle className="flex items-center gap-2 text-lg"><BarChart3 className="h-5 w-5 text-brand-blue" />每日答题趋势</CardTitle></CardHeader><CardContent>
            <div className="flex h-44 items-end gap-1" aria-label="每日答题趋势图">{report.daily_trend.map((item) => <div key={item.date} className="flex min-w-0 flex-1 flex-col items-center gap-1"><span className="text-[10px] text-brand-gray">{item.answered || ""}</span><div className="w-full min-h-1 rounded-t bg-blue-400 transition-colors hover:bg-blue-500" style={{ height: `${Math.max((item.answered / maxAnswered) * 120, item.answered ? 4 : 1)}px` }} title={`${item.date}：${item.answered} 题，答对 ${item.correct} 题`} /><span className="text-[9px] text-brand-gray">{item.date.slice(5)}</span></div>)}</div>
          </CardContent></Card>
        </section>

        <section className="grid gap-6 lg:grid-cols-2">
          <PointList title="薄弱知识点" icon={<AlertCircle className="h-5 w-5 text-rose-500" />} items={report.weak_points} tone="rose" empty="暂未发现需要重点巩固的知识点。" />
          <PointList title="优势知识点" icon={<Award className="h-5 w-5 text-emerald-500" />} items={report.strong_points} tone="emerald" empty="多完成一些练习，系统会在这里识别你的优势。" />
        </section>

        <Card className="shadow-card"><CardHeader><CardTitle className="text-lg">知识点掌握热力图</CardTitle></CardHeader><CardContent>{heatmapEntries.length ? <div className="flex flex-wrap gap-3">{heatmapEntries.map(([point, level]) => <div key={point} className="rounded-lg px-3 py-2 text-sm" style={{ backgroundColor: `rgba(59, 130, 246, ${0.12 + level * 0.7})`, color: level > 0.68 ? "white" : "#1e3a8a" }}>{point} {Math.round(level * 100)}%</div>)}</div> : <NoData text="还没有知识点数据，开始练习吧。" />}</CardContent></Card>
      </main>
    </MainLayout>
  );
}

function Metric({ icon: Icon, label, value, color = "text-gray-900" }: { icon: typeof BookOpen; label: string; value: string; color?: string }) { return <Card className="shadow-card"><CardContent className="p-4"><div className="mb-2 flex items-center gap-2 text-sm text-brand-gray"><Icon className="h-4 w-4" />{label}</div><p className={`text-2xl font-bold ${color}`}>{value}</p></CardContent></Card>; }
function NoData({ text }: { text: string }) { return <div className="py-8 text-center text-sm text-brand-gray">{text}</div>; }
function EmptyState({ title, action, href }: { title: string; action: string; href: string }) { return <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4"><p className="text-sm text-brand-gray">{title}</p><Link href={href}><Button>{action}</Button></Link></div>; }
function PointList({ title, icon, items, tone, empty }: { title: string; icon: React.ReactNode; items: Array<{ point: string; level: number; suggestion?: string }>; tone: "rose" | "emerald"; empty: string }) { const classes = tone === "rose" ? "border-rose-100 bg-rose-50" : "border-emerald-100 bg-emerald-50"; return <Card className="shadow-card"><CardHeader><CardTitle className="flex items-center gap-2 text-lg">{icon}{title}</CardTitle></CardHeader><CardContent className="space-y-3">{items.length ? items.map((item) => <div key={item.point} className={`rounded-lg border p-3 ${classes}`}><div className="flex justify-between gap-2 text-sm font-medium"><span>{item.point}</span><span>{Math.round(item.level * 100)}%</span></div><Progress value={item.level * 100} className="mt-2" />{item.suggestion && <p className="mt-2 text-xs text-brand-gray">{item.suggestion}</p>}</div>) : <NoData text={empty} />}</CardContent></Card>; }
