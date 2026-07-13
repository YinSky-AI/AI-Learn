"use client";

import React from "react";
import Link from "next/link";
import { MainLayout } from "@/components/layout/main-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { ProgressRing } from "@/components/common/progress-ring";
import { useAuthStore } from "@/stores/auth-store";
import {
  Settings,
  Edit3,
  Flame,
  Trophy,
  Star,
  BookOpen,
  Code2,
  Palette,
  Calculator,
  FlaskConical,
  Languages,
  Landmark,
  ChevronRight,
  Award,
  Lock,
  TrendingUp,
  Calendar,
  Zap,
  Shield,
  Bell,
  Moon,
} from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export default function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  // 未登录引导
  if (!isAuthenticated) {
    return (
      <MainLayout>
        <div className="flex min-h-[60vh] flex-col items-center justify-center">
          <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-gray-100">
            <Lock className="h-10 w-10 text-brand-gray" />
          </div>
          <h2 className="mt-6 text-xl font-bold text-gray-900">请先登录</h2>
          <p className="mt-2 text-sm text-brand-gray">登录后即可查看个人资料、学习进度和成就</p>
          <Link href="/login" className="mt-6">
            <Button>
              <Lock className="mr-2 h-4 w-4" />
              去登录
            </Button>
          </Link>
        </div>
      </MainLayout>
    );
  }

  // Mock 数据
  const mockProfile = {
    nickname: user?.nickname || "同学",
    bio: user?.bio || "热爱学习，喜欢探索新知识",
    level: 8,
    xp: 1280,
    maxXp: 2000,
    streak: {
      current: 7,
      longest: 15,
    },
    weeklyGoal: { target: 300, current: 180 },
    skills: [
      { name: "数学思维", subject: "math", level: 5, progress: 72, icon: Calculator },
      { name: "编程基础", subject: "programming", level: 3, progress: 45, icon: Code2 },
      { name: "英语阅读", subject: "english", level: 4, progress: 58, icon: Languages },
      { name: "科学探索", subject: "science", level: 3, progress: 35, icon: FlaskConical },
      { name: "语文写作", subject: "chinese", level: 6, progress: 80, icon: BookOpen },
      { name: "艺术创意", subject: "art", level: 2, progress: 25, icon: Palette },
    ],
    badges: [
      { name: "学习新星", color: "bg-amber-100 text-amber-600", unlocked: true },
      { name: "连续7天", color: "bg-orange-100 text-orange-600", unlocked: true },
      { name: "数学达人", color: "bg-blue-100 text-blue-600", unlocked: true },
      { name: "编程入门", color: "bg-indigo-100 text-indigo-600", unlocked: true },
      { name: "知识渊博", color: "bg-green-100 text-green-600", unlocked: false },
      { name: "学习大师", color: "bg-purple-100 text-purple-600", unlocked: false },
    ],
  };

  const xpProgress = Math.round((mockProfile.xp / mockProfile.maxXp) * 100);
  const weeklyProgress = Math.round(
    (mockProfile.weeklyGoal.current / mockProfile.weeklyGoal.target) * 100,
  );

  const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.08 } },
  };

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 },
  };

  return (
    <MainLayout>
      <motion.div variants={container} initial="hidden" animate="show" className="space-y-6">
        {/* 个人信息卡片 */}
        <motion.div variants={item}>
          <Card className="shadow-card">
            <CardContent className="p-6">
              <div className="flex flex-col items-start gap-6 sm:flex-row sm:items-center">
                {/* 头像 */}
                <div className="relative">
                  <Avatar className="h-20 w-20">
                    <AvatarImage src={user?.avatar || "/avatars/default.svg"} />
                    <AvatarFallback className="bg-brand-blue text-2xl text-white">
                      {mockProfile.nickname.charAt(0)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="absolute -bottom-1 -right-1 rounded-full bg-brand-blue p-1">
                    <Edit3 className="h-3 w-3 text-white" />
                  </div>
                </div>

                {/* 基本信息 */}
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h1 className="text-xl font-bold text-gray-900">{mockProfile.nickname}</h1>
                    <Badge className="bg-brand-blue text-white">Lv.{mockProfile.level}</Badge>
                  </div>
                  <p className="mt-1 text-sm text-brand-gray">{mockProfile.bio}</p>

                  {/* 经验值进度 */}
                  <div className="mt-3 flex items-center gap-3">
                    <div className="flex-1">
                      <div className="mb-1 flex justify-between text-xs">
                        <span className="text-brand-gray">经验值</span>
                        <span className="font-medium text-gray-700">
                          {mockProfile.xp} / {mockProfile.maxXp}
                        </span>
                      </div>
                      <Progress value={xpProgress} className="h-2" />
                    </div>
                    <Button variant="outline" size="sm">
                      <Edit3 className="mr-1 h-3 w-3" />
                      编辑资料
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* 连胜 + 周目标 + 统计 */}
        <motion.div variants={item} className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {/* 连续学习 */}
          <Card className="shadow-card">
            <CardContent className="flex items-center gap-4 p-5">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-orange-50">
                <Flame className="h-6 w-6 text-brand-orange" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{mockProfile.streak.current}天</p>
                <p className="text-xs text-brand-gray">
                  连续学习（最长{mockProfile.streak.longest}天）
                </p>
              </div>
            </CardContent>
          </Card>

          {/* 周目标 */}
          <Card className="shadow-card">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <p className="text-sm text-brand-gray">本周目标</p>
                <span className="text-sm font-medium text-brand-blue">
                  {mockProfile.weeklyGoal.current}/{mockProfile.weeklyGoal.target} 分钟
                </span>
              </div>
              <Progress value={weeklyProgress} className="mt-3 h-2" />
              <p className="mt-2 text-xs text-brand-gray">
                还差 {mockProfile.weeklyGoal.target - mockProfile.weeklyGoal.current} 分钟
              </p>
            </CardContent>
          </Card>

          {/* 总经验 */}
          <Card className="shadow-card">
            <CardContent className="flex items-center gap-4 p-5">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-purple-50">
                <Zap className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">1,280</p>
                <p className="text-xs text-brand-gray">累计经验值</p>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Tabs：技能 + 徽章 + 设置 */}
        <motion.div variants={item}>
          <Card className="shadow-card">
            <CardContent className="p-0">
              <Tabs defaultValue="skills" className="w-full">
                <TabsList className="w-full justify-start rounded-none border-b border-gray-100 bg-transparent p-0">
                  <TabsTrigger
                    value="skills"
                    className="rounded-none border-b-2 border-transparent px-6 py-3 data-[state=active]:border-brand-blue data-[state=active]:bg-transparent data-[state=active]:shadow-none"
                  >
                    <Star className="mr-1.5 h-4 w-4" />
                    技能
                  </TabsTrigger>
                  <TabsTrigger
                    value="badges"
                    className="rounded-none border-b-2 border-transparent px-6 py-3 data-[state=active]:border-brand-blue data-[state=active]:bg-transparent data-[state=active]:shadow-none"
                  >
                    <Award className="mr-1.5 h-4 w-4" />
                    徽章
                  </TabsTrigger>
                  <TabsTrigger
                    value="settings"
                    className="rounded-none border-b-2 border-transparent px-6 py-3 data-[state=active]:border-brand-blue data-[state=active]:bg-transparent data-[state=active]:shadow-none"
                  >
                    <Settings className="mr-1.5 h-4 w-4" />
                    设置
                  </TabsTrigger>
                </TabsList>

                {/* 技能面板 */}
                <TabsContent value="skills" className="p-6">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {mockProfile.skills.map((skill) => {
                      const Icon = skill.icon;
                      return (
                        <div
                          key={skill.name}
                          className="flex items-center gap-4 rounded-xl border border-gray-100 bg-gray-50/50 p-4"
                        >
                          <ProgressRing progress={skill.progress} size={56} strokeWidth={4}>
                            <span className="text-xs font-bold text-gray-700">
                              {skill.progress}
                            </span>
                          </ProgressRing>
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <Icon className="h-4 w-4 text-brand-blue" />
                              <span className="text-sm font-medium text-gray-900">
                                {skill.name}
                              </span>
                            </div>
                            <p className="mt-0.5 text-xs text-brand-gray">
                              等级 {skill.level}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </TabsContent>

                {/* 徽章面板 */}
                <TabsContent value="badges" className="p-6">
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
                    {mockProfile.badges.map((badge) => (
                      <div
                        key={badge.name}
                        className={cn(
                          "flex flex-col items-center gap-2 rounded-xl border p-4 transition-all",
                          badge.unlocked
                            ? "border-gray-100 bg-white shadow-sm"
                            : "border-dashed border-gray-200 bg-gray-50 opacity-60",
                        )}
                      >
                        <div
                          className={cn(
                            "flex h-12 w-12 items-center justify-center rounded-full",
                            badge.unlocked ? badge.color : "bg-gray-200 text-gray-400",
                          )}
                        >
                          {badge.unlocked ? (
                            <Trophy className="h-6 w-6" />
                          ) : (
                            <Lock className="h-5 w-5" />
                          )}
                        </div>
                        <span
                          className={cn(
                            "text-xs font-medium",
                            badge.unlocked ? "text-gray-700" : "text-brand-gray",
                          )}
                        >
                          {badge.name}
                        </span>
                      </div>
                    ))}
                  </div>
                </TabsContent>

                {/* 设置面板 */}
                <TabsContent value="settings" className="p-6">
                  <div className="space-y-1">
                    {[
                      {
                        icon: Shield,
                        label: "隐私设置",
                        desc: "管理个人隐私和安全",
                      },
                      {
                        icon: Bell,
                        label: "通知设置",
                        desc: "自定义通知方式",
                      },
                      {
                        icon: Moon,
                        label: "显示设置",
                        desc: "调整主题和字号",
                      },
                      {
                        icon: Calendar,
                        label: "学习提醒",
                        desc: "设置每日学习提醒时间",
                      },
                    ].map((setting) => {
                      const Icon = setting.icon;
                      return (
                        <button
                          key={setting.label}
                          className="flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left transition-colors hover:bg-gray-50"
                        >
                          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-100">
                            <Icon className="h-4 w-4 text-brand-gray" />
                          </div>
                          <div className="flex-1">
                            <p className="text-sm font-medium text-gray-900">{setting.label}</p>
                            <p className="text-xs text-brand-gray">{setting.desc}</p>
                          </div>
                          <ChevronRight className="h-4 w-4 text-brand-gray" />
                        </button>
                      );
                    })}
                  </div>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </motion.div>
      </motion.div>
    </MainLayout>
  );
}
