# 06 - 错题本系统：模型 + API + 前端页面

## 任务目标

实现完整的错题本功能：
- 答错自动收录
- 按学科/知识点/时间筛选
- 错题重练（随机从错题中抽题练习）
- 标记"已掌握"（从错题本移除）
- 错题详情 + AI讲解入口

## 当前代码状态

### 数据模型

目前还没有专门的错题本表。答题记录在 `user_answers` 表中，通过 `is_correct=false` 可以筛选出错题。

但缺少：
- 错题的单独管理（标记掌握、备注等）
- 错题的知识点聚合统计

### 前端

没有错题本页面。

## 需要做的改动

### Step 1：创建错题本模型

新建 `backend/app/models/wrong_book.py`：

```python
"""
错题本模型
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.core.database import Base


class WrongQuestion(Base):
    """错题本表"""

    __tablename__ = "wrong_questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id"), index=True
    )
    subject: Mapped[str] = mapped_column(String(50), index=True)
    
    # 错误相关
    wrong_count: Mapped[int] = mapped_column(Integer, default=1)  # 答错次数
    first_wrong_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_wrong_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_wrong_answer: Mapped[str] = mapped_column(Text, default="")  # 最近一次错误答案
    
    # 掌握状态
    is_mastered: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否已掌握
    mastered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0)  # 复习次数
    
    # 笔记
    user_note: Mapped[str] = mapped_column(Text, default="")  # 用户笔记
    
    # 关联
    question = relationship("Question", lazy="joined")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
```

### Step 2：错题本Service

新建 `backend/app/services/wrong_book_service.py`：

