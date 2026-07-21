# 02 - API层接接入出题 + Tools持久化实现

## 任务目标

1. 把 `QuestionPipeline` 接到 `POST /generate` API上，让前端真的能调用AI出题
2. 实现 `QuestionMemoryTool` 和 `QuestionSaveTool` 的数据库持久化逻辑
3. 让出题相关的2张"死表"（`generated_questions`, `generated_batches`）开始有数据写入

> 关于另外4张表：
> - `tool_call_logs`：01号简化了Tool层，此表不再需要
> - `evolution_records`：01号删除了SummaryAgent的自进化功能，此表不再需要
> - `harness_runs` 和 `error_logs`：03号TutorHarness保留了审计日志和错误处理机制，这两张表由03号负责写入

## 当前代码状态

### API层（未接通）

文件：`backend/app/api/v1/questions.py`

```python
@router.post("/generate")
async def generate_questions(
    body: QuestionGenerateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # TODO: 调用 AI Harness 执行实际生成
    # 目前只创建批次记录，返回占位数据
    batch = GeneratedQuestionBatch(
        course_id=body.course_id,
        created_by=user_id,
        status="pending",
        # ...
    )
    db.add(batch)
    await db.commit()
    return success_response(data={"batch_id": str(batch.id), "questions": []})
```

### QuestionMemoryTool（返回空）

文件：`backend/app/ai/tools/question_memory_tool.py`

```python
class QuestionMemoryTool:
    async def get_recent_questions(self, subject, user_id=None, limit=20):
        # TODO: 从数据库查询最近做过的题目
        return []  # 占位

    async def get_wrong_questions(self, subject, user_id, limit=20):
        # TODO: 查询错题
        return []  # 占位

    async def get_skill_level(self, subject, user_id):
        # TODO: 查询技能水平
        return {"subject": subject, "level": "intermediate"}  # 占位
```

### QuestionSaveTool（永远返回0）

文件：`backend/app/ai/tools/question_save_tool.py`

```python
class QuestionSaveTool:
    async def save_batch(self, questions, subject, age_group, course_id=None, user_id=None):
        # TODO: 批量保存生成的题目到数据库
        return {"saved_count": 0, "batch_id": None}  # 占位
```

### 相关模型表

文件：`backend/app/models/ai_generated.py`

- `GeneratedQuestionBatch` — 生成批次表
- `GeneratedQuestion` — 生成的题目表
- `ToolCallLog` — Tool调用日志
- `HarnessRun` — 运行记录
- `ErrorLog` — 错误日志
- `EvolutionRecord` — 进化记录

这些表的模型定义已经写好了，但从来没有数据写入。

## 需要做的改动

### Step 1：实现 QuestionMemoryTool

修改 `backend/app/ai/tools/question_memory_tool.py`：

