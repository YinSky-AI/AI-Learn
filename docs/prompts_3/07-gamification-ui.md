# 07 - 游戏化UI：积分 + 等级 + 连胜 + 成就通知

## 任务目标

把学习变成游戏，让用户愿意回来：
- 答题得积分，积分升级
- 连胜机制（连续答对有加成）
- 学习日历（打卡记录）
- 成就通知（解锁成就时弹Toast）
- 个人资料页展示等级/积分/连胜

## 当前代码状态

### User模型

文件：`backend/app/models/user.py`

User表可能有 `points`、`level`、`streak` 等字段，也可能没有。先确认，没有就加上。

### 前端个人中心

文件：`frontend/src/app/(main)/profile/page.tsx`

目前个人中心比较简单，只有基本信息。

### 答题API

答题时可能已经在加分了，也可能没有。需要确认。

## 需要做的改动

### Step 1：确认/完善用户积分字段

在User模型中确认有以下字段，没有就加上：

```python
# 在User模型中增加/确认：
points: Mapped[int] = mapped_column(Integer, default=0)  # 总积分
level: Mapped[int] = mapped_column(Integer, default=1)   # 等级（1-100）
streak: Mapped[int] = mapped_column(Integer, default=0)   # 当前连胜
max_streak: Mapped[int] = mapped_column(Integer, default=0)  # 最高连胜
total_answered: Mapped[int] = mapped_column(Integer, default=0)  # 总答题数
correct_answered: Mapped[int] = mapped_column(Integer, default=0)  # 答对数
last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # 最后活跃日期
study_days_count: Mapped[int] = mapped_column(Integer, default=0)  # 累计学习天数
```

### Step 2：积分计算逻辑

新建 `backend/app/services/gamification_service.py`：

```python
"""
游戏化服务：积分、等级、连胜、成就
"""

import math
from datetime import date

# 等级对应所需积分（指数增长）
def get_level_up_points(level: int) -> int:
    """升到下一级需要的积分"""
    return int(100 * math.pow(1.2, level - 1))

def calculate_level(total_points: int) -> int:
    """根据总积分计算等级"""
    level = 1
    points_needed = 0
    while True:
        points_needed += get_level_up_points(level)
        if total_points < points_needed:
            return level
        level += 1

def get_level_progress(total_points: int) -> tuple:
    """获取当前等级的进度 (当前等级, 已得积分, 升级所需积分)"""
    level = 1
    points_needed = 0
    prev_points = 0
    while True:
        points_needed += get_level_up_points(level)
        if total_points < points_needed:
            current_points = total_points - prev_points
            needed = get_level_up_points(level)
            return level, current_points, needed
        prev_points = points_needed
        level += 1

# 答题积分计算
def calculate_answer_points(
    is_correct: bool,
    difficulty: str = "intermediate",
    current_streak: int = 0,
) -> tuple:
    """
    计算答题获得的积分
    
    Returns: (points, streak_bonus, difficulty_bonus)
    """
    if not is_correct:
        return 0, 0, 0
    
    # 基础分
    base = {
        "beginner": 5,
        "intermediate": 10,
        "advanced": 20,
    }.get(difficulty, 10)
    
    # 连胜加成（每5连胜+10%，最多+50%）
    streak_multiplier = min(current_streak * 0.1, 0.5)
    streak_bonus = int(base * streak_multiplier)
    
    total = base + streak_bonus
    return total, streak_bonus, base


# 成就定义
ACHIEVEMENTS = [
    {
        "id": "first_answer",
        "name": "初出茅庐",
        "description": "完成第一道题",
        "icon": "🎯",
        "condition": lambda user: user.total_answered >= 1,
    },
    {
        "id": "ten_correct",
        "name": "小试牛刀",
        "description": "累计答对10道题",
        "icon": "✨",
        "condition": lambda user: user.correct_answered >= 10,
    },
    {
        "id": "streak_5",
        "name": "势如破竹",
        "description": "连续答对5道题",
        "icon": "🔥",
        "condition": lambda user: user.max_streak >= 5,
    },
    {
        "id": "streak_10",
        "name": "百战百胜",
        "description": "连续答对10道题",
        "icon": "💪",
        "condition": lambda user: user.max_streak >= 10,
    },
    {
        "id": "level_5",
        "name": "学有所成",
        "description": "达到5级",
        "icon": "⭐",
        "condition": lambda user: user.level >= 5,
    },
    {
        "id": "study_7_days",
        "name": "一周坚持",
        "description": "累计学习7天",
        "icon": "📅",
        "condition": lambda user: user.study_days_count >= 7,
    },
]


def check_new_achievements(user, previous_state: dict) -> list:
    """
    检查是否解锁了新成就
    
    Args:
        user: 当前用户对象（更新后）
        previous_state: 更新前的状态字典
    
    Returns:
        新解锁的成就列表
    """
    new_achievements = []
    
    for ach in ACHIEVEMENTS:
        # 检查之前是否已经达成
        prev_achieved = ach["condition"](type('FakeUser', (), previous_state)())
        current_achieved = ach["condition"](user)
        
        if current_achieved and not prev_achieved:
            new_achievements.append({
                "id": ach["id"],
                "name": ach["name"],
                "description": ach["description"],
                "icon": ach["icon"],
            })
    
    return new_achievements


def update_study_daily(user) -> bool:
    """
    更新每日学习记录
    
    如果今天是新的一天，学习天数+1
    Returns: 是否是新的一天（新的一天可以弹"欢迎回来"）
    """
    today = date.today()
    if user.last_active_date != today:
        user.last_active_date = today
        user.study_days_count = (user.study_days_count or 0) + 1
        return True
    return False
```