```python
"""
错题本服务
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wrong_book import WrongQuestion
from app.models.question import Question

logger = logging.getLogger(__name__)


class WrongBookService:
    """错题本服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def add_wrong_question(
        self,
        user_id: uuid.UUID,
        question_id: uuid.UUID,
        subject: str,
        wrong_answer: str = "",
    ) -> WrongQuestion:
        """
        添加错题（如果已存在则答错次数+1）
        
        Args:
            user_id: 用户ID
            question_id: 题目ID
            subject: 学科
            wrong_answer: 错误答案
        
        Returns:
            WrongQuestion 对象
        """
        # 检查是否已经在错题本中
        query = select(WrongQuestion).where(
            WrongQuestion.user_id == user_id,
            WrongQuestion.question_id == question_id,
        )
        result = await self.db.execute(query)
        wq = result.scalar_one_or_none()
        
        if wq:
            # 已存在：更新答错次数和时间
            wq.wrong_count += 1
            wq.last_wrong_at = datetime.utcnow()
            wq.last_wrong_answer = wrong_answer
            wq.is_mastered = False  # 又错了，重置掌握状态
            wq.mastered_at = None
        else:
            # 新增
            wq = WrongQuestion(
                user_id=user_id,
                question_id=question_id,
                subject=subject,
                last_wrong_answer=wrong_answer,
            )
            self.db.add(wq)
        
        await self.db.commit()
        await self.db.refresh(wq)
        return wq
    
    async def get_wrong_questions(
        self,
        user_id: uuid.UUID,
        subject: Optional[str] = None,
        is_mastered: Optional[bool] = None,
        knowledge_point: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[WrongQuestion], int]:
        """
        获取错题列表
        
        Args:
            user_id: 用户ID
            subject: 学科筛选
            is_mastered: 是否已掌握
            knowledge_point: 知识点筛选
            page: 页码
            page_size: 每页数量
        
        Returns:
            (错题列表, 总数)
        """
        query = select(WrongQuestion).where(WrongQuestion.user_id == user_id)
        
        if subject:
            query = query.where(WrongQuestion.subject == subject)
        
        if is_mastered is not None:
            query = query.where(WrongQuestion.is_mastered == is_mastered)
        
        # 知识点筛选需要关联Question表
        if knowledge_point:
            query = query.join(Question).where(
                Question.knowledge_points.op("@>")(f'["{knowledge_point}"]')
            )
        
        # 总数
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0
        
        # 分页
        query = query.order_by(desc(WrongQuestion.last_wrong_at))
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        questions = result.scalars().all()
        
        return list(questions), total
    
    async def mark_mastered(
        self, user_id: uuid.UUID, question_id: uuid.UUID
    ) -> bool:
        """标记为已掌握"""
        query = select(WrongQuestion).where(
            WrongQuestion.user_id == user_id,
            WrongQuestion.question_id == question_id,
        )
        result = await self.db.execute(query)
        wq = result.scalar_one_or_none()
        
        if wq:
            wq.is_mastered = True
            wq.mastered_at = datetime.utcnow()
            await self.db.commit()
            return True
        return False
    
    async def increment_review(
        self, user_id: uuid.UUID, question_id: uuid.UUID
    ) -> None:
        """增加复习次数"""
        query = select(WrongQuestion).where(
            WrongQuestion.user_id == user_id,
            WrongQuestion.question_id == question_id,
        )
        result = await self.db.execute(query)
        wq = result.scalar_one_or_none()
        
        if wq:
            wq.review_count += 1
            await self.db.commit()
    
    async def get_random_wrong_questions(
        self,
        user_id: uuid.UUID,
        subject: Optional[str] = None,
        count: int = 5,
    ) -> List[Question]:
        """
        随机抽取错题用于重练
        
        优先抽取：未掌握的、答错次数多的、最近答错的
        """
        query = (
            select(Question)
            .join(WrongQuestion, WrongQuestion.question_id == Question.id)
            .where(
                WrongQuestion.user_id == user_id,
                WrongQuestion.is_mastered == False,
            )
        )
        
        if subject:
            query = query.where(WrongQuestion.subject == subject)
        
        # 按答错次数降序，随机取N个
        query = query.order_by(desc(WrongQuestion.wrong_count), func.random()).limit(count)
        
        result = await self.db.execute(query)
        questions = result.scalars().all()
        
        return list(questions)
    
    async def get_stats(self, user_id: uuid.UUID) -> dict:
        """
        获取错题本统计数据
        
        Returns:
            {
                total: 总错题数,
                mastered: 已掌握数,
                unmastered: 未掌握数,
                by_subject: { 语文: N, 数学: N, ... },
                need_review_today: 今天需要复习的数量
            }
        """
        # 总数
        total_q = select(func.count()).select_from(
            select(WrongQuestion.id).where(WrongQuestion.user_id == user_id).subquery()
        )
        total = (await self.db.execute(total_q)).scalar() or 0
        
        # 已掌握
        mastered_q = select(func.count()).select_from(
            select(WrongQuestion.id).where(
                WrongQuestion.user_id == user_id,
                WrongQuestion.is_mastered == True,
            ).subquery()
        )
        mastered = (await self.db.execute(mastered_q)).scalar() or 0
        
        # 按学科统计
        by_subject = {}
        subject_q = select(
            WrongQuestion.subject,
            func.count(WrongQuestion.id).label("cnt")
        ).where(
            WrongQuestion.user_id == user_id,
            WrongQuestion.is_mastered == False,
        ).group_by(WrongQuestion.subject)
        
        result = await self.db.execute(subject_q)
        for row in result.all():
            by_subject[row.subject] = row.cnt
        
        # 今天需要复习的（最近3天答错的且未掌握）
        three_days_ago = datetime.utcnow() - timedelta(days=3)
        review_q = select(func.count()).select_from(
            select(WrongQuestion.id).where(
                WrongQuestion.user_id == user_id,
                WrongQuestion.is_mastered == False,
                WrongQuestion.last_wrong_at >= three_days_ago,
            ).subquery()
        )
        need_review = (await self.db.execute(review_q)).scalar() or 0
        
        return {
            "total": total,
            "mastered": mastered,
            "unmastered": total - mastered,
            "by_subject": by_subject,
            "need_review_today": need_review,
        }
```

### Step 3：错题本API

新建 `backend/app/api/v1/wrong_book.py`：