```python
"""
题目记忆检索Tool：从数据库查询历史题、错题、技能水平
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question
from app.models.user_answer import UserAnswer

logger = logging.getLogger(__name__)


class QuestionMemoryTool:
    """题目记忆检索工具"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_recent_questions(
        self, 
        subject: str, 
        user_id: Optional[str] = None, 
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        查询最近做过的题目，用于避免重复出题
        
        Args:
            subject: 学科
            user_id: 用户ID（None则查全局）
            limit: 返回数量
        
        Returns:
            题目列表，每个包含 id, question, topic, difficulty, knowledge_points
        """
        try:
            query = (
                select(Question)
                .where(Question.subject == subject)
                .order_by(desc(Question.created_at))
                .limit(limit)
            )
            
            # 如果指定了用户，查该用户做过的题
            if user_id:
                query = (
                    select(Question)
                    .join(UserAnswer, UserAnswer.question_id == Question.id)
                    .where(
                        Question.subject == subject,
                        UserAnswer.user_id == user_id,
                    )
                    .order_by(desc(UserAnswer.answered_at))
                    .limit(limit)
                )
            
            result = await self.db.execute(query)
            questions = result.scalars().all()
            
            return [
                {
                    "id": str(q.id),
                    "question": q.question_text[:100],  # 截断，省token
                    "topic": q.knowledge_points[0] if q.knowledge_points else "",
                    "difficulty": q.difficulty,
                    "knowledge_points": q.knowledge_points or [],
                }
                for q in questions
            ]
        except Exception as e:
            logger.error(f"查询最近题目失败: {e}")
            return []
    
    async def get_wrong_questions(
        self,
        subject: str,
        user_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        查询用户的错题，用于生成针对性练习
        
        Args:
            subject: 学科
            user_id: 用户ID
            limit: 返回数量
        
        Returns:
            错题列表
        """
        try:
            query = (
                select(Question)
                .join(UserAnswer, UserAnswer.question_id == Question.id)
                .where(
                    Question.subject == subject,
                    UserAnswer.user_id == user_id,
                    UserAnswer.is_correct == False,
                )
                .order_by(desc(UserAnswer.answered_at))
                .limit(limit)
            )
            
            result = await self.db.execute(query)
            questions = result.scalars().all()
            
            return [
                {
                    "id": str(q.id),
                    "question": q.question_text[:100],
                    "knowledge_points": q.knowledge_points or [],
                    "difficulty": q.difficulty,
                }
                for q in questions
            ]
        except Exception as e:
            logger.error(f"查询错题失败: {e}")
            return []
    
    async def get_skill_level(self, subject: str, user_id: str) -> Dict[str, Any]:
        """
        评估用户的技能水平，用于调整出题难度
        
        算法：根据最近30天的正确率和题目难度，计算综合水平
        
        Args:
            subject: 学科
            user_id: 用户ID
        
        Returns:
            { level: beginner/intermediate/advanced, accuracy: float, total_answered: int }
        """
        try:
            # 查询最近30天的答题记录
            from datetime import datetime, timedelta
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            query = select(UserAnswer).where(
                UserAnswer.user_id == user_id,
                UserAnswer.answered_at >= thirty_days_ago,
            )
            
            # 如果有question关联，按学科过滤
            # 简化处理：先查所有，再关联
            result = await self.db.execute(query)
            answers = result.scalars().all()
            
            if not answers:
                return {"level": "intermediate", "accuracy": 0.5, "total_answered": 0}
            
            # 计算正确率
            correct_count = sum(1 for a in answers if a.is_correct)
            accuracy = correct_count / len(answers)
            
            # 简单的水平判定
            if accuracy >= 0.8:
                level = "advanced"
            elif accuracy >= 0.5:
                level = "intermediate"
            else:
                level = "beginner"
            
            return {
                "level": level,
                "accuracy": accuracy,
                "total_answered": len(answers),
            }
        except Exception as e:
            logger.error(f"查询技能水平失败: {e}")
            return {"level": "intermediate", "accuracy": 0.5, "total_answered": 0}
```

### Step 2：实现 QuestionSaveTool

修改 `backend/app/ai/tools/question_save_tool.py`：

```python
"""
题目保存Tool：批量保存生成的题目到数据库
"""

import uuid
import hashlib
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_generated import GeneratedQuestion, GeneratedQuestionBatch
from app.models.question import Question

logger = logging.getLogger(__name__)


class QuestionSaveTool:
    """题目保存工具"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def _compute_hash(self, question_text: str) -> str:
        """计算题目的哈希值，用于去重"""
        return hashlib.md5(question_text.encode("utf-8")).hexdigest()
    
    async def save_batch(
        self,
        questions: List[Dict[str, Any]],
        subject: str,
        age_group: str,
        course_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        批量保存生成的题目
        
        Args:
            questions: 题目列表
            subject: 学科
            age_group: 年龄段
            course_id: 课程ID
            user_id: 用户ID
        
        Returns:
            { saved_count: int, batch_id: str, failed_count: int }
        """
        if not questions:
            return {"saved_count": 0, "batch_id": None, "failed_count": 0}
        
        try:
            # 1. 创建批次记录
            batch = GeneratedQuestionBatch(
                course_id=course_id,
                created_by=user_id,
                subject=subject,
                age_group=age_group,
                total_count=len(questions),
                status="completed",
            )
            self.db.add(batch)
            await self.db.flush()  # 获取batch.id
            
            # 2. 逐条保存题目
            saved_count = 0
            failed_count = 0
            
            for q in questions:
                try:
                    question_text = q.get("question", "")
                    if not question_text:
                        failed_count += 1
                        continue
                    
                    # 计算哈希
                    sim_hash = self._compute_hash(question_text)
                    
                    # 构造选项
                    options = q.get("options", [])
                    if options and isinstance(options[0], dict):
                        # 已经是 {label, content} 格式
                        options_json = options
                    elif options and isinstance(options[0], str):
                        # 纯字符串数组，转成对象格式
                        options_json = [
                            {"label": chr(65 + i), "content": opt}
                            for i, opt in enumerate(options)
                        ]
                    else:
                        options_json = []
                    
                    gen_q = GeneratedQuestion(
                        batch_id=batch.id,
                        question_type=q.get("type", "choice"),
                        question_text=question_text,
                        options=options_json,
                        correct_answer=q.get("answer", ""),
                        explanation=q.get("explanation", ""),
                        difficulty=q.get("difficulty", "intermediate"),
                        knowledge_points=q.get("knowledge_points", []),
                        subject=subject,
                        age_group=age_group,
                        similarity_hash=sim_hash,
                        quality_score=q.get("quality_score", 0.8),
                        safety_score=q.get("safety_score", 1.0),
                    )
                    self.db.add(gen_q)
                    saved_count += 1
                    
                except Exception as e:
                    logger.error(f"保存单题失败: {e}")
                    failed_count += 1
                    continue
            
            # 3. 更新批次状态
            batch.saved_count = saved_count
            batch.failed_count = failed_count
            
            await self.db.commit()
            
            logger.info(f"保存题目批次：{saved_count}道成功，{failed_count}道失败")
            
            return {
                "saved_count": saved_count,
                "batch_id": str(batch.id),
                "failed_count": failed_count,
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"保存题目批次失败: {e}")
            return {"saved_count": 0, "batch_id": None, "failed_count": len(questions)}
```

