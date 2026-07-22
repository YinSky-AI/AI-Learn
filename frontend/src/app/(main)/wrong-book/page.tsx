"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BookOpenCheck, CheckCircle2, Lightbulb, RefreshCw } from "lucide-react";
import { MainLayout } from "@/components/layout/main-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TutorChat } from "@/components/ai/tutor-chat";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import apiClient, { TokenManager } from "@/lib/api-client";

type WrongQuestion = { id: string; question_id: string; question_text: string; subject: string; wrong_count: number; is_mastered: boolean; knowledge_point?: string; options?: Array<{ key: string; value: string }>; difficulty?: string };
type Stats = { total: number; mastered: number; unmastered: number; need_review_today: number; by_subject: Record<string, number> };

export default function WrongBookPage() {
  return (
    <MainLayout>
      <WrongBookContent />
    </MainLayout>
  );
}

function WrongBookContent() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [questions, setQuestions] = useState<WrongQuestion[]>([]);
  const [subject, setSubject] = useState("all");
  const [tab, setTab] = useState("unmastered");
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");
  const [explaining, setExplaining] = useState<WrongQuestion | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const router = useRouter();

  const load = useCallback(async () => {
    const token = TokenManager.getAccessToken();
    if (!token || TokenManager.isTokenExpired(token)) { setAuthRequired(true); setLoading(false); return; }
    setAuthRequired(false);
    setLoading(true); setNotice("");
    try {
      const [nextStats, nextQuestions] = await Promise.all([
        apiClient.get<Stats>("/v1/wrong-book/stats"),
        apiClient.get<{ items: WrongQuestion[] }>(`/v1/wrong-book?is_mastered=${tab === "mastered"}${subject === "all" ? "" : `&subject=${encodeURIComponent(subject)}`}`),
      ]);
      setStats(nextStats); setQuestions(nextQuestions.items || []);
    } catch (error: unknown) { setNotice((error as { code?: number }).code === 401 ? "登录已失效，请重新登录。" : "错题本暂时无法加载，请稍后重试。"); }
    finally { setLoading(false); }
  }, [subject, tab]);

  useEffect(() => { void load(); }, [load]);
  async function master(questionId: string) { try { await apiClient.post(`/v1/wrong-book/${questionId}/master`, {}); await load(); } catch { setNotice("标记失败，请稍后重试。"); } }
  function practice() { router.push(`/wrong-book/practice${subject === "all" ? "" : `?subject=${encodeURIComponent(subject)}`}`); }

  if (authRequired) return <main className="mx-auto max-w-xl px-4 py-16 text-center"><BookOpenCheck className="mx-auto h-12 w-12 text-brand-blue" /><h1 className="mt-4 text-xl font-bold">登录后查看错题本</h1><p className="mt-2 text-sm text-gray-600">错题、掌握状态和复习记录只属于你的学习账户。</p><Button asChild className="mt-6"><Link href="/login">去登录</Link></Button></main>;

  return <main className="mx-auto max-w-5xl space-y-6 px-4 py-6 md:px-8" aria-label="错题本">
    <section className="rounded-2xl bg-gradient-to-r from-rose-500 to-orange-500 p-6 text-white shadow-sm"><div className="flex items-center gap-3"><BookOpenCheck className="h-8 w-8" /><div><h1 className="text-2xl font-bold">错题本</h1><p className="mt-1 text-sm text-white/90">回顾错因，逐步把薄弱点变成掌握点。</p></div></div></section>
    {stats && <section className="grid grid-cols-3 gap-3"><Stat label="待掌握" value={stats.unmastered} tone="rose" /><Stat label="已掌握" value={stats.mastered} tone="emerald" /><Stat label="近三日待复习" value={stats.need_review_today} tone="blue" /></section>}
    <Button className="w-full" onClick={() => void practice()}><RefreshCw className="mr-2 h-4 w-4" />错题重练</Button>
    {notice && <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">{notice}</p>}
    <div className="flex flex-wrap gap-2"><Badge className="cursor-pointer" variant={subject === "all" ? "default" : "outline"} onClick={() => setSubject("all")}>全部</Badge>{Object.entries(stats?.by_subject || {}).map(([name, count]) => <Badge key={name} className="cursor-pointer" variant={subject === name ? "default" : "outline"} onClick={() => setSubject(name)}>{name} ({count})</Badge>)}</div>
    <Tabs value={tab} onValueChange={setTab}><TabsList className="grid w-full grid-cols-2"><TabsTrigger value="unmastered">待掌握 {stats ? `(${stats.unmastered})` : ""}</TabsTrigger><TabsTrigger value="mastered">已掌握 {stats ? `(${stats.mastered})` : ""}</TabsTrigger></TabsList><TabsContent value={tab} className="space-y-3 pt-2">{loading ? <p className="py-10 text-center text-sm text-gray-500">正在加载错题…</p> : questions.length === 0 ? <Empty mastered={tab === "mastered"} /> : questions.map((question) => <article key={question.id} className="rounded-xl border bg-white p-4 shadow-sm"><div className="mb-2 flex items-center justify-between gap-3"><Badge variant="outline">{question.subject}</Badge><span className="text-xs text-rose-600">错 {question.wrong_count} 次</span></div><h2 className="font-medium leading-6 text-gray-900">{question.question_text}</h2>{question.knowledge_point && <p className="mt-2 text-xs text-gray-500">知识点：{question.knowledge_point}</p>}<div className="mt-4 flex gap-2"><Button variant="outline" className="flex-1" onClick={() => setExplaining(question)}><Lightbulb className="mr-1 h-4 w-4" />AI 讲解</Button>{!question.is_mastered && <Button className="flex-1" onClick={() => void master(question.question_id)}><CheckCircle2 className="mr-1 h-4 w-4" />标记掌握</Button>}</div></article>)}</TabsContent></Tabs>
    <Dialog open={Boolean(explaining)} onOpenChange={(open) => !open && setExplaining(null)}><DialogContent className="max-w-2xl p-0">{explaining && <TutorChat topic={explaining.subject} questionContext={{ id: explaining.question_id, question_text: explaining.question_text, knowledge_points: explaining.knowledge_point ? [explaining.knowledge_point] : [], difficulty: explaining.difficulty, subject: explaining.subject }} initialPrompt="我想复盘这道错题，请先引导我找到自己的思路问题。" />}</DialogContent></Dialog>
  </main>;
}

function Stat({ label, value, tone }: { label: string; value: number; tone: "rose" | "emerald" | "blue" }) { const color = { rose: "bg-rose-50 text-rose-700", emerald: "bg-emerald-50 text-emerald-700", blue: "bg-blue-50 text-blue-700" }[tone]; return <div className={`rounded-xl p-4 text-center ${color}`}><p className="text-2xl font-bold">{value}</p><p className="mt-1 text-xs">{label}</p></div>; }
function Empty({ mastered }: { mastered: boolean }) { return <div className="rounded-xl border border-dashed py-14 text-center"><CheckCircle2 className="mx-auto h-10 w-10 text-emerald-400" /><p className="mt-3 text-sm text-gray-600">{mastered ? "还没有已掌握的错题" : "太棒了，当前没有待掌握的错题！"}</p></div>; }
