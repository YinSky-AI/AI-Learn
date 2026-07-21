"use client";

import { useEffect, useState } from "react";
import { Download, X } from "lucide-react";
import { Button } from "@/components/ui/button";

type DeferredInstallPrompt = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

const DISMISSED_KEY = "pwa-install-dismissed";
const VISITS_KEY = "pwa-visit-count";

export function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<DeferredInstallPrompt | null>(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    const onBeforeInstallPrompt = (event: Event) => {
      event.preventDefault();
      const visits = Number(window.localStorage.getItem(VISITS_KEY) || "0") + 1;
      window.localStorage.setItem(VISITS_KEY, String(visits));
      setDeferredPrompt(event as DeferredInstallPrompt);
      setShow(visits >= 3 && !window.localStorage.getItem(DISMISSED_KEY));
    };

    window.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onBeforeInstallPrompt);
  }, []);

  const dismiss = () => {
    window.localStorage.setItem(DISMISSED_KEY, "true");
    setShow(false);
  };

  const install = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const choice = await deferredPrompt.userChoice;
    if (choice.outcome === "accepted") setShow(false);
    setDeferredPrompt(null);
  };

  if (!show) return null;

  return (
    <section className="fixed inset-x-4 bottom-20 z-50 rounded-2xl bg-white p-4 shadow-2xl ring-1 ring-slate-200 md:hidden" aria-label="安装应用提示">
      <div className="flex items-start gap-3">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-xl" aria-hidden="true">📚</div>
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold text-slate-900">添加到主屏幕</h2>
          <p className="mt-0.5 text-sm text-slate-600">像 App 一样使用，学习更方便。</p>
        </div>
        <button type="button" onClick={dismiss} className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-slate-500 active:bg-slate-100" aria-label="关闭安装提示">
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="mt-3 flex gap-2">
        <Button type="button" variant="outline" className="min-h-[44px] flex-1" onClick={dismiss}>稍后再说</Button>
        <Button type="button" className="min-h-[44px] flex-1" onClick={() => void install()}><Download className="mr-1 h-4 w-4" />立即添加</Button>
      </div>
    </section>
  );
}