### Step 3：答题时更新积分

在答题API中集成游戏化服务：

```python
# 答题接口中增加：
from app.services.gamification_service import (
    calculate_answer_points, 
    calculate_level,
    check_new_achievements,
    update_study_daily,
)

# 保存答题结果之前/之后：

# 记录之前的状态（用于成就检测）
prev_state = {
    "total_answered": user.total_answered,
    "correct_answered": user.correct_answered,
    "max_streak": user.max_streak,
    "level": user.level,
    "study_days_count": user.study_days_count,
}

# 更新连胜
if is_correct:
    user.streak = (user.streak or 0) + 1
    user.max_streak = max(user.max_streak or 0, user.streak)
else:
    user.streak = 0

# 更新答题统计
user.total_answered = (user.total_answered or 0) + 1
if is_correct:
    user.correct_answered = (user.correct_answered or 0) + 1

# 计算积分
points_earned, streak_bonus, base_points = calculate_answer_points(
    is_correct=is_correct,
    difficulty=question.difficulty,
    current_streak=user.streak,
)
user.points = (user.points or 0) + points_earned

# 更新等级
new_level = calculate_level(user.points)
leveled_up = new_level > user.level
user.level = new_level

# 更新每日学习
is_new_day = update_study_daily(user)

# 检查新成就
new_achievements = check_new_achievements(user, prev_state)

# 在返回结果中增加游戏化信息：
return success_response(
    data={
        # ... 原有的答题结果
        "gamification": {
            "points_earned": points_earned,
            "base_points": base_points,
            "streak_bonus": streak_bonus,
            "total_points": user.points,
            "level": user.level,
            "streak": user.streak,
            "leveled_up": leveled_up,
            "new_achievements": new_achievements,
            "is_new_day": is_new_day,
        },
    }
)
```

### Step 4：游戏化数据API

在用户相关API中增加获取游戏化数据的接口：
- GET /api/v1/user/gamification — 获取当前积分、等级、连胜等
- GET /api/v1/user/achievements — 获取成就列表和解锁状态

### Step 5：前端成就通知组件

新建 `frontend/src/components/gamification/achievement-toast.tsx`：

```tsx
"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Trophy } from "lucide-react";

interface Achievement {
  id: string;
  name: string;
  description: string;
  icon: string;
}

interface Props {
  achievement: Achievement | null;
  onClose: () => void;
}

export function AchievementToast({ achievement, onClose }: Props) {
  useEffect(() => {
    if (achievement) {
      const timer = setTimeout(onClose, 4000);
      return () => clearTimeout(timer);
    }
  }, [achievement, onClose]);

  return (
    <AnimatePresence>
      {achievement && (
        <motion.div
          initial={{ y: -100, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -100, opacity: 0 }}
          className="fixed top-4 left-1/2 -translate-x-1/2 z-50"
        >
          <div className="bg-gradient-to-r from-amber-400 to-orange-500 text-white px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-4 min-w-[300px]">
            <div className="text-4xl">{achievement.icon}</div>
            <div className="flex-1">
              <div className="text-xs opacity-80 mb-0.5">🎉 成就解锁</div>
              <div className="font-bold text-lg">{achievement.name}</div>
              <div className="text-sm opacity-90">{achievement.description}</div>
            </div>
            <button
              onClick={onClose}
              className="p-1 hover:bg-white/20 rounded-full transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

### Step 6：前端积分/等级展示

在学习页顶部加一个简洁的积分条：
- 当前等级
- 升级进度条
- 当前连胜（有连胜时显示🔥）

在个人中心页展示完整的游戏化信息：
- 等级徽章
- 总积分
- 答题统计（总题数、正确率）
- 连胜记录
- 学习天数
- 成就墙（已解锁的成就图标）

## 文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `backend/app/services/gamification_service.py` | 游戏化核心逻辑 |
| 修改 | `backend/app/models/user.py` | 确认/增加积分相关字段 |
| 修改 | `backend/app/api/v1/user_courses.py` | 答题时更新积分 |
| 新增API | 用户/游戏化相关接口 | 获取积分、成就数据 |
| 新建 | `frontend/src/components/gamification/achievement-toast.tsx` | 成就通知 |
| 新建 | `frontend/src/components/gamification/level-badge.tsx` | 等级徽章组件 |
| 修改 | `frontend/src/app/(main)/learning/[id]/page.tsx` | 顶部积分条 |
| 修改 | `frontend/src/app/(main)/profile/page.tsx` | 个人中心游戏化展示 |

## 验收标准

- [ ] 答对题目能获得积分，答错不扣分
- [ ] 连胜有额外积分加成
- [ ] 积分达到阈值后自动升级
- [ ] 解锁成就时弹出动画通知
- [ ] 个人中心能看到完整的游戏化数据
- [ ] 学习页顶部显示等级和连胜
- [ ] 新的一天学习时有"欢迎回来"的提示

## 注意事项

1. **数据库迁移**：新增字段需要migration
2. **积分不要太容易**：要让用户有成长感但又不会太快满级
3. **成就不要太密集**：一次答题解锁太多成就会显得廉价
4. **动画要克制**：成就通知不要太频繁，最多同时显示1个
5. **移动端适配**：积分条在小屏幕上要紧凑
6. **性能**：成就检查用纯函数计算，不要查DB

## 依赖关系

- **前置依赖**：06号（错题本，有完整答题流程）
- **后续依赖**：08号（行为建模）
