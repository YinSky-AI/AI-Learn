"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  BookOpen,
  ChevronRight,
  Network,
  RotateCw,
  Sparkles,
  Target,
} from "lucide-react";
import { MainLayout } from "@/components/layout/main-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import type { KnowledgeGraphNode, KnowledgeGraphResponse } from "@/types/api";

const SUBJECTS = [
  { code: "math", name: "数学", tone: "bg-blue-600" },
  { code: "chinese", name: "语文", tone: "bg-pink-500" },
  { code: "english", name: "英语", tone: "bg-amber-500" },
] as const;

type SubjectCode = (typeof SUBJECTS)[number]["code"];

const MASTERY_LEGEND = [
  { label: "熟练（80%+）", dot: "bg-emerald-500" },
  { label: "掌握（60–79%）", dot: "bg-lime-400" },
  { label: "一般（40–59%）", dot: "bg-amber-400" },
  { label: "薄弱（20–39%）", dot: "bg-orange-400" },
  { label: "待加强（0–19%）", dot: "bg-rose-400" },
  { label: "未学习", dot: "bg-gray-300" },
] as const;

function masteryMeta(mastery: number | null) {
  if (mastery === null) return { label: "未学习", dot: "bg-gray-300", text: "text-gray-500", panel: "bg-gray-50" };
  if (mastery >= 0.8) return { label: "熟练", dot: "bg-emerald-500", text: "text-emerald-700", panel: "bg-emerald-50" };
  if (mastery >= 0.6) return { label: "掌握", dot: "bg-lime-400", text: "text-lime-700", panel: "bg-lime-50" };
  if (mastery >= 0.4) return { label: "一般", dot: "bg-amber-400", text: "text-amber-700", panel: "bg-amber-50" };
  if (mastery >= 0.2) return { label: "薄弱", dot: "bg-orange-400", text: "text-orange-700", panel: "bg-orange-50" };
  return { label: "待加强", dot: "bg-rose-400", text: "text-rose-700", panel: "bg-rose-50" };
}

function learningAdvice(mastery: number | null) {
  if (mastery === null) return "你还没有完成这个知识点的练习。先做一组基础题，图谱就会开始记录你的掌握度。";
  if (mastery >= 0.8) return "已经掌握得很扎实，可以尝试更有挑战性的题目，并用讲解检验理解。";
  if (mastery >= 0.6) return "整体掌握不错，建议练习一组变式题，巩固容易混淆的细节。";
  if (mastery >= 0.4) return "基础已经建立，建议再完成一组针对性练习并复盘错题。";
  return "这个知识点目前较薄弱，建议从基础例题开始，再逐步增加难度。";
}

