/**
 * 登录页面
 *
 * 功能说明：
 * - 提供用户登录表单，包含用户名、密码输入
 * - 支持密码显示/隐藏切换
 * - 表单校验（非空校验）
 * - 登录成功后自动跳转到首页
 * - 使用 auth-store 进行认证状态管理
 */

"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { GraduationCap, Eye, EyeOff, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth-store";

/**
 * 将 error 转换为用户友好的提示文字
 * @param error - 未知类型的错误对象
 * @returns 用户友好的错误提示字符串
 */
function getErrorMessage(error: unknown): string {
  if (typeof error === "string") return error;
  if (error && typeof error === "object") {
    if ("message" in error && typeof (error as Record<string, unknown>).message === "string") {
      return (error as { message: string }).message;
    }
  }
  return "登录失败，请检查用户名和密码";
}

/**
 * 登录页面组件
 * @returns 登录表单页面
 */
export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const isLoading = useAuthStore((s) => s.isLoading);
  const error = useAuthStore((s) => s.error);

  // 表单状态
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [success, setSuccess] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({ username: false, password: false });

  /**
   * 处理表单提交
   * @param e - 表单提交事件
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // 校验非空
    const hasEmptyUsername = !username.trim();
    const hasEmptyPassword = !password.trim();
    setFieldErrors({ username: hasEmptyUsername, password: hasEmptyPassword });
    // 空字段校验：任一字段为空则提示错误
    if (hasEmptyUsername || hasEmptyPassword) {
      useAuthStore.setState({ error: "请输入用户名和密码" });
      return;
    }
    try {
      await login({ username, password });
      setSuccess(true);
      // 延迟跳转，让用户看到成功提示
      setTimeout(() => {
        router.push("/home");
      }, 1000);
    } catch {
      // 错误已在 store 中处理
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-blue">
            <GraduationCap className="h-8 w-8 text-white" />
          </div>
          <h1 className="mt-4 text-2xl font-bold text-gray-900">AI学堂</h1>
          <p className="mt-1 text-sm text-brand-gray">智能学习平台</p>
        </div>

        {/* 登录卡片 */}
        <Card className="shadow-card">
          <CardHeader className="text-center">
            <CardTitle className="text-xl">欢迎回来</CardTitle>
            <CardDescription>请输入你的账号和密码登录</CardDescription>
          </CardHeader>

          <form onSubmit={handleSubmit}>
            <CardContent className="space-y-4">
              {/* 错误提示 */}
              {error && (
                <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-brand-red">
                  {getErrorMessage(error)}
                </div>
              )}

              {/* 成功提示 */}
              {success && (
                <div className="rounded-lg bg-green-50 px-3 py-2 text-sm text-green-600">
                  登录成功，正在跳转...
                </div>
              )}

              {/* 用户名 */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">用户名</label>
                <Input
                  placeholder="请输入用户名"
                  value={username}
                  onChange={(e) => { setUsername(e.target.value); if (fieldErrors.username) setFieldErrors(prev => ({ ...prev, username: false })); }}
                  disabled={isLoading}
                  className={fieldErrors.username ? "border-red-500 focus-visible:ring-red-500" : ""}
                />
              </div>

              {/* 密码 */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">密码</label>
                <div className="relative">
                  <Input
                    type={showPassword ? "text" : "password"}
                    placeholder="请输入密码"
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); if (fieldErrors.password) setFieldErrors(prev => ({ ...prev, password: false })); }}
                    disabled={isLoading}
                    className={fieldErrors.password ? "border-red-500 focus-visible:ring-red-500 pr-10" : "pr-10"}
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-brand-gray hover:text-gray-700"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
            </CardContent>

            <CardFooter className="flex flex-col gap-4">
              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                登录
              </Button>

              <div className="text-center text-sm text-brand-gray">
                还没有账号？
                <Link href="/register" className="ml-1 font-medium text-brand-blue hover:underline">
                  立即注册
                </Link>
              </div>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  );
}
