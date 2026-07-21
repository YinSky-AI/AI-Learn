# 01 - 出题系统简化：8层Agent → 2层（生成+评估）

## 任务目标

把当前 `backend/app/ai/` 目录下复杂的8层Agent出题系统，简化为**2层流水线**：生成层 + 评估层。

**为什么要简化？**
- 原来的L1意图理解、L2题型规划都是多余的——前端已经传了科目/年级/题型/数量，后端不需要再让LLM"理解"一遍
- L5质检和L6安全审查可以合并为一次评估调用，不必每题调2次LLM
- PID控制器（L7）在出题场景下价值不大，用简单阈值判断就行
- 简化后：一次出题从50+次LLM调用降到3-5次，成本降10倍，速度快5倍

**保留什么？**
- 保留 Agent 基类（BaseAgent）和 Provider——代码质量不错，后面辅导系统还要用
- 保留 Prompt 模板——可以改改继续用
- 保留数据库模型表——结构是合理的

## 当前代码状态

### 当前架构（8层，位于 backend/app/ai/）

```
harness.py                    ← 总编排器，8层串行+3轮循环
agents/
  base.py                     ← Agent基类（保留，这个写得很好）
  course_intent.py            ← L1 意图理解（删除）
  question_planner.py         ← L2 题型规划（删除）
  question_memory.py          ← L3 记忆检索（简化后合并到生成层）
  question_generator.py       ← L4 题目生成（保留并改造）
  quality_checker.py          ← L5 快速质检（合并到评估层）
  safety_auditor.py           ← L6 安全审查（合并到评估层）
  quality_reviewer.py         ← L6 深度评审（删除）
  summary_agent.py            ← L8 会话总结（删除）
feedback_aggregator.py        ← PID控制器（删除）
error_logger.py               ← 错误日志（保留）
prompts/
  course_intent.py            ← 删除
  question_planning.py        ← 删除
  question_generation.py      ← 保留并修改
  quality_check.py            ← 合并到评估prompt
  safety_audit.py             ← 合并到评估prompt
  summary.py                  ← 删除
tools/
  question_memory_tool.py     ← 保留，简化后生成层调用
  question_save_tool.py       ← 保留
  skill_retrieval_tool.py     ← 删除
  error_reporting_tool.py     ← 删除
```

### BaseAgent 基类（保留）

`backend/app/ai/agents/base.py` 第136行：
```python
async def execute(self, **kwargs) -> Any:
    """标准执行流程：构建Prompt → 调用LLM → 解析响应"""
    messages = self._build_prompt(**kwargs)
    response = await self._call_llm(messages)
    return self._parse_response(response, **kwargs)
```

这个基类写得很好，保留不动。后面的辅导Agent也用这个基类。

### Provider（保留）

`backend/app/ai/provider.py` 用 `AsyncOpenAI` 调DeepSeek，有指数退避重试，保留不动。

## 需要做的改动

### Step 1：创建新的简化出题模块

在 `backend/app/ai/` 下新建 `question_pipeline.py`：

