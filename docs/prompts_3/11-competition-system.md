# 11 - 竞赛系统：每日挑战 + 排行榜 + 速度得分

## 任务目标

增加游戏化竞争元素，让学习更有动力：
- 每日挑战（每天一套题，计时挑战）
- 排行榜（按积分/连胜/正确率排名）
- 速度得分（答得又快又对得分更高）
- PK模式（和AI对战，有时间压力）

这个功能是"锦上添花"的，时间够就做，不够就跳过。

## 当前代码状态

目前没有竞赛相关的功能。

## 需要做的改动

### Step 1：每日挑战模型

新建 `backend/app/models/daily_challenge.py`：

```python
"""
每日挑战模型
"""

import uuid
from datetime import date, datetime
from sqlalchemy import String, Integer, DateTime, Date, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.core.database import Base


class DailyChallenge(Base):
    """每日挑战记录"""

    __tablename__ = "daily_challenges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    challenge_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(50))
    question_count: Mapped[int] = mapped_column(Integer, default=10)
    time_limit_seconds: Mapped[int] = mapped_column(Integer, default=300)  # 5分钟
    description: Mapped[str] = mapped_column(String(255, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DailyChallengeAttempt(Base):
    """每日挑战参与记录"""

    __tablename__ = "daily_challenge_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daily_challenges.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    
    score: Mapped[int] = mapped_column(Integer, default=0)  # 综合得分
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 排名
    
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

### Step 2：每日挑战服务

新建 `backend/app/services/daily_challenge_service.py`：

核心逻辑：
- 每天生成一套挑战题（从题库随机抽）
- 用户可以参与挑战，计时
- 得分 = 正确数 × 100 + 速度加成 + 连胜加成
- 完成后计算排名

### Step 3：排行榜API

新建排行榜接口：
- GET /api/v1/leaderboard/daily — 每日挑战排行榜
- GET /api/v1/leaderboard/total — 总积分排行榜
- GET /api/v1/leaderboard/streak — 连胜排行榜

### Step 4：前端每日挑战页

新建 `frontend/src/app/(main)/challenge/page.tsx`：

页面包含：
- 今日挑战卡片（学科、题目数、时间限制）
- "开始挑战"按钮
- 挑战进行中：计时器 + 题目 + 进度条
- 挑战结束：得分 + 排名 + 错题回顾

### Step 5：排行榜页面

新建 `frontend/src/app/(main)/leaderboard/page.tsx`：

- 三个Tab：每日 / 总积分 / 连胜
- 排行榜列表（头像、名字、分数、排名徽章）
- 当前用户的排名高亮
- 前三名有特殊样式（金/银/铜）

## 文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `backend/app/models/daily_challenge.py` | 挑战模型 |
| 新建 | `backend/app/services/daily_challenge_service.py` | 挑战服务 |
| 新建API | 挑战+排行榜接口 | 后端API |
| 新建 | `frontend/src/app/(main)/challenge/page.tsx` | 每日挑战页 |
| 新建 | `frontend/src/app/(main)/leaderboard/page.tsx` | 排行榜页 |
| 修改 | 导航组件 | 加入挑战/排行榜入口 |

## 验收标准

- [ ] 每天有一套挑战题
- [ ] 挑战有计时功能
- [ ] 完成后显示得分和排名
- [ ] 排行榜展示前50名
- [ ] 前三名有特殊样式
- [ ] 当前用户排名高亮
- [ ] 速度越快得分越高

## 注意事项

1. **题目不要太难**：挑战题难度适中，太打击信心就没人玩了
2. **防作弊**：简单的防作弊（同一用户一天只能参与一次），不用太复杂
3. **实时性**：排行榜不需要实时，每天刷新就行
4. **空数据**：没人玩的时候排行榜要有友好提示
5. **时间紧就简化**：如果时间不够，只做每日挑战，排行榜以后再加

## 依赖关系

- **前置依赖**：07号（游戏化积分系统）
- **后续依赖**：无
