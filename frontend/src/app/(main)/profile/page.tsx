/**
 * 个人中心页面
 *
 * 功能说明：
 * - 展示用户头像、昵称、等级、经验值等基本信息
 * - 学习统计（连续学习天数、周目标、总经验值）
 * - 技能面板、徽章成就、设置三个 Tab 切换
 * - 支持编辑昵称和简介
 * - 未登录用户显示引导去登录
 * - 从后端获取成就数据并展示解锁/未解锁状态
 */

"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { MainLayout } from "@/components/layout/main-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { ProgressRing } from "@/components/common/progress-ring";
import { useAuthStore } from "@/stores/auth-store";
import { apiClient } from "@/lib/api-client";
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
  Loader2,
  Rocket,
} from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

/** 成就数据接口（来自 /api/v1/achievements/me） */
interface AchievementItem {
  id: string;
  code?: string;
  name: string;
  description?: string;
  icon_url?: string;
  achieved_at?: string | null;
  unlocked?: boolean;
}

/**
 * 个人中心页面组件
 * @returns 个人资料页面
 */
export default function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const stats = useAuthStore((s) => s.stats);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const fetchUserStats = useAuthStore((s) => s.fetchUserStats);
  const updateUser = useAuthStore((s) => s.updateUser);
  const fetchProfile = useAuthStore((s) => s.fetchProfile);

  // 成就数据状态
  const [achievements, setAchievements] = useState<AchievementItem[]>([]);
  const [achievementsLoading, setAchievementsLoading] = useState(false);

  // 编辑资料 Dialog 状态
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editNickname, setEditNickname] = useState("");
  const [editBio, setEditBio] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  /**
   * 获取用户成就数据
   */
  const fetchAchievements = useCallback(async () => {
    setAchievementsLoading(true);
    try {
      const data = await apiClient.get<AchievementItem[]>("/v1/achievements/me");
      setAchievements(Array.isArray(data) ? data : []);
    } catch (error) {
      console.warn("获取成就数据失败:", error);
      setAchievements([]);
    } finally {
      setAchievementsLoading(false);
    }
  }, []);

  // 页面挂载时获取最新统计数据和成就
  useEffect(() => {
    if (isAuthenticated) {
      fetchUserStats();
      fetchAchievements();
    }
  }, [isAuthenticated, fetchAchievements, fetchUserStats]);

  // 从真实数据计算等级和经验值（每 200 分升一级）
  const totalScore = stats?.total_score ?? user?.points ?? 0;
  const LEVEL_XP = 200; // 每 200 分升一级
  const level = Math.floor(totalScore / LEVEL_XP) + 1;
  const xpInCurrentLevel = totalScore % LEVEL_XP;
  const maxXpInLevel = LEVEL_XP;
  const xpProgress = Math.round((xpInCurrentLevel / maxXpInLevel) * 100);

  // 连续学习天数
  const streakDays = stats?.streak_days ?? user?.streakDays ?? 0;

  // 本周学习时间（默认目标 5 小时）
  const weekStudyHours = stats?.week_study_hours ?? 0;
  const weeklyTarget = 5; // 默认每周目标 5 小时
  const weeklyProgress = weekStudyHours > 0 ? Math.min(Math.round((weekStudyHours / weeklyTarget) * 100), 100) : 0;

  // 昵称和简介（带默认值）
  const nickname = user?.nickname || "同学";
  const bio = user?.bio || "热爱学习，喜欢探索新知识";

  // 技能面板：标注即将上线
  const skillSubjects = [
    { name: "数学思维", icon: Calculator },
    { name: "编程基础", icon: Code2 },
    { name: "英语阅读", icon: Languages },
    { name: "科学探索", icon: FlaskConical },
    { name: "语文写作", icon: BookOpen },
    { name: "艺术创意", icon: Palette },
  ];

  // 徽章颜色列表（循环使用）
  const badgeColors = [
    "bg-amber-100 text-amber-600",
    "bg-orange-100 text-orange-600",
    "bg-blue-100 text-blue-600",
    "bg-indigo-100 text-indigo-600",
    "bg-green-100 text-green-600",
    "bg-purple-100 text-purple-600",
    "bg-pink-100 text-pink-600",
    "bg-cyan-100 text-cyan-600",
    "bg-red-100 text-red-600",
    "bg-teal-100 text-teal-600",
    "bg-lime-100 text-lime-600",
    "bg-violet-100 text-violet-600",
  ];

  /**
   * 打开编辑资料弹窗，初始化表单值
   */
  const handleOpenEditDialog = () => {
    setEditNickname(nickname);
    setEditBio(bio);
    setEditDialogOpen(true);
  };

  /**
   * 保存编辑后的个人资料
   */
  const handleSaveProfile = async () => {
    if (!editNickname.trim()) return;
    setEditSaving(true);
    try {
      await apiClient.put("/v1/users/me", { nickname: editNickname.trim() });
      // 更新本地 store
      updateUser({ nickname: editNickname.trim(), bio: editBio.trim() });
      setEditDialogOpen(false);
    } catch (error) {
      console.error("更新资料失败:", error);
      // 即使 API 失败也更新本地 store 作为 fallback
      updateUser({ nickname: editNickname.trim(), bio: editBio.trim() });
      setEditDialogOpen(false);
    } finally {
      setEditSaving(false);
    }
  };

  // 未登录引导：显示登录提示
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

  // 容器与子元素动画配置
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
                      {nickname.charAt(0)}
                    </AvatarFallback>
                  </Avatar>
                </div>

                {/* 基本信息 */}
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h1 className="text-xl font-bold text-gray-900">{nickname}</h1>
                    <Badge className="bg-brand-blue text-white">Lv.{level}</Badge>
                  </div>
                  <p className="mt-1 text-sm text-brand-gray">{bio}</p>

                  {/* 经验值进度 */}
                  <div className="mt-3 flex items-center gap-3">
                    <div className="flex-1">
                      <div className="mb-1 flex justify-between text-xs">
                        <span className="text-brand-gray">经验值</span>
                        <span className="font-medium text-gray-700">
                          {xpInCurrentLevel} / {maxXpInLevel}
                        </span>
                      </div>
                      <Progress value={xpProgress} className="h-2" />
                    </div>
                    <Button variant="outline" size="sm" onClick={handleOpenEditDialog}>
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
                <p className="text-2xl font-bold text-gray-900">{streakDays}天</p>
                <p className="text-xs text-brand-gray">连续学习</p>
              </div>
            </CardContent>
          </Card>

          {/* 周目标 */}
          <Card className="shadow-card">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <p className="text-sm text-brand-gray">本周学习</p>
                <span className="text-sm font-medium text-brand-blue">
                  {weekStudyHours}/{weeklyTarget} 小时
                </span>
              </div>
              <Progress value={weeklyProgress} className="mt-3 h-2" />
              <p className="mt-2 text-xs text-brand-gray">
                {weekStudyHours >= weeklyTarget
                  ? "已完成本周目标"
                  : `还差 ${(weeklyTarget - weekStudyHours).toFixed(1)} 小时`}
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
                <p className="text-2xl font-bold text-gray-900">
                  {totalScore.toLocaleString()}
                </p>
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

                {/* 技能面板 - 即将上线 */}
                <TabsContent value="skills" className="p-6">
                  <div className="mb-4 rounded-xl border border-dashed border-brand-blue/30 bg-brand-blue/5 p-4 text-center">
                    <Rocket className="mx-auto h-8 w-8 text-brand-blue" />
                    <p className="mt-2 text-sm font-medium text-brand-blue">技能系统即将上线</p>
                    <p className="mt-1 text-xs text-brand-gray">
                      完成更多课程后，你的学科技能将在这里展示
                    </p>
                  </div>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {skillSubjects.map((skill) => {
                      const Icon = skill.icon;
                      return (
                        <div
                          key={skill.name}
                          className="flex items-center gap-4 rounded-xl border border-gray-100 bg-gray-50/50 p-4 opacity-60"
                        >
                          <ProgressRing progress={0} size={56} strokeWidth={4}>
                            <span className="text-xs text-brand-gray">--</span>
                          </ProgressRing>
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <Icon className="h-4 w-4 text-brand-gray" />
                              <span className="text-sm font-medium text-gray-500">
                                {skill.name}
                              </span>
                            </div>
                            <p className="mt-0.5 text-xs text-brand-gray">
                              等级 --
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </TabsContent>

                {/* 徽章面板 - 从后端获取 */}
                <TabsContent value="badges" className="p-6">
                  {achievementsLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-6 w-6 animate-spin text-brand-gray" />
                      <span className="ml-2 text-sm text-brand-gray">加载成就中...</span>
                    </div>
                  ) : achievements.length > 0 ? (
                    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
                      {achievements.map((ach, index) => {
                        const isUnlocked = ach.achieved_at != null || ach.unlocked === true;
                        const colorClass = badgeColors[index % badgeColors.length];
                        return (
                          <div
                            key={ach.id || ach.code || ach.name}
                            className={cn(
                              "flex flex-col items-center gap-2 rounded-xl border p-4 transition-all",
                              isUnlocked
                                ? "border-gray-100 bg-white shadow-sm"
                                : "border-dashed border-gray-200 bg-gray-50 opacity-60",
                            )}
                          >
                            <div
                              className={cn(
                                "flex h-12 w-12 items-center justify-center rounded-full",
                                isUnlocked ? colorClass : "bg-gray-200 text-gray-400",
                              )}
                            >
                              {isUnlocked ? (
                                <Trophy className="h-6 w-6" />
                              ) : (
                                <Lock className="h-5 w-5" />
                              )}
                            </div>
                            <span
                              className={cn(
                                "text-xs font-medium",
                                isUnlocked ? "text-gray-700" : "text-brand-gray",
                              )}
                            >
                              {ach.name}
                            </span>
                            {ach.description && (
                              <span className="text-center text-[10px] text-brand-gray">
                                {ach.description}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-8 text-brand-gray">
                      <Trophy className="h-12 w-12 text-gray-200" />
                      <p className="mt-3 text-sm">暂无成就数据</p>
                      <p className="mt-1 text-xs">完成学习任务来解锁成就吧</p>
                    </div>
                  )}
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

      {/* 编辑资料 Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑资料</DialogTitle>
            <DialogDescription>修改你的个人信息</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">昵称</label>
              <Input
                value={editNickname}
                onChange={(e) => setEditNickname(e.target.value)}
                placeholder="请输入昵称"
                maxLength={50}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">简介</label>
              <textarea
                value={editBio}
                onChange={(e) => setEditBio(e.target.value)}
                placeholder="介绍一下你自己吧"
                maxLength={200}
                rows={3}
                className="flex w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm ring-offset-white placeholder:text-brand-gray focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditDialogOpen(false)}
              disabled={editSaving}
            >
              取消
            </Button>
            <Button
              onClick={handleSaveProfile}
              disabled={editSaving || !editNickname.trim()}
            >
              {editSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </MainLayout>
  );
}