```python
"""
简化出题流水线：生成层 + 评估层，最多2轮迭代

架构：
  GeneratorAgent  →  生成题目（1次LLM调用，一次生成N道）
  EvaluatorAgent  →  评估题目质量+安全（1次LLM调用，一次评估N道）
  反馈循环        →  不通过的题让Generator重生成，最多2轮
"""

import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.base import BaseAgent
from app.ai.tools.question_memory_tool import QuestionMemoryTool
from app.ai.tools.question_save_tool import QuestionSaveTool
from app.ai.prompts.question_generation import build_generation_prompt
from app.ai.prompts.question_evaluation import build_evaluation_prompt

logger = logging.getLogger(__name__)


class GeneratorAgent(BaseAgent):
    """题目生成Agent：一次调用生成多道题"""
    
    def __init__(self):
        super().__init__(temperature=0.8)
    
    def _build_prompt(self, **kwargs) -> list:
        subject = kwargs.get("subject", "")
        age_group = kwargs.get("age_group", "")
        question_type = kwargs.get("question_type", "choice")
        count = kwargs.get("count", 5)
        difficulty = kwargs.get("difficulty", "intermediate")
        knowledge_points = kwargs.get("knowledge_points", [])
        avoid_topics = kwargs.get("avoid_topics", [])
        
        system_prompt, user_prompt = build_generation_prompt(
            subject=subject,
            age_group=age_group,
            question_type=question_type,
            count=count,
            difficulty=difficulty,
            knowledge_points=knowledge_points,
            avoid_topics=avoid_topics,
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    
    def _parse_response(self, response: str, **kwargs) -> List[Dict]:
        # 解析JSON数组，返回题目列表
        import json
        try:
            # 尝试提取JSON数组
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                questions = json.loads(json_str)
                return questions
        except Exception as e:
            logger.error(f"解析生成结果失败: {e}")
        return []


class EvaluatorAgent(BaseAgent):
    """题目评估Agent：一次评估多道题的质量和安全性"""
    
    def __init__(self):
        super().__init__(temperature=0.1)  # 低温度确保评估一致性
    
    def _build_prompt(self, **kwargs) -> list:
        questions = kwargs.get("questions", [])
        subject = kwargs.get("subject", "")
        age_group = kwargs.get("age_group", "")
        
        system_prompt, user_prompt = build_evaluation_prompt(
            questions=questions,
            subject=subject,
            age_group=age_group,
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    
    def _parse_response(self, response: str, **kwargs) -> Dict:
        # 解析评估结果：{ passed: [indexes], failed: [{index, reason, type}] }
        import json
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                result = json.loads(json_str)
                return result
        except Exception as e:
            logger.error(f"解析评估结果失败: {e}")
        return {"passed": [], "failed": []}


class QuestionPipeline:
    """简化出题流水线"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.generator = GeneratorAgent()
        self.evaluator = EvaluatorAgent()
        self.memory_tool = QuestionMemoryTool(db)
        self.save_tool = QuestionSaveTool(db)
    
    async def generate(
        self,
        subject: str,
        age_group: str,
        count: int = 5,
        question_type: str = "choice",
        difficulty: str = "intermediate",
        knowledge_points: Optional[List[str]] = None,
        course_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        生成题目主入口
        
        Args:
            subject: 学科
            age_group: 年龄段
            count: 题目数量
            question_type: 题型 (choice/multi_choice/true_false/fill_blank/short_answer)
            difficulty: 难度 (beginner/intermediate/advanced)
            knowledge_points: 知识点列表
            course_id: 课程ID
            user_id: 用户ID
        
        Returns:
            { questions: [...], total_generated: N, pass_rate: float }
        """
        knowledge_points = knowledge_points or []
        max_rounds = 2
        all_questions = []
        remaining = count
        
        # Step 1: 查询历史题，避免重复
        history = await self.memory_tool.get_recent_questions(
            subject=subject,
            user_id=user_id,
            limit=count * 3,
        )
        avoid_topics = [q.get("topic", "") for q in history if q.get("topic")]
        
        for round_num in range(max_rounds):
            if remaining <= 0:
                break
            
            # Step 2: 生成题目
            generated = await self.generator.execute(
                subject=subject,
                age_group=age_group,
                question_type=question_type,
                count=remaining,
                difficulty=difficulty,
                knowledge_points=knowledge_points,
                avoid_topics=avoid_topics,
            )
            
            if not generated:
                logger.warning(f"第{round_num+1}轮生成失败")
                break
            
            # Step 3: 评估题目
            eval_result = await self.evaluator.execute(
                questions=generated,
                subject=subject,
                age_group=age_group,
            )
            
            passed_indexes = eval_result.get("passed", [])
            failed_list = eval_result.get("failed", [])
            
            # 收集通过的题
            passed_questions = [generated[i] for i in passed_indexes if i < len(generated)]
            all_questions.extend(passed_questions)
            remaining = count - len(all_questions)
            
            # 收集不通过的原因，下一轮避开
            failed_reasons = [f.get("reason", "") for f in failed_list]
            if failed_reasons:
                avoid_topics.extend(failed_reasons[:5])
            
            logger.info(
                f"第{round_num+1}轮：生成{len(generated)}道，"
                f"通过{len(passed_questions)}道，通过率{len(passed_questions)/len(generated)*100:.0f}%"
            )
        
        # 如果不够数量，用最后一轮的题补足（哪怕没通过评估）
        if len(all_questions) < count and generated:
            # 从评估结果中找质量问题而非安全问题的题
            quality_failed = [
                generated[f["index"]] 
                for f in failed_list 
                if f.get("type") == "quality" and f["index"] < len(generated)
            ]
            all_questions.extend(quality_failed[:count - len(all_questions)])
        
        # 截取到指定数量
        final_questions = all_questions[:count]
        
        # Step 4: 保存到数据库（如果有save_tool的实现）
        try:
            await self.save_tool.save_batch(
                questions=final_questions,
                subject=subject,
                age_group=age_group,
                course_id=course_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.error(f"保存题目失败: {e}")
            # 保存失败不影响返回结果
        
        return {
            "questions": final_questions,
            "total_generated": len(final_questions),
            "pass_rate": len(final_questions) / max(count, 1),
        }
```