```python
"""
错题本API
"""

import uuid
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.schemas.common import ApiResponse, success_response, paged_response
from app.services.wrong_book_service import WrongBookService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats")
async def get_wrong_book_stats(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取错题本统计数据"""
    service = WrongBookService(db)
    stats = await service.get_stats(user_id)
    return success_response(data=stats)


@router.get("")
async def get_wrong_questions(
    subject: str = None,
    is_mastered: bool = None,
    knowledge_point: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取错题列表"""
    service = WrongBookService(db)
    questions, total = await service.get_wrong_questions(
        user_id=user_id,
        subject=subject,
        is_mastered=is_mastered,
        knowledge_point=knowledge_point,
        page=page,
        page_size=page_size,
    )
    
    # 序列化
    items = []
    for wq in questions:
        q = wq.question
        items.append({
            "id": str(wq.id),
            "question_id": str(q.id),
            "question_text": q.question_text,
            "options": q.options,
            "correct_answer": q.correct_answer,
            "explanation": q.explanation,
            "subject": wq.subject,
            "knowledge_points": q.knowledge_points,
            "difficulty": q.difficulty,
            "wrong_count": wq.wrong_count,
            "review_count": wq.review_count,
            "last_wrong_at": wq.last_wrong_at.isoformat(),
            "is_mastered": wq.is_mastered,
            "user_note": wq.user_note,
        })
    
    return paged_response(items=items, total=total, page=page, page_size=page_size)


@router.post("/{question_id}/master")
async def mark_mastered(
    question_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """标记为已掌握"""
    service = WrongBookService(db)
    result = await service.mark_mastered(user_id, question_id)
    return success_response(data={"success": result})


@router.get("/practice")
async def get_wrong_practice_questions(
    subject: str = None,
    count: int = Query(5, ge=1, le=20),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """随机抽取错题用于重练"""
    service = WrongBookService(db)
    questions = await service.get_random_wrong_questions(
        user_id=user_id,
        subject=subject,
        count=count,
    )
    
    items = [
        {
            "id": str(q.id),
            "question_text": q.question_text,
            "options": q.options,
            "subject": q.subject,
            "difficulty": q.difficulty,
            "knowledge_points": q.knowledge_points,
        }
        for q in questions
    ]
    
    return success_response(data={"questions": items, "count": len(items)})
```

别忘了在主路由中注册这个router。

### Step 4：答题时自动收录

在答题提交接口中，答错时调用 `WrongBookService.add_wrong_question()`。

### Step 5：前端错题本页面

新建 `frontend/src/app/(main)/wrong-book/page.tsx`：

