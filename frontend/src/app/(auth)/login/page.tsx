"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { GraduationCap, Eye, EyeOff, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth-store";

export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const isLoading = useAuthStore((s) => s.isLoading);
  const error = useAuthStore((s) => s.error);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // 空字段校验
    if (!username.trim() || !password.trim()) {
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
                  {error}
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
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={isLoading}
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
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={isLoading}
                    className="pr-10"
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
