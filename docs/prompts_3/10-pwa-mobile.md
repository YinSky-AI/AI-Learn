# 10 - PWA移动端适配

## 任务目标

把网站变成PWA（渐进式Web应用），让用户可以：
- 在手机上"添加到主屏幕"，像App一样打开
- 离线能打开（至少能看缓存的内容
- 有推送通知（学习提醒）
- 触摸友好的交互（按钮够大、操作顺手）

这是一个"花时间不多但体验提升很大的功能，面试也能讲。

## 当前代码状态

### 前端技术栈

Next.js + TypeScript + Tailwind CSS。
Next.js 自带 PWA 支持，加个 manifest 和 service worker 就行。

### 移动端适配

目前应该有响应式，但可能没有针对移动端优化。

## 需要做的改动

### Step 1：添加 PWA Manifest

在 `public/` 目录下新建 `manifest.json`：

```json
{
  "name": "AI学习助手",
  "short_name": "AI学习",
  "description": "AI驱动的个性化学习平台",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#3b82f6",
  "orientation": "portrait",
  "icons": [
    {
      "src": "/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-512-maskable.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "maskable"
    }
  ],
  "categories": ["education", "productivity"],
  "lang": "zh-CN"
}
```

### Step 2：生成 App 图标

用简单的 SVG 生成几个尺寸的图标（或者用在线工具生成）。至少需要：
- 192x192
- 512x512
- 512x512 maskable

放在 `public/icons/` 目录下。

### Step 3：配置 Next.js PWA

安装 `next-pwa` 或用 Next.js 14+ 自带的 PWA 支持。

如果用 next-pwa：

```bash
npm install next-pwa
```

修改 `next.config.js`：

```js
const withPWA = require('next-pwa')({
  dest: 'public',
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  // ... 其他配置
};

module.exports = withPWA(nextConfig);
```

> 如果 Next.js 版本比较新，可能有更简单的方式。按项目实际的 Next.js 版本来。

### Step 4：在 layout 中引入 manifest

修改 `app/layout.tsx`：

```tsx
import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  // ...
  manifest: "/manifest.json",
  // 苹果相关
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "AI学习助手",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "white" },
    { media: "(prefers-color-scheme: dark)", color: "black" },
  ],
};
```

### Step 5：移动端UI优化

#### 5.1 底部导航栏（移动端）

新建 `components/layout/mobile-bottom-nav.tsx`：

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, BookOpen, BarChart3, User, MessageCircle } from "lucide-react";

const navItems = [
  { href: "/", label: "首页", icon: Home },
  { href: "/courses", label: "课程", icon: BookOpen },
  { href: "/wrong-book", label: "错题", icon: BookOpen },
  { href: "/report", label: "报告", icon: BarChart3 },
  { href: "/profile", label: "我的", icon: User },
];

export function MobileBottomNav() {
  const pathname = usePathname();

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-40 md:hidden">
      <div className="flex justify-around items-center h-16">
        {navItems.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          const Icon = item.icon;
          
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center justify-center flex-1 h-full transition-colors ${
                isActive ? "text-blue-600" : "text-gray-500"
              }`}
            >
              <Icon className="w-5 h-5 mb-0.5" />
              <span className="text-[10px]">{item.label}</span>
            </Link>
          );
        })}
      </div>
      {/* iOS安全区域
      <div className="h-[env(safe-area-inset-bottom)]" />
    </div>
  );
}
```

在主 layout 中加入底部导航（只在移动端显示）。

#### 5.2 答题页移动端优化

学习页在手机上的优化：
- 选项按钮高度 >= 44px（手指点击区域够大）
- 顶部进度条更粗一些
- 字体适当调大
- 增加触摸反馈（按下效果）

#### 5.3 增加安装提示

加一个"添加到主屏幕的提示组件：

```tsx
// components/pwa/install-prompt.tsx
"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { X, Download } from "lucide-react";

export function InstallPrompt() {
  const [show, setShow] = useState(false);
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
      // 只在用户访问3次后显示，不要太频繁
      const visitCount = Number(localStorage.getItem("visit_count") || "0") + 1;
      localStorage.setItem("visit_count", String(visitCount));
      if (visitCount >= 3 && !localStorage.getItem("install_dismissed")) {
        setShow(true);
      }
    };

    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") {
      setShow(false);
    }
    setDeferredPrompt(null);
  };

  const handleDismiss = () => {
    setShow(false);
    localStorage.setItem("install_dismissed", "true");
  };

  if (!show) return null;

  return (
    <div className="fixed bottom-20 left-4 right-4 bg-white rounded-2xl shadow-2xl p-4 z-50 md:hidden">
      <div className="flex items-start gap-3">
      <div className="w-12 h-12 bg-blue-500 rounded-xl flex items-center justify-center text-white text-2xl">
        📱
      </div>
      <div className="flex-1">
        <h3 className="font-semibold">添加到主屏幕</h3>
        <p className="text-sm text-gray-600">
          像App一样使用，学习更方便
        </p>
      </div>
      <button
        onClick={handleDismiss}
        className="text-gray-400 hover:text-gray-600"
      >
        <X className="w-5 h-5" />
      </button>
    </div>
    <div className="flex gap-2 mt-3">
      <Button variant="outline" size="sm" className="flex-1" onClick={handleDismiss}>
        稍后再说
      </Button>
      <Button size="sm" className="flex-1" onClick={handleInstall}>
        <Download className="w-4 h-4 mr-1" />
        立即添加
      </Button>
    </div>
    </div>
  );
}
```

### Step 6：推送通知（可选）

加一个简单的学习提醒推送：
- 用户设置每天的学习提醒时间
- 到点了发推送通知

这个需要后端配合，用 Web Push API。如果时间紧可以先不做，PWA的核心价值是"添加到主屏幕"。

### Step 7：离线页面

加一个简单的离线降级页面，没网的时候显示：
- "网络连接断开"
- 已缓存的内容还能看（题目列表、个人中心等）

## 文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `public/manifest.json` | PWA manifest |
| 新建 | `public/icons/` | App图标 |
| 修改 | `next.config.js` | 或 `next.config.mjs` | 配置PWA |
| 修改 | `app/layout.tsx` | 引入manifest + viewport |
| 新建 | `components/layout/mobile-bottom-nav.tsx` | 移动端底部导航 |
| 新建 | `components/pwa/install-prompt.tsx` | 安装提示 |
| 修改 | 各页面 | 移动端适配优化 |

## 验收标准

- [ ] 手机浏览器打开后能"添加到主屏幕"
- [ ] 添加后有独立的图标和启动画面
- [ ] 打开后全屏显示，没有浏览器地址栏
- [ ] 移动端有底部导航栏
- [ ] 按钮和可点击区域够大（>= 44px）
- [ ] 文字大小适合手机阅读
- [ ] 断网时不会全白，有离线提示

## 注意事项

1. **图标很重要**：图标一定要做，没有图标用户不想加到主屏幕
2. **不要强制安装**：安装提示要节制，用户拒绝后不要再弹
3. **iOS Safari**：iOS 上 PWA 支持有限，但基本功能能用
4. **Service Worker 缓存策略**：不要缓存太激进，不然更新不了
5. **开发模式禁用**：开发环境关掉 PWA，不然影响开发体验
6. **触摸反馈**：按钮按下要有视觉反馈（颜色变深/变小）

## 依赖关系

- **前置依赖**：核心功能（答题、错题本等）基本完成
- **后续依赖**：无