```tsx
"use client";

import { useState, useEffect } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BookOpen, CheckCircle, RefreshCw, ChevronRight, Lightbulb } from "lucide-react";

// 错题本页面
export default function WrongBookPage() {
  const [stats, setStats] = useState<any>(null);
  const [activeSubject, setActiveSubject] = useState("all");
  const [activeTab, setActiveTab] = useState("unmastered");
  const [questions, setQuestions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadStats();
  }, []);

  useEffect(() => {
    loadQuestions();
  }, [activeSubject, activeTab]);

  const loadStats = async () => {
    const res = await fetch("/api/v1/wrong-book/stats");
    const data = await res.json();
    if (data.code === 0) setStats(data.data);
  };

  const loadQuestions = async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (activeSubject !== "all") params.set("subject", activeSubject);
    params.set("is_mastered", activeTab === "mastered" ? "true" : "false");
    params.set("page_size", "50");

    const res = await fetch(`/api/v1/wrong-book?${params}`);
    const data = await res.json();
    if (data.code === 0) setQuestions(data.data.items || []);
    setLoading(false);
  };

  const handleMaster = async (qid: string) => {
    await fetch(`/api/v1/wrong-book/${qid}/master`, { method: "POST" });
    loadQuestions();
    loadStats();
  };

  const handlePractice = async () => {
    // 跳转到错题练习页（或弹出练习面板）
    const params = new URLSearchParams();
    if (activeSubject !== "all") params.set("subject", activeSubject);
    const res = await fetch(`/api/v1/wrong-book/practice?${params}`);
    const data = await res.json();
    if (data.code === 0 && data.data.questions.length > 0) {
      // TODO: 开始错题练习
      alert(`抽到 ${data.data.questions.length} 道错题，开始练习！`);
    }
  };

  if (!stats) return <div className="p-8 text-center">加载中...</div>;

  const subjects = Object.keys(stats.by_subject || {});

  return (
    <div className="container mx-auto px-4 py-6 max-w-4xl">
      {/* 头部统计 */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-4 flex items-center gap-2">
          <BookOpen className="w-7 h-7" />
          错题本
        </h1>
        
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="bg-red-50 rounded-xl p-4 text-center">
            <div className="text-3xl font-bold text-red-600">{stats.unmastered}</div>
            <div className="text-sm text-red-600">待掌握</div>
          </div>
          <div className="bg-green-50 rounded-xl p-4 text-center">
            <div className="text-3xl font-bold text-green-600">{stats.mastered}</div>
            <div className="text-sm text-green-600">已掌握</div>
          </div>
          <div className="bg-blue-50 rounded-xl p-4 text-center">
            <div className="text-3xl font-bold text-blue-600">{stats.need_review_today}</div>
            <div className="text-sm text-blue-600">今日待复习</div>
          </div>
        </div>

        <Button
          onClick={handlePractice}
          className="w-full bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          错题重练
        </Button>
      </div>

      {/* 学科筛选 */}
      <ScrollArea className="whitespace-nowrap mb-4">
        <div className="flex gap-2 pb-2">
          <Badge
            variant={activeSubject === "all" ? "default" : "outline"}
            className="cursor-pointer"
            onClick={() => setActiveSubject("all")}
          >
            全部
          </Badge>
          {subjects.map((s) => (
            <Badge
              key={s}
              variant={activeSubject === s ? "default" : "outline"}
              className="cursor-pointer"
              onClick={() => setActiveSubject(s)}
            >
              {s} ({stats.by_subject[s]})
            </Badge>
          ))}
        </div>
      </ScrollArea>

      {/* 标签页 */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full">
          <TabsTrigger value="unmastered" className="flex-1">
            未掌握 ({stats.unmastered})
          </TabsTrigger>
          <TabsTrigger value="mastered" className="flex-1">
            已掌握 ({stats.mastered})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="unmastered" className="mt-4 space-y-3">
          {loading ? (
            <div className="text-center py-8 text-gray-400">加载中...</div>
          ) : questions.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <CheckCircle className="w-16 h-16 mx-auto mb-2 opacity-30" />
              <p>太棒了，没有错题！</p>
            </div>
          ) : (
            questions.map((wq) => (
              <div key={wq.id} className="bg-white rounded-xl p-4 shadow-sm border">
                <div className="flex justify-between items-start mb-2">
                  <Badge variant="outline" className="text-xs">
                    {wq.subject}
                  </Badge>
                  <Badge
                    variant="destructive"
                    className="text-xs"
                  >
                    错{wq.wrong_count}次
                  </Badge>
                </div>
                <p className="text-sm mb-3 line-clamp-2">{wq.question_text}</p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="flex-1">
                    <Lightbulb className="w-3 h-3 mr-1" />
                    AI讲解
                  </Button>
                  <Button size="sm" className="flex-1" onClick={() => handleMaster(wq.question_id)}>
                    <CheckCircle className="w-3 h-3 mr-1" />
                    已掌握
                  </Button>
                </div>
              </div>
            ))
          )}
        </TabsContent>

        <TabsContent value="mastered" className="mt-4 space-y-3">
          {/* 已掌握列表，类似上面 */}
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

### Step 6：导航菜单加入口

在侧边栏/底部导航中加入"错题本"入口。

## 文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `backend/app/models/wrong_book.py` | 错题本数据模型 |
| 新建 | `backend/app/services/wrong_book_service.py` | 错题本服务逻辑 |
| 新建 | `backend/app/api/v1/wrong_book.py` | 错题本API |
| 修改 | `backend/app/api/v1/user_courses.py` | 答错自动收录 |
| 修改 | 主路由注册 | 注册wrong_book router |
| 新建 | `frontend/src/app/(main)/wrong-book/page.tsx` | 错题本页面 |
| 修改 | 导航组件 | 加入错题本入口 |

## 验收标准

- [ ] 答错的题自动出现在错题本中
- [ ] 错题列表支持按学科筛选
- [ ] 可以标记"已掌握"
- [ ] "错题重练"能随机抽取错题
- [ ] 统计数据正确（总数、已掌握、待复习）
- [ ] 前端页面美观，交互流畅
- [ ] 每道错题有"AI讲解"入口

## 注意事项

1. **数据库迁移**：新建模型后需要生成migration并执行
2. **错题去重**：同一道题多次答错只增加次数，不重复创建
3. **性能考虑**：错题多了之后，随机抽取要注意性能（加索引）
4. **练习流程**：错题重练的答题流程可以复用学习页的组件
5. **已掌握的不消失**：已掌握的题还在列表中（有单独的tab），方便复习

## 依赖关系

- **前置依赖**：05号（答题反馈增强）
- **后续依赖**：08号（行为建模）
