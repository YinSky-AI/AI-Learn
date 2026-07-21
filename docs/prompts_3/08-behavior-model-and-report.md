# 08 - 行为建模 + 学习报告页

## 任务目标

1. 每次答题都更新用户的行为画像（知识点掌握程度）
2. 生成可视化的学习报告页：
   - 总体学习情况（学习时长、答题数、正确率）
   - 各学科掌握雷达图
   - 知识点掌握热力图
   - 薄弱知识点推荐
   - 学习趋势（近7天/30天）

## 当前代码状态

### 行为模型

User模型中有个 `behavior_model` JSON字段，但可能从来没有写入过数据。

### 学习报告

目前没有学习报告页面。

## 需要做的改动

### Step 1：行为模型更新服务

新建 `backend/app/services/behavior_service.py`：

```python
"""
行为建模服务：跟踪用户的知识点掌握程度和学习行为
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.user_answer import UserAnswer
from app.models.question import Question

logger = logging.getLogger(__name__)


class BehaviorService:
    """行为建模服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def update_after_answer(
        self,
        user_id: str,
        question: Question,
        is_correct: bool,
        response_time_ms: int = 0,
    ) -> dict:
        """
        答题后更新行为模型
        
        更新内容：
        - 知识点掌握程度（答对加分，答错减分，带时间衰减）
        - 学科掌握程度
        - 答题速度
        - 难度适应度
        """
        user = await self.db.get(User, user_id)
        if not user:
            return {}
        
        # 读取当前行为模型
        behavior = user.behavior_model or {}
        if isinstance(behavior, str):
            behavior = json.loads(behavior)
        
        # 初始化结构
        if "knowledge_mastery" not in behavior:
            behavior["knowledge_mastery"] = {}  # {知识点: {level, total, correct, last_updated}}
        if "subject_mastery" not in behavior:
            behavior["subject_mastery"] = {}  # {学科: {level, total, correct}}
        if "study_stats" not in behavior:
            behavior["study_stats"] = {
                "total_time_minutes": 0,
                "daily_records": {},  # {日期: {answered, correct, time_minutes}}
            }
        
        # 更新知识点掌握
        knowledge_points = question.knowledge_points or []
        for kp in knowledge_points:
            if kp not in behavior["knowledge_mastery"]:
                behavior["knowledge_mastery"][kp] = {
                    "level": 0.5,  # 初始掌握度50%
                    "total": 0,
                    "correct": 0,
                    "last_updated": None,
                }
            
            kp_data = behavior["knowledge_mastery"][kp]
            kp_data["total"] += 1
            if is_correct:
                kp_data["correct"] += 1
            
            # 指数移动平均更新掌握度
            # 答对：掌握度上升，答错：掌握度下降
            alpha = 0.3  # 学习率
            if is_correct:
                kp_data["level"] = min(1.0, kp_data["level"] + alpha * (1 - kp_data["level"]))
            else:
                kp_data["level"] = max(0.0, kp_data["level"] - alpha * kp_data["level"])
            
            kp_data["last_updated"] = datetime.utcnow().isoformat()
        
        # 更新学科掌握
        subject = question.subject
        if subject not in behavior["subject_mastery"]:
            behavior["subject_mastery"][subject] = {
                "level": 0.5,
                "total": 0,
                "correct": 0,
            }
        
        subj_data = behavior["subject_mastery"][subject]
        subj_data["total"] += 1
        if is_correct:
            subj_data["correct"] += 1
        subj_data["level"] = subj_data["correct"] / max(subj_data["total"], 1)
        
        # 更新每日学习记录
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if today not in behavior["study_stats"]["daily_records"]:
            behavior["study_stats"]["daily_records"][today] = {
                "answered": 0,
                "correct": 0,
                "time_minutes": 0,
            }
        
        day_record = behavior["study_stats"]["daily_records"][today]
        day_record["answered"] += 1
        if is_correct:
            day_record["correct"] += 1
        day_record["time_minutes"] += response_time_ms / 60000  # 转分钟
        
        behavior["study_stats"]["total_time_minutes"] += response_time_ms / 60000
        
        # 保存回用户模型
        user.behavior_model = behavior
        await self.db.commit()
        
        return behavior
    
    async def get_learning_report(self, user_id: str, days: int = 30) -> dict:
        """
        生成学习报告
        
        Returns:
            {
                overview: { total_answered, correct_rate, study_days, total_time },
                subject_mastery: [{ subject, level, total, correct }],
                weak_points: [{ point, level, suggestion }],
                strong_points: [{ point, level }],
                daily_trend: [{ date, answered, correct }],
                knowledge_heatmap: { [知识点]: level },
            }
        """
        user = await self.db.get(User, user_id)
        if not user:
            return {}
        
        behavior = user.behavior_model or {}
        if isinstance(behavior, str):
            behavior = json.loads(behavior)
        
        # 1. 总体概览
        knowledge_mastery = behavior.get("knowledge_mastery", {})
        subject_mastery = behavior.get("subject_mastery", {})
        study_stats = behavior.get("study_stats", {})
        daily_records = study_stats.get("daily_records", {})
        
        total_answered = sum(
            s.get("total", 0) for s in subject_mastery.values()
        )
        total_correct = sum(
            s.get("correct", 0) for s in subject_mastery.values()
        )
        correct_rate = total_correct / max(total_answered, 1)
        
        # 计算学习天数
        study_days = len(daily_records)
        
        # 2. 学科掌握（排序）
        subjects = [
            {
                "subject": subj,
                "level": data.get("level", 0),
                "total": data.get("total", 0),
                "correct": data.get("correct", 0),
            }
            for subj, data in subject_mastery.items()
        ]
        subjects.sort(key=lambda x: x["level"], reverse=True)
        
        # 3. 薄弱知识点（掌握度最低的5个）
        all_kps = [
            {"point": kp, "level": data.get("level", 0), "total": data.get("total", 0)}
            for kp, data in knowledge_mastery.items()
        ]
        all_kps.sort(key=lambda x: x["level"])
        weak_points = [
            {
                **wp,
                "suggestion": f"建议多练习{wp['point']}相关的题目",
            }
            for wp in all_kps[:5] if wp["total"] >= 2  # 至少做过2题才算薄弱
        ]
        
        # 4. 强项知识点
        strong_points = [
            sp for sp in all_kps[-5:] if sp["level"] >= 0.7
        ]
        strong_points.reverse()
        
        # 5. 每日趋势（近N天）
        daily_trend = []
        for i in range(days - 1, -1, -1):
            date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            record = daily_records.get(date, {"answered": 0, "correct": 0})
            daily_trend.append({
                "date": date,
                "answered": record.get("answered", 0),
                "correct": record.get("correct", 0),
            })
        
        # 6. 知识点热力图（所有知识点及其掌握度）
        heatmap = {
            kp: data.get("level", 0)
            for kp, data in knowledge_mastery.items()
        }
        
        return {
            "overview": {
                "total_answered": total_answered,
                "correct_rate": round(correct_rate, 3),
                "study_days": study_days,
                "total_time_minutes": round(study_stats.get("total_time_minutes", 0), 1),
            },
            "subject_mastery": subjects,
            "weak_points": weak_points,
            "strong_points": strong_points,
            "daily_trend": daily_trend,
            "knowledge_heatmap": heatmap,
        }
```

