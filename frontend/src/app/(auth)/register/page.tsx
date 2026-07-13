"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { GraduationCap, Eye, EyeOff, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth-store";
import { AGE_GROUP_LIST } from "@/lib/content";

export default function RegisterPage() {
  const router = useRouter();
  const register = useAuthStore((s) => s.register);
  const isLoading = useAuthStore((s) => s.isLoading);
  const error = useAuthStore((s) => s.error);

  const [formData, setFormData] = useState({
    username: "",
    password: "",
    confirmPassword: "",
    email: "",
    nickname: "",
    age: "10",
    gender: "male" as "male" | "female" | "other",
  });
  const [showPassword, setShowPassword] = useState(false);

  const updateForm = (key: string, value: string) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
  };

  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    useAuthStore.getState().clearError();

    if (formData.password !== formData.confirmPassword) {
      setLocalError("两次输入的密码不一致");
      return;
    }
    if (formData.password.length < 6) {
      setLocalError("密码长度至少为6位");
      return;
    }

    try {
      await register({
        username: formData.username,
        password: formData.password,
        email: formData.email || formData.username,
        nickname: formData.nickname,
        age: parseInt(formData.age),
        gender: formData.gender,
      });
      router.push("/home");
    } catch {
      // 错误已在 store 中处理
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-8">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-blue">
            <GraduationCap className="h-8 w-8 text-white" />
          </div>
          <h1 className="mt-4 text-2xl font-bold text-gray-900">AI学堂</h1>
          <p className="mt-1 text-sm text-brand-gray">创建你的学习账号</p>
        </div>

        {/* 注册卡片 */}
        <Card className="shadow-card">
          <CardHeader className="text-center">
            <CardTitle className="text-xl">注册新账号</CardTitle>
            <CardDescription>填写以下信息开始你的学习之旅</CardDescription>
          </CardHeader>

          <form onSubmit={handleSubmit}>
            <CardContent className="space-y-4">
              {/* 错误提示 */}
              {(localError || error) && (
                <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-brand-red">
                  {localError || error}
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                {/* 用户名 */}
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-gray-700">用户名</label>
                  <Input
                    placeholder="用户名"
                    value={formData.username}
                    onChange={(e) => updateForm("username", e.target.value)}
                    required
                    disabled={isLoading}
                  />
                </div>

                {/* 昵称 */}
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-gray-700">昵称</label>
                  <Input
                    placeholder="显示昵称"
                    value={formData.nickname}
                    onChange={(e) => updateForm("nickname", e.target.value)}
                    required
                    disabled={isLoading}
                  />
                </div>
              </div>

              {/* 邮箱 */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">邮箱</label>
                <Input
                  type="email"
                  placeholder="your@email.com"
                  value={formData.email}
                  onChange={(e) => updateForm("email", e.target.value)}
                  required
                  disabled={isLoading}
                />
              </div>

              {/* 密码 */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">密码</label>
                <div className="relative">
                  <Input
                    type={showPassword ? "text" : "password"}
                    placeholder="至少6位密码"
                    value={formData.password}
                    onChange={(e) => updateForm("password", e.target.value)}
                    required
                    minLength={6}
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

              {/* 确认密码 */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">确认密码</label>
                <Input
                  type="password"
                  placeholder="再次输入密码"
                  value={formData.confirmPassword}
                  onChange={(e) => updateForm("confirmPassword", e.target.value)}
                  required
                  disabled={isLoading}
                />
                {formData.confirmPassword && formData.password !== formData.confirmPassword && (
                  <p className="text-xs text-brand-red">两次密码输入不一致</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                {/* 年龄 */}
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-gray-700">年龄</label>
                  <Select value={formData.age} onValueChange={(v) => updateForm("age", v)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 13 }, (_, i) => i + 6).map((age) => (
                        <SelectItem key={age} value={String(age)}>
                          {age}岁
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* 性别 */}
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-gray-700">性别</label>
                  <Select value={formData.gender} onValueChange={(v) => updateForm("gender", v)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="male">男</SelectItem>
                      <SelectItem value="female">女</SelectItem>
                      <SelectItem value="other">保密</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>

            <CardFooter className="flex flex-col gap-4">
              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                注册
              </Button>

              <div className="text-center text-sm text-brand-gray">
                已有账号？
                <Link href="/login" className="ml-1 font-medium text-brand-blue hover:underline">
                  去登录
                </Link>
              </div>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  );
}