### Step 3：接通 API 层

修改 `backend/app/api/v1/questions.py` 中的 `POST /generate`：

```python
from app.ai.question_pipeline import QuestionPipeline

# ...

@router.post("/generate")
async def generate_questions(
    body: QuestionGenerateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    AI生成题目接口
    
    调用简化后的2层出题流水线：生成 + 评估
    """
    try:
        pipeline = QuestionPipeline(db)
        
        result = await pipeline.generate(
            subject=body.subject,
            age_group=body.age_group or "9-12",
            count=body.count or 5,
            question_type=body.question_type or "choice",
            difficulty=body.difficulty or "intermediate",
            knowledge_points=body.knowledge_points or [],
            course_id=body.course_id,
            user_id=user_id,
        )
        
        return success_response(
            data={
                "questions": result["questions"],
                "total_generated": result["total_generated"],
                "pass_rate": result["pass_rate"],
            },
            message=f"成功生成 {result['total_generated']} 道题目",
        )
        
    except Exception as e:
        logger.error(f"生成题目失败: {e}")
        return error_response(message=f"生成题目失败: {str(e)}")
```

同时确保 `QuestionGenerateRequest` schema 包含需要的字段：
- subject (必填)
- age_group
- count
- question_type
- difficulty
- knowledge_points
- course_id

### Step 4：Tool调用日志（可选，先简单做）

在 `QuestionMemoryTool` 和 `QuestionSaveTool` 的每个方法中，增加日志记录到 `tool_call_logs` 表。

先简单做——用Python logging 输出就行，表的写入可以后面再加。重点是先让核心功能跑通。

## 文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 修改 | `backend/app/ai/tools/question_memory_tool.py` | 实现3个查询方法 |
| 修改 | `backend/app/ai/tools/question_save_tool.py` | 实现批量保存 |
| 修改 | `backend/app/api/v1/questions.py` | 接通 POST /generate |
| 验证 | `backend/app/schemas/question.py` | 确认请求体字段齐全 |

## 验收标准

- [ ] `POST /api/v1/questions/generate` 调用后能返回真实的题目列表
- [ ] generated_questions 表中有新记录
- [ ] generated_batches 表中有新的批次记录
- [ ] similarity_hash 字段有值
- [ ] QuestionMemoryTool.get_recent_questions 能返回历史题
- [ ] QuestionMemoryTool.get_wrong_questions 能返回错题
- [ ] 生成失败时有合理的错误提示，不崩

## 注意事项

1. **Question模型字段要对应**：保存时注意字段名和类型，特别是options是JSON格式
2. **事务处理**：保存批次时用事务，单题失败不影响其他题
3. **异步注意**：所有DB操作都是async的，记得await
4. **导入路径**：确认Question和UserAnswer模型的导入路径
5. **降级策略**：Pipeline生成失败时返回空列表，不要让API 500

## 依赖关系

- **前置依赖**：01号（出题系统简化完成）
- **后续依赖**：03号（多Agent辅导系统）、05号（错题本）等