### Step 2：创建评估Prompt

在 `backend/app/ai/prompts/` 下新建 `question_evaluation.py`：

```python
"""
题目评估Prompt：同时评估质量和安全性，一次评估多道题
"""


def build_evaluation_prompt(questions: list, subject: str, age_group: str) -> tuple:
    """
    构建评估Prompt
    
    Returns: (system_prompt, user_prompt)
    """
    system_prompt = f"""你是一位严格的K12教育内容审核专家，负责评估AI生成的题目。
你需要从以下4个维度评估每道题：

1. **正确性**：答案是否正确，解析是否合理
2. **适龄性**：难度和表述是否适合{age_group}年龄段的学生
3. **安全性**：是否包含敏感、暴力、色情、政治等不适宜内容
4. **质量**：题目表述是否清晰，选项是否有区分度，是否有歧义

对每道题给出"通过"或"不通过"的判断，不通过的要说明原因和类型（quality/safety）。

只返回JSON，格式如下：
{{
  "passed": [0, 2, 5],
  "failed": [
    {{"index": 1, "reason": "选项B和D含义相近，缺乏区分度", "type": "quality"}},
    {{"index": 3, "reason": "涉及不适宜内容", "type": "safety"}}
  ]
}}

注意：index是题目在列表中的索引，从0开始。只返回JSON，不要其他文字。"""

    # 格式化题目列表
    questions_text = ""
    for i, q in enumerate(questions):
        q_type = q.get("type", "choice")
        q_text = q.get("question", "")
        q_options = q.get("options", [])
        q_answer = q.get("answer", "")
        q_explanation = q.get("explanation", "")
        
        options_text = ""
        if q_options:
            for j, opt in enumerate(q_options):
                label = chr(65 + j) if isinstance(opt, str) else opt.get("label", "")
                content = opt if isinstance(opt, str) else opt.get("content", "")
                options_text += f"      {label}. {content}\n"
        
        questions_text += f"""
题目 {i}（{q_type}）：
  题干：{q_text}
  选项：
{options_text}  答案：{q_answer}
  解析：{q_explanation}
"""

    user_prompt = f"""请评估以下{len(questions)}道{subject}题目的质量和安全性：

{questions_text}

请严格按照要求的JSON格式返回评估结果。"""

    return system_prompt, user_prompt
```

### Step 3：修改生成Prompt

修改 `backend/app/ai/prompts/question_generation.py`，让它一次生成多道题（而不是一道），并且去掉多余的层级。

**核心改动**：
- 一次prompt生成N道题，而不是循环调用N次
- 去掉course_intent和planner相关的内容
- 直接接收subject/age_group/count等参数

保留原有的适龄性要求和题目结构定义，这些写得不错。

### Step 4：删除不需要的文件

删除以下文件（它们是8层架构的冗余部分）：
```
agents/course_intent.py
agents/question_planner.py
agents/quality_checker.py
agents/safety_auditor.py
agents/quality_reviewer.py
agents/summary_agent.py
agents/question_memory.py    ← 记忆检索合并到pipeline里，不需要单独的Agent
feedback_aggregator.py
prompts/course_intent.py
prompts/question_planning.py
prompts/quality_check.py
prompts/safety_audit.py
prompts/summary.py
tools/skill_retrieval_tool.py
tools/error_reporting_tool.py
# 注意：error_logger.py 不删除！03号TutorHarness仍需要它
```

> 注意：删除前确认这些文件没有被其他地方引用。主要检查ai.py。

### Step 5：保留 harness.py 文件，但替换其中的 AIHarness 类

**不要删除 `harness.py` 文件，但文件内容需要大改。**

