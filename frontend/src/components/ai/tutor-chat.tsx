"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import apiClient from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { ChatRequest, ChatResponse, TutorQuestionContext } from "@/types/api";
import { getTutorRoleMeta, TUTOR_UNAVAILABLE_MESSAGE, type TutorRole } from "./tutor-presentation";

export type { TutorQuestionContext } from "@/types/api";
interface ChatMessage { id: string; role: TutorRole; name?: string; content: string; }

interface TutorChatProps {
  questionContext?: TutorQuestionContext;
  isCorrect?: boolean;
  userAnswer?: string;
  topic?: string;
  initialPrompt?: string;
  courseId?: string;
  lessonId?: string;
  quickPrompts?: readonly string[];
  onQuickPrompt?: (prompt: string) => boolean | void;
  showHeader?: boolean;
  className?: string;
}

export function TutorChat({
  questionContext,
  isCorrect,
  userAnswer,
  topic,
  initialPrompt,
  courseId,
  lessonId,
  quickPrompts = [],
  onQuickPrompt,
  showHeader = true,
  className,
}: TutorChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const hasSentInitial = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, isLoading]);

  async function sendMessage(rawText: string) {
    const text = rawText.trim();
    if (!text || isLoading) return;
    const userMessage: ChatMessage = { id: `${Date.now()}-student`, role: "student", content: text };
    const history: NonNullable<ChatRequest["conversationHistory"]> = messages.slice(-10).map((message) => ({
      role: message.role === "student" ? "user" : "assistant",
      content: message.content,
    }));
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setError("");
    setIsLoading(true);
    try {
      const request: ChatRequest = {
        message: text,
        context: { courseId, lessonId, question: questionContext, is_correct: isCorrect, student_answer: userAnswer, subject: topic || questionContext?.subject },
        conversationHistory: history,
      };
      const result = await apiClient.post<ChatResponse>("/v1/ai/chat", request);
      const tutorMessages = result.messages.map((message, index): ChatMessage => ({ id: `${Date.now()}-${index}-${message.role}`, role: message.role, name: message.name, content: message.content }));
      if (result.suggested_next_step) tutorMessages.push({ id: `${Date.now()}-next`, role: "assistant", name: "下一步", content: result.suggested_next_step });
      setMessages((current) => [...current, ...tutorMessages]);
    } catch {
      setError(TUTOR_UNAVAILABLE_MESSAGE);
    } finally { setIsLoading(false); }
  }

  useEffect(() => {
    if (initialPrompt && !hasSentInitial.current) { hasSentInitial.current = true; void sendMessage(initialPrompt); }
  // initialPrompt intentionally initiates exactly once when dialog opens.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPrompt]);

  function onSubmit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); void sendMessage(input); }

  return (
    <section className={cn("flex h-[min(70vh,560px)] flex-col overflow-hidden rounded-xl border bg-white", className)} aria-label="多角色 AI 辅导对话">
      {showHeader && <header className="bg-gradient-to-r from-blue-600 to-violet-600 p-4 text-white"><h2 className="font-semibold">AI 辅导老师</h2><p className="mt-1 text-sm text-white/85">老师、助教、诊断师和鼓励师会一起陪你梳理思路。</p></header>}
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {!messages.length && !isLoading && <div className="py-10 text-center text-sm text-gray-500"><Sparkles className="mx-auto mb-2 h-8 w-8 text-violet-500" />说说你卡在哪一步，我来陪你想。</div>}
        {messages.map((message) => {
          const meta = getTutorRoleMeta(message.role, message.name);
          const student = message.role === "student";
          return <div key={message.id} className={cn("flex gap-2", student && "justify-end")}>
            {!student && <span className="mt-1 text-lg" aria-hidden>{meta.emoji}</span>}
            <div className={cn("max-w-[88%] rounded-xl border px-3 py-2 text-sm leading-6", meta.className)}><p className="mb-1 text-xs font-semibold">{meta.name}</p><p className="whitespace-pre-wrap">{message.content}</p></div>
          </div>;
        })}
        {isLoading && <p className="text-sm text-gray-500">AI 辅导老师正在思考…</p>}
        {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
        <div ref={bottomRef} />
      </div>
      {quickPrompts.length > 0 && (
        <div className="flex shrink-0 gap-2 overflow-x-auto border-t px-3 py-2" aria-label="快捷问题">
          {quickPrompts.map((prompt) => (
            <Button
              key={prompt}
              type="button"
              variant="outline"
              size="sm"
              className="min-h-9 shrink-0 rounded-full text-xs"
              disabled={isLoading}
              onClick={() => {
                if (onQuickPrompt?.(prompt)) return;
                void sendMessage(prompt);
              }}
            >
              {prompt}
            </Button>
          ))}
        </div>
      )}
      <form onSubmit={onSubmit} className="flex gap-2 border-t p-3"><Input value={input} onChange={(event) => setInput(event.target.value)} disabled={isLoading} placeholder="输入你的思路或问题…" aria-label="输入给 AI 辅导老师的消息" /><Button type="submit" size="icon" disabled={isLoading || !input.trim()} aria-label="发送消息"><Send className="h-4 w-4" /></Button></form>
    </section>
  );
}
