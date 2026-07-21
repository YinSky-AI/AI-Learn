# 12 - 全局浮动AI辅导按钮

## 任务目标

在全站右下角加一个浮动的AI辅导按钮，用户在任何页面都可以随时打开AI老师提问。

点击后弹出聊天面板，支持：
- 随时提问（任何学科问题都可以问）
- 上下文感知（如果在学习页，自动带上当前题目信息）
- 多角色对话（用03号做好的多Agent辅导系统）

## 当前代码状态

### 多Agent辅导系统

已在 03-04 号提示词中做好了，API和UI组件都有。

### 全局布局

主布局在 `app/(main)/layout.tsx` 中。

## 需要做的改动

### Step 1：全局浮动按钮组件

新建 `components/ai/floating-ai-button.tsx`：

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { MessageCircle, X, Sparkles } from "lucide-react";
import { TutorChat } from "./tutor-chat";

interface Props {
  topic?: string;
  questionContext?: any;
}

export function FloatingAIButton({ topic, questionContext }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [hasNewMessage, setHasNewMessage] = useState(false);

  return (
    <>
      {/* 浮动按钮 */}
      <button
        onClick={() => setIsOpen(!isOpen(true))
        className={`fixed bottom-20 right-4 z-40 md:bottom-8 md:right-8 z-50 ${
          isOpen ? "hidden" : "flex"
        } items-center justify-center w-14 h-14 rounded-full bg-gradient-to-r from-blue-500 to-purple-500 text-white shadow-lg hover:shadow-xl transition-all hover:scale-105 active:scale-95`}
      >
        <div className="relative">
          <MessageCircle className="w-6 h-6" />
          {hasNewMessage && (
            <span className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full animate-pulse" />
          )}
        </div>
      </button>

      {/* 聊天面板 */}
      {isOpen && (
        <div className="fixed bottom-20 right-4 md:bottom-8 md:right-8 w-[calc(100%-2rem)] md:w-[380px h-[500px] z-50 shadow-2xl rounded-2xl overflow-hidden">
          <TutorChat
            topic={topic}
            questionContext={questionContext}
            onClose={() => setIsOpen(false)}
          />
        </div>
      )}
    </>
  );
}
```

### Step 2：在主布局中引入

修改 `app/(main)/layout.tsx`，在主布局中加入浮动按钮。

> 注意：浮动按钮是 client component，layout 是 server component，需要单独包一层。

### Step 3：上下文感知

在不同页面传入不同的 context：
- 学习页：传入当前题目信息
- 错题本页：传入当前学科
- 其他页面：不传，用户可以自由提问

### Step 4：快捷问题建议

聊天面板底部增加几个快捷问题按钮：
- "给我讲个知识点"
- "出一道题考考我"
- "这个难不难？"

用户点一下就能发送，不用打字。

## 文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `components/ai/floating-ai-button.tsx` | 全局浮动按钮 |
| 修改 | `app/(main)/layout.tsx` | 引入浮动按钮 |
| 修改 | `components/ai/tutor-chat.tsx` | 增加快捷问题 + 关闭按钮 |

## 验收标准

- [ ] 所有页面右下角都有浮动AI按钮
- [ ] 点击后展开聊天面板
- [ ] 可以正常对话
- 学习页打开时有题目上下文
- [ ] 可以最小化/关闭聊天面板
- [ ] 移动端也能正常显示

## 注意事项

1. **不要挡内容**：浮动按钮不要挡住重要的操作按钮
2. **可关闭**：用户关掉后就变成小按钮
3. **性能**：聊天组件懒加载，不要一开始就加载
4. **移动端适配**：手机上聊天面板占满宽度
5. **键盘弹出**：手机上输入时键盘弹出，输入框要跟着上移

## 依赖关系

- **前置依赖**：04号（辅导系统UI完成）
- **后续依赖**：无