### Step 2：行为模型API

在用户相关API中增加：
- GET /api/v1/user/behavior/report?days=30 — 获取学习报告
- GET /api/v1/user/behavior/knowledge — 获取知识点掌握详情

### Step 3：答题时更新行为模型

在答题接口中调用 `BehaviorService.update_after_answer()`。

### Step 4：前端学习报告页

新建 `frontend/src/app/(main)/report/page.tsx`：

```tsx
"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { BookOpen, Target, Clock, TrendingUp, AlertCircle, Award } from "lucide-react";

// 需要安装 recharts 用于图表
// import { RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Tooltip, ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Legend, BarChart, Bar } from "recharts";

export default function LearningReportPage() {
  const [report, setReport] = useState<any>(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    loadReport();
  }, [days]);

  const loadReport = async () => {
    const res = await fetch(`/api/v1/user/behavior/report?days=${days}`);
    const data = await res.json();
    if (data.code === 0) setReport(data.data);
  };

  if (!report) return <div className="p-8 text-center">加载中...</div>;

  const { overview, subject_mastery, weak_points, strong_points, daily_trend } = report;

  return (
    <div className="container mx-auto px-4 py-6 max-w-5xl">
      <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <TrendingUp className="w-7 h-7" />
        学习报告
      </h1>

      {/* 时间范围选择 */}
      <Tabs defaultValue="30" className="mb-6" onValueChange={(v) => setDays(Number(v))}>
        <TabsList>
          <TabsTrigger value="7">近7天</TabsTrigger>
          <TabsTrigger value="30">近30天</TabsTrigger>
          <TabsTrigger value="90">近90天</TabsTrigger>
        </TabsList>
      </Tabs>

      {/* 概览卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
              <BookOpen className="w-4 h-4" />
              答题总数
            </div>
            <div className="text-2xl font-bold">{overview.total_answered}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
              <Target className="w-4 h-4" />
              正确率
            </div>
            <div className="text-2xl font-bold text-green-600">
              {Math.round(overview.correct_rate * 100)}%
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
              <Clock className="w-4 h-4" />
              学习天数
            </div>
            <div className="text-2xl font-bold text-blue-600">{overview.study_days}天</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
              <Award className="w-4 h-4" />
              学习时长
            </div>
            <div className="text-2xl font-bold text-purple-600">
              {Math.round(overview.total_time_minutes / 60)}小时
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 学科掌握雷达图 + 每日趋势 */}
      <div className="grid md:grid-cols-2 gap-6 mb-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">学科掌握</CardTitle>
          </CardHeader>
          <CardContent>
            {subject_mastery.length === 0 ? (
              <div className="text-center py-8 text-gray-400">暂无数据</div>
            ) : (
              <div className="space-y-3">
                {subject_mastery.map((s: any) => (
                  <div key={s.subject}>
                    <div className="flex justify-between text-sm mb-1">
                      <span>{s.subject}</span>
                      <span className="text-gray-500">{Math.round(s.level * 100)}%</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-blue-400 to-blue-600 rounded-full transition-all"
                        style={{ width: `${s.level * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">每日答题趋势</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[200px] flex items-end gap-1">
              {daily_trend.map((d: any) => (
                <div key={d.date} className="flex-1 flex flex-col items-center">
                  <div
                    className="w-full bg-blue-400 rounded-t transition-all hover:bg-blue-500"
                    style={{ height: `${(d.answered / Math.max(...daily_trend.map((x: any) => x.answered), 1)) * 150}px` }}
                    title={`${d.date}: ${d.answered}题`}
                  />
                  <div className="text-[10px] text-gray-400 mt-1">
                    {d.date.slice(5)}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 薄弱点 + 强项 */}
      <div className="grid md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-red-500" />
              薄弱知识点
            </CardTitle>
          </CardHeader>
          <CardContent>
            {weak_points.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                太棒了，没有明显薄弱点！
              </div>
            ) : (
              <ul className="space-y-3">
                {weak_points.map((wp: any) => (
                  <li key={wp.point} className="p-3 bg-red-50 rounded-lg">
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-medium text-sm">{wp.point}</span>
                      <span className="text-red-600 text-sm">
                        {Math.round(wp.level * 100)}%
                      </span>
                    </div>
                    <div className="h-1.5 bg-red-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-red-400 rounded-full"
                        style={{ width: `${wp.level * 100}%` }}
                      />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">{wp.suggestion}</p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Award className="w-5 h-5 text-green-500" />
              强项知识点
            </CardTitle>
          </CardHeader>
          <CardContent>
            {strong_points.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                多答题来发现你的强项吧~
              </div>
            ) : (
              <ul className="space-y-3">
                {strong_points.map((sp: any) => (
                  <li key={sp.point} className="p-3 bg-green-50 rounded-lg">
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-medium text-sm">{sp.point}</span>
                      <span className="text-green-600 text-sm">
                        {Math.round(sp.level * 100)}%
                      </span>
                    </div>
                    <div className="h-1.5 bg-green-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-400 rounded-full"
                        style={{ width: `${sp.level * 100}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
```

> 注：如果项目没有装 recharts，先用纯CSS的条形图/进度条实现（上面的代码就是纯CSS的），够用了。后面有时间再加图表库。

### Step 5：导航加入口

在侧边栏/底部导航中加入"学习报告"入口。

## 文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `backend/app/services/behavior_service.py` | 行为建模服务 |
| 新增API | 用户/行为相关接口 | 学习报告接口 |
| 修改 | 答题API | 答题后更新行为模型 |
| 新建 | `frontend/src/app/(main)/report/page.tsx` | 学习报告页面 |
| 修改 | 导航组件 | 加入学习报告入口 |

## 验收标准

- [ ] 每次答题后 behavior_model 字段有更新
- [ ] 知识点掌握度会根据答题结果变化
- [ ] 学习报告页能展示总体数据
- [ ] 学科掌握进度条正确显示
- [ ] 每日答题趋势图正确显示
- [ ] 薄弱知识点和强项知识点列表正确
- [ ] 支持切换7天/30天/90天范围

## 注意事项

1. **behavior_model字段**：确认User模型有这个字段，没有就加上（JSON类型）
2. **JSON序列化**：读写时注意处理字符串和对象的转换
3. **时间衰减**：掌握度不是永久的，长期不练习会慢慢下降（这个可以先不做，等v2）
4. **性能**：behavior字段是一个JSON，每次答题都要读写整个JSON，数据量大了之后可能需要拆分
5. **空数据处理**：新用户没有数据时，页面要有友好的空状态
6. **图表库**：先用纯CSS实现，等基本功能跑通了再加 recharts

## 依赖关系

- **前置依赖**：07号（游戏化，有完整答题统计）
- **后续依赖**：11号（知识图谱可视化）
