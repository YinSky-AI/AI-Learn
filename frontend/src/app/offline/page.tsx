import Link from "next/link";
import { CloudOff, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function OfflinePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center px-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50 text-blue-600"><CloudOff className="h-8 w-8" /></div>
      <h1 className="mt-6 text-xl font-semibold text-slate-900">网络连接断开</h1>
      <p className="mt-2 text-sm leading-6 text-slate-600">请检查网络后重试。已经缓存的学习内容仍可在恢复连接后继续使用。</p>
      <Button asChild className="mt-6 min-h-[44px]"><Link href="/home"><RefreshCw className="mr-2 h-4 w-4" />重新连接</Link></Button>
    </main>
  );
}
