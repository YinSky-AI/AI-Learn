/**
 * Markdown 渲染组件
 *
 * 功能说明：
 * - 渲染 Markdown 格式内容（用于 AI 回复、课程内容等）
 * - 支持 GitHub Flavored Markdown（GFM）
 * - 代码块语法高亮（highlight.js）
 * - 自定义段落、标题、列表、代码、引用块、表格、链接等样式
 * - 动态加载 highlight.js 主题 CSS
 */

"use client";

import React, { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { cn } from "@/lib/utils";

/** Markdown 渲染器属性 */
interface MarkdownRendererProps {
  content: string;
  className?: string;
}

/**
 * Markdown 渲染组件
 * @param content - Markdown 内容字符串
 * @param className - 额外类名
 * @returns 渲染后的 HTML 内容
 */
export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  const [cssLoaded, setCssLoaded] = useState(false);

  // 动态加载 highlight.js 主题 CSS（避免 SSR 问题）
  useEffect(() => {
    if (document.querySelector('link[data-hljs-theme]')) {
      setCssLoaded(true);
      return;
    }
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css";
    link.setAttribute("data-hljs-theme", "true");
    link.onload = () => setCssLoaded(true);
    document.head.appendChild(link);
  }, []);

  return (
    <div className={cn("markdown-body", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          // 自定义段落样式
          p: ({ children, ...props }) => (
            <p
              className="mb-2 last:mb-0 leading-relaxed"
              {...props}
            >
              {children}
            </p>
          ),
          // 标题样式
          h1: ({ children, ...props }) => (
            <h1 className="mb-2 mt-3 text-lg font-bold" {...props}>{children}</h1>
          ),
          h2: ({ children, ...props }) => (
            <h2 className="mb-1.5 mt-2.5 text-base font-bold" {...props}>{children}</h2>
          ),
          h3: ({ children, ...props }) => (
            <h3 className="mb-1 mt-2 text-sm font-semibold" {...props}>{children}</h3>
          ),
          h4: ({ children, ...props }) => (
            <h4 className="mb-1 mt-1.5 text-sm font-medium" {...props}>{children}</h4>
          ),
          // 列表样式
          ul: ({ children, ...props }) => (
            <ul className="mb-2 ml-4 list-disc space-y-0.5" {...props}>{children}</ul>
          ),
          ol: ({ children, ...props }) => (
            <ol className="mb-2 ml-4 list-decimal space-y-0.5" {...props}>{children}</ol>
          ),
          li: ({ children, ...props }) => (
            <li className="leading-relaxed" {...props}>{children}</li>
          ),
          // 代码块
          code: ({ className: codeClassName, children, ...props }) => {
            const isInline = !codeClassName;
            if (isInline) {
              return (
                <code
                  className="rounded bg-gray-200 px-1 py-0.5 text-xs font-mono text-gray-800"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return (
              <code className={cn("text-xs font-mono", codeClassName)} {...props}>
                {children}
              </code>
            );
          },
          pre: ({ children, ...props }) => (
            <pre
              className="mb-2 overflow-x-auto rounded-lg bg-gray-900 p-3 text-xs text-gray-100"
              {...props}
            >
              {children}
            </pre>
          ),
          // 引用块
          blockquote: ({ children, ...props }) => (
            <blockquote
              className="mb-2 border-l-3 border-purple-400 bg-purple-50 py-1.5 pl-3 text-sm italic text-gray-700"
              {...props}
            >
              {children}
            </blockquote>
          ),
          // 表格
          table: ({ children, ...props }) => (
            <div className="mb-2 overflow-x-auto">
              <table className="w-full border-collapse border border-gray-200 text-sm" {...props}>
                {children}
              </table>
            </div>
          ),
          th: ({ children, ...props }) => (
            <th
              className="border border-gray-200 bg-gray-100 px-2 py-1 text-left font-semibold"
              {...props}
            >
              {children}
            </th>
          ),
          td: ({ children, ...props }) => (
            <td className="border border-gray-200 px-2 py-1" {...props}>
              {children}
            </td>
          ),
          // 分隔线
          hr: ({ ...props }) => (
            <hr className="my-2 border-gray-200" {...props} />
          ),
          // 粗体
          strong: ({ children, ...props }) => (
            <strong className="font-semibold text-gray-900" {...props}>{children}</strong>
          ),
          // 链接
          a: ({ href, children, ...props }) => (
            <a
              href={href}
              className="text-blue-500 underline hover:text-blue-600"
              target="_blank"
              rel="noopener noreferrer"
              {...props}
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