原 `harness.py` 中的 `AIHarness` 类（8层出题编排器）已废弃，因为出题功能已由 `question_pipeline.py` 接管。但文件本身的框架机制很好，要保留复用：

- **保留复用**：运行上下文 `_run_context`、日志审计 `_audit_tool`、错误处理 `_error_logger`、Agent初始化模式
- **替换内容**：`AIHarness` 类改为 `TutorHarness` 类（4Agent辅导编排器）
- **结果**：`harness.py` 中只有一个 `TutorHarness` 类，不再有 `AIHarness` 类

形成**双Harness架构**：
- `backend/app/ai/question_pipeline.py` — `QuestionPipeline`（2层出题）
- `backend/app/ai/harness.py` — `TutorHarness`（4Agent辅导）

> 如果 grep 发现 `harness.py` 被其他地方 import（除了 `ai.py` 和 03/04号相关文件），先记下来，03号改造时统一处理。

### Step 6：在 `backend/app/ai/__init__.py` 中导出 QuestionPipeline

确保 `backend/app/ai/__init__.py` 中有：
```python
from app.ai.question_pipeline import QuestionPipeline

__all__ = ["QuestionPipeline"]
```
这样02号的 `from app.ai.question_pipeline import QuestionPipeline` 才能正常导入。

## 文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `backend/app/ai/question_pipeline.py` | 简化后的2层出题流水线 |
| 新建 | `backend/app/ai/prompts/question_evaluation.py` | 评估Prompt |
| 修改 | `backend/app/ai/prompts/question_generation.py` | 改为一次生成多道题 |
| 改造 | `backend/app/ai/harness.py` | AIHarness类替换为TutorHarness |
| 修改 | `backend/app/ai/__init__.py` | 导出QuestionPipeline |
| 删除 | `backend/app/ai/agents/course_intent.py` | L1 |
| 删除 | `backend/app/ai/agents/question_planner.py` | L2 |
| 删除 | `backend/app/ai/agents/question_memory.py` | L3（合并到pipeline） |
| 删除 | `backend/app/ai/agents/quality_checker.py` | L5（合并到评估） |
| 删除 | `backend/app/ai/agents/safety_auditor.py` | L6（合并到评估） |
| 删除 | `backend/app/ai/agents/quality_reviewer.py` | L6（删除） |
| 删除 | `backend/app/ai/agents/summary_agent.py` | L8（删除） |
| 删除 | `backend/app/ai/feedback_aggregator.py` | PID控制器（删除） |
| 删除 | `backend/app/ai/prompts/course_intent.py` | 配套prompt |
| 删除 | `backend/app/ai/prompts/question_planning.py` | 配套prompt |
| 删除 | `backend/app/ai/prompts/quality_check.py` | 配套prompt |
| 删除 | `backend/app/ai/prompts/safety_audit.py` | 配套prompt |
| 删除 | `backend/app/ai/prompts/summary.py` | 配套prompt |
| 删除 | `backend/app/ai/tools/skill_retrieval_tool.py` | 未使用的tool |
| 删除 | `backend/app/ai/tools/error_reporting_tool.py` | 未使用的tool |

## 验收标准

- [ ] `QuestionPipeline.generate()` 能正常调用，返回题目列表
- [ ] 一次出题的LLM调用次数不超过 2 + 1 = 3次（生成×最多2轮 + 评估×1轮/生成1轮）
- [ ] 评估Agent能正确识别明显错误的题目（比如答案不对的）
- [ ] 删除旧文件后项目不报错（grep确认没有引用）
- [ ] BaseAgent基类和Provider保留不动
- [ ] 生成的题目包含：题干、选项、答案、解析、知识点、难度

## 注意事项

1. **删除文件前先 grep 引用**：确保要删除的文件没有被import
2. **生成Prompt要控制输出格式**：必须让LLM返回严格的JSON数组，解析失败是最大的坑
3. **评估要低temperature**：0.1以下，确保同样的题每次评估结果一致
4. **失败降级**：如果评估解析失败，默认全部通过（不能因为评估坏了就出不了题）
5. **保存是可选的**：save_tool可能还没实现，用try-except包起来，保存失败不影响返回

## 依赖关系

- **前置依赖**：无（这是第1个做的）
- **后续依赖**：02号（API层接入）依赖这个