export default function KnowledgeGraphPage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const [subject, setSubject] = useState<SubjectCode>("math");
  const [graph, setGraph] = useState<KnowledgeGraphResponse | null>(null);
  const [selectedNode, setSelectedNode] = useState<KnowledgeGraphNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    setSelectedNode(null);
    apiClient
      .get<KnowledgeGraphResponse>("/v1/knowledge-graph", { subject })
      .then((data) => {
        if (!active) return;
        setGraph(data);
        setSelectedNode(data.children?.[0] ?? data);
      })
      .catch(() => active && setError("知识图谱暂时无法加载，请稍后重试。"))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [isAuthenticated, reloadKey, subject]);

  if (!isAuthenticated) {
    return (
      <MainLayout>
        <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 text-center">
          <Network className="h-12 w-12 text-gray-300" />
          <div>
            <h1 className="font-semibold text-gray-800">登录后查看你的知识图谱</h1>
            <p className="mt-1 text-sm text-brand-gray">系统会根据答题记录呈现每个知识点的掌握度。</p>
          </div>
          <Button asChild><Link href="/login">去登录</Link></Button>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <main className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
              <Network className="h-7 w-7 text-brand-blue" />
              知识图谱
            </h1>
            <p className="mt-1 text-sm text-brand-gray">沿着知识脉络查看掌握程度，找到最值得练习的下一步。</p>
          </div>
          {graph && !loading && (
            <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-2 text-sm text-blue-700">
              已学习 <strong>{graph.learned_leaf_count}</strong> / {graph.total_leaf_count} 个知识点
            </div>
          )}
        </header>

        <div className="grid grid-cols-3 gap-2 rounded-2xl border border-gray-100 bg-white p-2 shadow-card" role="tablist" aria-label="选择学科">
          {SUBJECTS.map((item) => (
            <button
              key={item.code}
              type="button"
              role="tab"
              aria-selected={subject === item.code}
              onClick={() => setSubject(item.code)}
              className={cn(
                "min-h-[44px] rounded-xl px-3 text-sm font-medium transition-colors",
                subject === item.code ? `${item.tone} text-white shadow-sm` : "text-gray-600 hover:bg-gray-50",
              )}
            >
              {item.name}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex min-h-[360px] items-center justify-center rounded-2xl border border-gray-100 bg-white text-sm text-brand-gray">
            <RotateCw className="mr-2 h-4 w-4 animate-spin" />正在加载知识图谱…
          </div>
        ) : error || !graph ? (
          <div className="flex min-h-[360px] flex-col items-center justify-center gap-4 rounded-2xl border border-rose-100 bg-rose-50 text-center">
            <AlertCircle className="h-10 w-10 text-rose-400" />
            <p className="text-sm text-rose-700">{error || "暂无知识图谱"}</p>
            <Button variant="outline" onClick={() => setReloadKey((value) => value + 1)}>
              <RotateCw className="mr-2 h-4 w-4" />重新加载
            </Button>
          </div>
        ) : (
          <>
            {graph.learned_leaf_count === 0 && (
              <div className="flex items-start gap-3 rounded-xl border border-amber-100 bg-amber-50 p-4 text-sm text-amber-800">
                <Sparkles className="mt-0.5 h-5 w-5 shrink-0" />
                <p><strong>还没有学习数据。</strong> 图谱结构已为你准备好，完成练习后节点会按掌握度逐步点亮。</p>
              </div>
            )}

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
              <Card className="shadow-card">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg">{graph.name}知识体系</CardTitle>
                </CardHeader>
                <CardContent className="max-h-[620px] space-y-2 overflow-y-auto">
                  {graph.children?.map((node) => (
                    <KnowledgeTreeNode
                      key={node.id}
                      node={node}
                      selectedId={selectedNode?.id}
                      onSelect={setSelectedNode}
                    />
                  ))}
                </CardContent>
              </Card>

              <NodeDetails node={selectedNode} subject={subject} />
            </div>

            <section className="rounded-2xl border border-gray-100 bg-white p-4 shadow-card" aria-label="掌握度图例">
              <h2 className="mb-3 text-sm font-semibold text-gray-700">掌握度图例</h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {MASTERY_LEGEND.map((item) => (
                  <div key={item.label} className="flex items-center gap-2 text-xs text-gray-600">
                    <span className={cn("h-3 w-3 shrink-0 rounded-full", item.dot)} />
                    {item.label}
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </main>
    </MainLayout>
  );
}

function KnowledgeTreeNode({
  node,
  selectedId,
  onSelect,
  depth = 0,
}: {
  node: KnowledgeGraphNode;
  selectedId?: string;
  onSelect: (node: KnowledgeGraphNode) => void;
  depth?: number;
}) {
  const meta = masteryMeta(node.mastery);
  return (
    <div>
      <button
        type="button"
        onClick={() => onSelect(node)}
        className={cn(
          "flex min-h-[44px] w-full items-center gap-3 rounded-xl border px-3 py-2 text-left transition-colors",
          selectedId === node.id ? "border-blue-200 bg-blue-50 ring-2 ring-blue-100" : "border-transparent hover:bg-gray-50",
        )}
        style={{ paddingLeft: `${12 + Math.min(depth, 2) * 16}px` }}
      >
        <span className={cn("h-3 w-3 shrink-0 rounded-full ring-4 ring-white", meta.dot)} />
        <span className="min-w-0 flex-1">
          <span className={cn("block truncate text-sm", node.is_leaf ? "font-medium text-gray-700" : "font-semibold text-gray-900")}>{node.name}</span>
          {node.description && !node.is_leaf && <span className="mt-0.5 block truncate text-xs text-brand-gray">{node.description}</span>}
        </span>
        <span className={cn("shrink-0 text-xs font-medium", meta.text)}>{node.mastery_percent === null ? "—" : `${node.mastery_percent}%`}</span>
        {!node.is_leaf && <ChevronRight className="h-4 w-4 shrink-0 text-gray-300" />}
      </button>
      {node.children && (
        <div className="ml-4 border-l border-gray-100 pl-1">
          {node.children.map((child) => (
            <KnowledgeTreeNode key={child.id} node={child} selectedId={selectedId} onSelect={onSelect} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

function NodeDetails({ node, subject }: { node: KnowledgeGraphNode | null; subject: SubjectCode }) {
  if (!node) {
    return (
      <Card className="shadow-card"><CardContent className="flex min-h-[260px] flex-col items-center justify-center text-center text-sm text-brand-gray"><Network className="mb-3 h-10 w-10 text-gray-200" />选择左侧节点查看知识点详情</CardContent></Card>
    );
  }
  const meta = masteryMeta(node.mastery);
  const practiceHref = `/knowledge-practice?${new URLSearchParams({
    node_id: node.id,
    name: node.name,
    subject,
  }).toString()}`;
  return (
    <Card className="h-fit shadow-card lg:sticky lg:top-6">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg">知识点详情</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div>
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-xl font-bold text-gray-900">{node.name}</h2>
            <span className={cn("rounded-full px-2.5 py-1 text-xs font-semibold", meta.panel, meta.text)}>{meta.label}</span>
          </div>
          {node.description && <p className="mt-2 text-sm leading-6 text-brand-gray">{node.description}</p>}
        </div>

        <div className={cn("rounded-xl p-4", meta.panel)}>
          <div className="flex items-center justify-between text-sm">
            <span className={cn("font-medium", meta.text)}>当前掌握度</span>
            <strong className={cn("text-xl", meta.text)}>{node.mastery_percent === null ? "未学习" : `${node.mastery_percent}%`}</strong>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/80">
            <div className={cn("h-full rounded-full transition-all", meta.dot)} style={{ width: `${node.mastery_percent ?? 0}%` }} />
          </div>
        </div>

        {node.is_leaf ? (
          <>
            <div className="rounded-xl border border-blue-100 bg-blue-50 p-4">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-blue-800"><Target className="h-4 w-4" />学习建议</h3>
              <p className="mt-2 text-sm leading-6 text-blue-700">{learningAdvice(node.mastery)}</p>
            </div>
            <Button asChild className="min-h-[44px] w-full">
              <Link href={practiceHref}><BookOpen className="mr-2 h-4 w-4" />练习这个知识点</Link>
            </Button>
          </>
        ) : (
          <div>
            <h3 className="mb-2 text-sm font-semibold text-gray-700">包含知识点</h3>
            <div className="flex flex-wrap gap-2">
              {node.children?.map((child) => {
                const childMeta = masteryMeta(child.mastery);
                return (
                  <button key={child.id} type="button" className={cn("min-h-[44px] rounded-xl px-3 py-2 text-xs font-medium", childMeta.panel, childMeta.text)}>
                    {child.name} {child.mastery_percent === null ? "" : `${child.mastery_percent}%`}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
