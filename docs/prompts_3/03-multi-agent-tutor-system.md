# 03 - 多Agent辅导系统：架构设计与4个Agent实现

## 任务目标

这是整个项目**最有技术亮点**的部分。把多Agent系统用在真正适合的场景——**AI学习辅导对话**。

设计4个不同角色的Agent，像**真正的培训机构辅导团队**一样协作：

| Agent | 角色 | 职责 |
|-------|------|------|
| **ExplainerAgent** | 主讲老师 | 用学生能听懂的语言讲解知识点 |
| **SocratesAgent** | 助教/提问老师 | 苏格拉底式提问，检验学生理解 |
| **DiagnoserAgent** | 学管/诊断老师 | 分析学生掌握程度，决定教学策略 |
| **EncouragerAgent** | 班主任/心理老师 | 情绪支持，调整学习节奏 |

**核心机制：Agent之间能互相交流**

这不是"4个角色轮流说话"，而是**真正的协作**：

- **共享状态（SharedState）**：所有Agent共享一块"黑板"，记录学生画像、教学策略、知识点掌握度
- **Agent间留言**：Diagnoser诊断出"学生基础薄弱" → 给Explainer留言"请从最基础讲" → Explainer下轮执行时读到留言，调整讲解方式
- **教学策略联动**：诊断结果自动更新教学策略（approach/pace/focus_areas），所有Agent都能感知
- **情绪感知**：学生连续答错 → 挫败感上升 → Encourager加强鼓励 → Explainer更耐心

**为什么这比单Agent好？**
- 像真正的培训机构多对一辅导，不是一个人干所有活
- Diagnoser的发现能真正影响Explainer的行为（不是各干各的）
- 学生体验更连贯——辅导团队有记忆、有协作、有策略调整
- 面试/毕设讲故事的素材多很多："多Agent协作+共享状态+策略联动"

**与洋葱学园的对标和差异化**

洋葱学园（2025年11月发布"自学破壁计划1.0"）已落地6智能体架构：AI自学大师、AI私人助教、AI思维教练、AI规划导师、AI自律伙伴、AI情感树洞。月互动量超2600万次，已进入2000+所学校。

我们的4个Agent与洋葱学园6智能体的对应关系：

| 洋葱学园 | 我们的Agent | 对应关系 |
|----------|------------|---------|
| AI自学大师 + AI私人助教 | Explainer（主讲老师） | 讲解+答疑 |
| AI思维教练 | Socrates（助教提问） | 苏格拉底式引导 |
| AI规划导师 | Diagnoser（诊断师） | 学情诊断+策略调整 |
| AI情感树洞 + AI自律伙伴 | Encourager（鼓励师） | 情感支持+正向反馈 |

**核心差异化**：洋葱学园的6个智能体是独立功能模块，彼此之间不传递信息。而我们的4个Agent通过**SharedState共享状态**和**Agent间留言**实现深度协作——Diagnoser的诊断结果能直接影响Explainer的讲解策略，Encourager能感知学生的挫败感变化。这才是真正的"多对一"辅导团队，而非6个独立工具的简单组合。

## 当前代码状态

### 现有的AI对话实现

文件：`backend/app/api/v1/ai.py`

当前的实现是**单Prompt、单角色**的：
```python
def _build_system_prompt(context):
    # 根据年龄段调整语气
    # 单一角色："你是一位耐心的老师"
    ...

@router.post("/chat")
async def chat(body: ChatRequest):
    # 直接调LLM，单轮对话
    ...
```

只有一个"AI助手"角色，没有多Agent协作。

### BaseAgent基类（已存在，直接用）

文件：`backend/app/ai/agents/base.py`

这个基类可以直接复用，4个辅导Agent都继承它。

### Provider（已存在，直接用）

文件：`backend/app/ai/provider.py`

直接复用。

## 需要做的改动

### Step 0：创建共享状态层（SharedState）

**这是整个多Agent协作的基础。没有这个，Agent之间就是孤岛。**

新建 `backend/app/ai/shared_state.py`：

设计一个所有Agent共享的"黑板"，包含：

1. **StudentProfile**：学生画像
   - `age_group`, `current_subject`, `current_topic`
   - `overall_mastery`（整体掌握度 0-1）
   - `frustration_level`（挫败感 0-1，连续答错会上升）
   - `engagement_level`（参与度 0-1）

2. **TeachingStrategy**：当前教学策略（由Diagnoser更新，所有Agent读取）
   - `approach`: standard / simplified / deep / challenge / review
   - `pace`: slow / normal / fast
   - `focus_areas`: 重点讲哪些知识点（list）
   - `avoid_areas`: 跳过哪些（list）
   - `next_agent`: 下一个该谁说话

3. **TopicMastery**：各知识点的掌握度 `{topic: {level, attempt_count, correct_count}}`
   - 用指数移动平均更新：`new_level = old_level * 0.7 + current * 0.3`
   - 每次答题后调用 `update_mastery(topic, is_correct)` 自动更新

4. **AgentMessages**：Agent间的留言板
   - `post_agent_message(from_agent, to_agent, content)`：A给B留言
   - `get_messages_for(agent_name)`：B读取所有给自己的留言
   - 示例：Diagnoser诊断后 → `post_agent_message("diagnoser", "explainer", "学生掌握度<30%，请从最基础讲")` → Explainer下轮执行时读到这条留言，在Prompt中增加"注意：学生基础薄弱，请用最简单的方式讲"

5. **ConversationMemory**：对话历史（最近10轮）

**关键方法**：
- `to_prompt_context()`：把共享状态格式化为字符串，注入每个Agent的Prompt中。包含学生画像、当前教学策略、知识点掌握度、其他Agent给自己的留言。
- `update_mastery(topic, is_correct)`：更新知识点掌握度
- `update_strategy(approach, pace, reason)`：更新教学策略

> 共享状态是一个纯Python dataclass，不依赖数据库，作为参数传给每个Agent的execute()。

### Step 1：创建4个辅导Agent（每个都要能读写共享状态）

在 `backend/app/ai/agents/` 下新建4个文件。**所有Agent的execute()都要接收并读写shared_state。**

#### 关键改造点（适用于全部4个Agent）

每个Agent的改造遵循相同模式：

1. `_build_prompt()` 中增加 `shared_state` 参数
2. 调用 `shared_state.to_prompt_context()` 获取状态文本，注入Prompt
3. 调用 `shared_state.get_messages_for(self.name)` 读取其他Agent给自己的留言，注入Prompt
4. `_parse_response()` 中根据结果更新共享状态或给其他Agent留言

#### 3.1 ExplainerAgent — 主讲老师（带共享状态）

文件：`backend/app/ai/agents/tutor/explainer.py`

```python
"""
讲解老师Agent：用学生能听懂的语言讲解知识点

特点：
- 善于用比喻和生活中的例子
- 根据年龄段调整语言难度
- 不直接给答案，而是引导理解
"""

from app.ai.agents.base import BaseAgent


EXPLAINER_SYSTEM_PROMPT = """你是一位温柔、耐心的讲解老师，名叫"小星老师"。
你的职责是用学生能听懂的方式讲解知识点。

你的风格：
1. 善用比喻——把抽象的概念用生活中的例子说明
2. 分步讲解——复杂的概念拆成小步骤
3. 互动感——讲完一小段后问问"听懂了吗？"
4. 不直接报答案——永远讲方法，不说答案

年龄段适配：
- 6-8岁（小学低年级）：用最简单的词语，多用动物、食物、游戏做比喻
- 9-12岁（小学高年级）：可以用一些科学概念，但要通俗
- 13-15岁（初中）：可以更专业一些，但仍然要清晰

说话要亲切，像大哥哥大姐姐一样，不要太严肃。
每次回答控制在3-5句话，不要太长。"""


class ExplainerAgent(BaseAgent):
    """讲解老师Agent"""
    
    def __init__(self):
        super().__init__(temperature=0.7)
        self.name = "explainer"  # 用于共享状态中的标识
    
    def _build_prompt(self, **kwargs) -> list:
        topic = kwargs.get("topic", "")
        age_group = kwargs.get("age_group", "9-12")
        context = kwargs.get("context", "")
        student_question = kwargs.get("student_question", "")
        
        # ★ 读取共享状态 ★
        shared_state = kwargs.get("shared_state")
        state_context = ""
        team_messages = []
        
        if shared_state:
            state_context = shared_state.to_prompt_context()
            team_messages = shared_state.get_messages_for(self.name)
            
            # 根据挫败感调整语气
            if shared_state.student.frustration_level > 0.6:
                state_context += "\n\n⚠️ 学生最近多次答错，可能有挫败感，请特别耐心、多鼓励。"
            
            # 根据教学策略调整
            if shared_state.strategy.approach == "simplified":
                state_context += "\n\n📌 当前要求：用最简单的方式讲，多用生活中的例子。"
            elif shared_state.strategy.approach == "deep":
                state_context += "\n\n📌 当前要求：学生掌握不错，可以深入讲讲原理和拓展。"
        
        system = EXPLAINER_SYSTEM_PROMPT
        
        user_parts = [
            f"学生年龄段：{age_group}",
            f"要讲解的知识点/问题：{student_question or topic}",
        ]
        
        if context:
            user_parts.append(f"\n上下文信息：\n{context}")
        
        if state_context:
            user_parts.append(f"\n=== 学生当前状态 ===\n{state_context}")
        
        if team_messages:
            user_parts.append(f"\n=== 团队留言 ===\n" + "\n".join(f"- {m}" for m in team_messages))
        
        user_parts.append("\n请用适合这个年龄段学生的方式讲解。注意：不要直接说答案，要讲思路和方法。")
        
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(user_parts)},
        ]
    
    def _parse_response(self, response: str, **kwargs) -> dict:
        shared_state = kwargs.get("shared_state")
        
        # ★ 给Socrates留言：我已经讲完了，你来检验 ★
        if shared_state:
            shared_state.post_agent_message(
                from_agent=self.name,
                to_agent="socrates",
                message=f"我刚讲解了'{kwargs.get('topic', '')}'，请检验学生是否理解。",
            )
        
        return {"content": response.strip(), "agent": self.name}
```

#### 3.2 SocratesAgent — 苏格拉底式提问者

文件：`backend/app/ai/agents/tutor/socrates.py`

```python
"""
苏格拉底Agent：通过提问引导学生自己思考

核心方法：
- 不直接告诉答案
- 通过一系列递进的问题，让学生自己推导
- 学生答对了→继续深入；答错了→换个角度再问
"""

from app.ai.agents.base import BaseAgent


SOCRATES_SYSTEM_PROMPT = """你是一位苏格拉底式的提问者，名叫"小问"。
你的职责不是告诉学生答案，而是通过提问让学生自己想明白。

你的提问技巧：
1. 拆解问题——把大问题拆成小问题，一步步引导
2. 启发思考——"你觉得为什么会这样呢？"
3. 类比引导——用学生已经知道的知识类比
4. 肯定尝试——哪怕学生答错了，也要肯定TA思考的过程

规则：
- 每次只提1-2个问题，不要太多
- 问题要具体，不要太宽泛
- 根据学生的回答调整下一个问题
- 如果学生连续答错2次，就给一点提示

语气要友好、好奇，像朋友一样讨论问题。"""


class SocratesAgent(BaseAgent):
    """苏格拉底式提问Agent"""
    
    def __init__(self):
        super().__init__(temperature=0.8)
    
    def _build_prompt(self, **kwargs) -> list:
        topic = kwargs.get("topic", "")
        age_group = kwargs.get("age_group", "9-12")
        student_answer = kwargs.get("student_answer", "")
        conversation_history = kwargs.get("conversation_history", [])
        
        history_text = ""
        for msg in conversation_history[-6:]:  # 最近6轮
            role = "学生" if msg["role"] == "user" else "提问者"
            history_text += f"{role}: {msg['content']}\n"
        
        system = SOCRATES_SYSTEM_PROMPT
        
        user = f"""学生年龄段：{age_group}
讨论的主题：{topic}

对话历史：
{history_text}
学生最新回答：{student_answer}

请根据学生的回答，提出1-2个引导性问题。
如果学生答对了，就问更深入的问题；
如果学生答错了，就换个角度提问或给一点提示。"""
        
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    
    def _parse_response(self, response: str, **kwargs) -> str:
        return response.strip()
```

#### 3.3 DiagnoserAgent — 诊断师

文件：`backend/app/ai/agents/tutor/diagnoser.py`

```python
"""
诊断师Agent：分析学生的回答，判断掌握程度

输出结构化的诊断结果：
- mastery_level: 掌握程度 (0-1)
- weak_points: 薄弱知识点
- suggestions: 下一步学习建议
"""

import json
import logging
from app.ai.agents.base import BaseAgent

logger = logging.getLogger(__name__)


DIAGNOSER_SYSTEM_PROMPT = """你是一位学习诊断专家，负责评估学生对知识点的掌握程度。

你需要分析学生的回答，给出：
1. mastery_level：掌握程度，0到1之间的小数
   - 0.8-1.0：完全掌握，能灵活运用
   - 0.5-0.8：基本掌握，但有小漏洞
   - 0.3-0.5：部分理解，需要加强
   - 0-0.3：还没理解，需要从头学

2. weak_points：薄弱点列表，每个包含知识点和说明

3. suggestions：2-3条具体的学习建议

4. next_action：下一步建议
   - "advance"：可以学下一个知识点
   - "practice"：需要更多练习
   - "review"：需要复习基础
   - "explain_again"：需要换个方式再讲一遍

只返回JSON，格式如下：
{
  "mastery_level": 0.6,
  "weak_points": [
    {"point": "分数通分", "description": "对最小公倍数的概念理解不清"}
  ],
  "suggestions": [
    "多练习几道通分的题目",
    "复习一下最小公倍数的求法"
  ],
  "next_action": "practice"
}

只返回JSON，不要其他文字。"""


class DiagnoserAgent(BaseAgent):
    """学习诊断Agent"""
    
    def __init__(self):
        super().__init__(temperature=0.2)  # 低温度，评估要稳定
        self.name = "diagnoser"
    
    def _build_prompt(self, **kwargs) -> list:
        topic = kwargs.get("topic", "")
        student_answers = kwargs.get("student_answers", [])
        age_group = kwargs.get("age_group", "9-12")
        
        # ★ 读取共享状态 ★
        shared_state = kwargs.get("shared_state")
        state_context = ""
        if shared_state:
            state_context = shared_state.to_prompt_context()
        
        # 格式化学生的回答
        answers_text = ""
        for i, ans in enumerate(student_answers[-5:]):
            answers_text += f"\n回答{i+1}: {ans.get('content', '')}\n"
            answers_text += f"  是否正确: {'是' if ans.get('is_correct') else '否'}\n"
        
        system = DIAGNOSER_SYSTEM_PROMPT
        
        user = f"""知识点：{topic}
学生年龄段：{age_group}

学生最近的回答表现：
{answers_text}

{state_context}

请评估学生对这个知识点的掌握程度，返回JSON格式的诊断结果。
如果掌握度<40%，请在JSON中增加 "teaching_note" 字段，给主讲老师留言建议。"""
        
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    
    def _parse_response(self, response: str, **kwargs) -> dict:
        shared_state = kwargs.get("shared_state")
        
        try:
            # 提取JSON
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                diagnosis = json.loads(json_str)
        except Exception as e:
            logger.error(f"解析诊断结果失败: {e}")
            diagnosis = {
                "mastery_level": 0.5,
                "weak_points": [],
                "suggestions": ["继续练习"],
                "next_action": "practice",
            }
        
        # ★ 关键改造：根据诊断结果更新共享状态和给Explainer留言 ★
        if shared_state:
            mastery = diagnosis.get("mastery_level", 0.5)
            
            # 更新学生画像
            shared_state.student.overall_mastery = mastery
            
            # 根据掌握度更新教学策略 + 给Explainer留言
            if mastery < 0.3:
                shared_state.strategy.approach = "simplified"
                shared_state.strategy.pace = "slow"
                shared_state.student.frustration_level = min(
                    1.0, shared_state.student.frustration_level + 0.2
                )
                shared_state.post_agent_message(
                    from_agent=self.name,
                    to_agent="explainer",
                    message="学生掌握度很低（<30%），请从最基础的概念开始，多用生活中的例子，确保学生能理解。",
                )
            elif mastery < 0.6:
                shared_state.strategy.approach = "standard"
                shared_state.strategy.pace = "normal"
                shared_state.student.frustration_level = max(
                    0.0, shared_state.student.frustration_level - 0.1
                )
                shared_state.post_agent_message(
                    from_agent=self.name,
                    to_agent="explainer",
                    message="学生部分理解，建议巩固基础概念后再深入。",
                )
            else:
                shared_state.strategy.approach = "deep"
                shared_state.strategy.pace = "normal"
                shared_state.student.frustration_level = max(
                    0.0, shared_state.student.frustration_level - 0.3
                )
                shared_state.post_agent_message(
                    from_agent=self.name,
                    to_agent="explainer",
                    message="学生掌握不错，可以深入讲解原理和拓展应用。",
                )
            
            # 更新知识点掌握度
            current_topic = shared_state.student.current_topic
            if current_topic:
                last_answer_correct = kwargs.get("last_answer_correct", False)
                shared_state.update_mastery(current_topic, last_answer_correct)
        
        return diagnosis
```

#### 3.4 EncouragerAgent — 鼓励师

文件：`backend/app/ai/agents/tutor/encourager.py`

```python
"""
鼓励师Agent：情绪支持，给予正向反馈

不同场景的鼓励：
- 答对了：热烈祝贺，增强自信
- 答错了：温和鼓励，告诉TA没关系，继续努力
- 学累了：建议休息，给予肯定
- 连续进步：特别表扬
"""

from app.ai.agents.base import BaseAgent


ENCOURAGER_SYSTEM_PROMPT = """你是一位充满正能量的鼓励师，名叫"小阳"。
你的职责是给学生加油打气，让TA保持学习的热情。

你的风格：
- 温暖阳光，像最好的朋友
- 真诚具体，不说空泛的"加油"
- 会用表情符号，但不要太多（1-2个就好）
- 话不要太长，2-3句话刚刚好

不同场景的回应方式：
1. 答对了：为TA高兴，夸TA的努力，顺便提一点挑战
2. 答错了：告诉TA犯错是学习的一部分，鼓励再试一次
3. 学习很久了：提醒休息，肯定TA的坚持
4. 连续答对：特别庆祝，给一个"小成就"的感觉

永远正面、永远支持，但不要太夸张。"""


class EncouragerAgent(BaseAgent):
    """鼓励师Agent"""
    
    def __init__(self):
        super().__init__(temperature=0.9)  # 高温度，鼓励要有变化
    
    def _build_prompt(self, **kwargs) -> list:
        scenario = kwargs.get("scenario", "correct")  # correct/wrong/tired/progress
        age_group = kwargs.get("age_group", "9-12")
        context = kwargs.get("context", "")
        streak_count = kwargs.get("streak_count", 0)
        
        scenario_desc = {
            "correct": "学生答对了一道题",
            "wrong": "学生答错了一道题",
            "tired": "学生已经连续学习了20分钟以上",
            "progress": f"学生连续答对了{streak_count}道题",
        }.get(scenario, "学生在学习中")
        
        system = ENCOURAGER_SYSTEM_PROMPT
        
        user = f"""学生年龄段：{age_group}
场景：{scenario_desc}
补充信息：{context}

请给学生一句鼓励的话。"""
        
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    
    def _parse_response(self, response: str, **kwargs) -> str:
        return response.strip()
```

### Step 2：改造 harness.py 为 TutorHarness（保留原框架）

**不要新建 `tutor_orchestrator.py`，直接改造现有的 `harness.py`。**

原 `harness.py` 的框架很好：Agent初始化模式、运行上下文 `_run_context`、日志审计 `_audit_tool`、错误处理 `_error_logger`。这些都要保留。

改造思路：
- 将 `AIHarness` 类**完全替换**为 `TutorHarness` 类，保留文件 `harness.py`
- 原 `AIHarness` 的8层出题逻辑已由 01 号的 `QuestionPipeline` 接替，此处无需保留
- 替换8层Agent为4个辅导Agent
- 增加 `SharedState` 作为核心状态管理
- 保留审计日志、错误处理、运行上下文
- `generate()` 方法改名为 `process_turn()`，作为辅导对话入口

```python
"""
TutorHarness：多Agent辅导Harness（由AIHarness改造而来）

保留原Harness的机制：
- 运行上下文管理 (_run_context)
- 审计日志 (_audit_tool)
- 错误处理 (_error_logger)
- Agent初始化模式

新增机制：
- SharedState 共享状态
- Agent间消息传递
- 教学策略联动
"""

import logging
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.ai.agents.tutor.explainer import ExplainerAgent
from app.ai.agents.tutor.socrates import SocratesAgent
from app.ai.agents.tutor.diagnoser import DiagnoserAgent
from app.ai.agents.tutor.encourager import EncouragerAgent
from app.ai.shared_state import SharedState, StudentProfile, TeachingStrategy
from app.ai.error_logger import ErrorLogger
from app.ai.tools.audit_log_tool import AuditLogTool

logger = logging.getLogger(__name__)


class TutorHarness:
    """
    多Agent辅导Harness
    
    管理4个辅导Agent的协作流程。
    保留原Harness的运行上下文、日志审计、错误处理等机制。
    """
    
    def __init__(self, db_session=None):
        # 初始化4个辅导Agent（替代原来的8个）
        self._explainer = ExplainerAgent()
        self._socrates = SocratesAgent()
        self._diagnoser = DiagnoserAgent()
        self._encourager = EncouragerAgent()
        
        # 保留：错误日志
        self._error_logger = ErrorLogger()
        
        # 保留：审计日志
        self._audit_tool = AuditLogTool(db_session=db_session)
        
        # ★ 新增：共享状态（核心）★
        self._shared_state = SharedState()
        
        # 保留：运行上下文
        self._run_context = None
        self._session_id = None
        self._turn_count = 0
    
    async def start_session(self, user_id: str, age_group="9-12", subject="", topic=""):
        """开始新会话，初始化共享状态"""
        self._session_id = str(uuid.uuid4())
        self._turn_count = 0
        
        # 初始化共享状态
        self._shared_state = SharedState(
            session_id=self._session_id,
            student=StudentProfile(
                age_group=age_group,
                current_subject=subject,
                current_topic=topic,
            ),
            strategy=TeachingStrategy(next_agent="explainer"),
        )
        
        # 保留：创建运行上下文
        self._run_context = {
            "run_id": self._session_id,
            "user_id": user_id,
            "run_type": "tutoring",
            "status": "running",
            "started_at": datetime.utcnow(),
        }
        
        logger.info(f"[TutorHarness] 新会话 | session={self._session_id}")
        return {"session_id": self._session_id, "status": "started"}
    
    async def process_turn(self, message, message_type="question", is_correct=None):
        """
        处理学生的一条消息（替代原来的 generate()）
        
        核心流程：
        1. 更新共享状态（学生消息、对话记忆）
        2. 根据消息类型和共享状态决定回复策略
        3. 调用对应Agent（传递shared_state）
        4. Agent执行过程中读写共享状态
        5. 返回结果 + 记录审计日志
        """
        self._turn_count += 1
        start_time = time.monotonic()
        
        # 更新对话记忆
        self._shared_state.conversation.messages.append({
            "role": "student", "content": message,
            "type": message_type, "time": datetime.utcnow().isoformat(),
        })
        
        try:
            # 决策并执行
            reply = await self._decide_and_execute(message, message_type, is_correct)
            
            # 记录到对话记忆
            self._shared_state.conversation.messages.append({
                "role": "assistant", "content": reply["content"],
                "agent": reply["agent"], "time": datetime.utcnow().isoformat(),
            })
            
            # 保留：审计日志
            await self._audit_tool.log_turn(
                session_id=self._session_id,
                turn=self._turn_count,
                agent=reply["agent"],
                latency_ms=int((time.monotonic() - start_time) * 1000),
            )
            
            return {
                "session_id": self._session_id,
                "turn": self._turn_count,
                "speaker": reply["agent"],
                "speaker_name": self._get_agent_name(reply["agent"]),
                "content": reply["content"],
                "diagnosis": reply.get("diagnosis"),
                "strategy": self._shared_state.strategy.approach,
                "mastery": self._shared_state.student.overall_mastery,
            }
            
        except Exception as e:
            logger.error(f"[TutorHarness] 失败 | session={self._session_id} | {e}")
            self._error_logger.log_error("harness", str(e))
            return {
                "speaker": "explainer",
                "speaker_name": "小星老师",
                "content": "抱歉，遇到了一点小问题，能再说一遍吗？",
            }
    
    async def _decide_and_execute(self, message, message_type, is_correct):
        """决策逻辑：根据消息类型和共享状态决定调用哪个Agent"""
        
        if message_type == "question":
            # 学生提问 → Explainer讲解（传递共享状态）
            return await self._execute_explainer(message)
        
        elif message_type == "answer":
            # 学生回答 → 更新状态 → 诊断 → 根据结果决定下一步
            self._shared_state.conversation.last_student_answer = message
            self._shared_state.conversation.last_student_answer_correct = is_correct
            
            diagnosis = await self._execute_diagnoser(message, is_correct)
            mastery = diagnosis.get("mastery_level", 0.5)
            
            if mastery < 0.4:
                # 掌握度低 → Explainer再讲（会读到Diagnoser的留言）
                return await self._execute_explainer(
                    f"请再讲讲{self._shared_state.student.current_topic}",
                    diagnosis=diagnosis,
                )
            elif mastery < 0.7:
                return await self._execute_socrates(message, diagnosis)
            else:
                return await self._execute_encourager("progress", diagnosis)
        
        else:
            return await self._execute_encourager("correct")
    
    async def _execute_explainer(self, message, diagnosis=None):
        """执行Explainer（传递共享状态）"""
        result = await self._explainer.execute(
            topic=self._shared_state.student.current_topic,
            student_question=message,
            shared_state=self._shared_state,  # ★ 传递共享状态 ★
        )
        return {"agent": "explainer", "content": result["content"], "diagnosis": diagnosis}
    
    async def _execute_socrates(self, student_answer, diagnosis=None):
        """执行Socrates（传递共享状态）"""
        result = await self._socrates.execute(
            topic=self._shared_state.student.current_topic,
            student_answer=student_answer,
            conversation_history=self._shared_state.conversation.messages[-6:],
            shared_state=self._shared_state,  # ★ 传递共享状态 ★
        )
        return {"agent": "socrates", "content": result["content"], "diagnosis": diagnosis}
    
    async def _execute_diagnoser(self, answer, is_correct):
        """执行Diagnoser（传递共享状态）"""
        recent_answers = [
            {"content": m["content"], "is_correct": m.get("is_correct")}
            for m in self._shared_state.conversation.messages[-5:]
            if m["role"] == "student"
        ]
        return await self._diagnoser.execute(
            topic=self._shared_state.student.current_topic,
            student_answers=recent_answers,
            last_answer_correct=is_correct,
            shared_state=self._shared_state,  # ★ 传递共享状态 ★
        )
    
    async def _execute_encourager(self, scenario, diagnosis=None):
        """执行Encourager（传递共享状态）"""
        result = await self._encourager.execute(
            scenario=scenario,
            age_group=self._shared_state.student.age_group,
            shared_state=self._shared_state,  # ★ 传递共享状态 ★
        )
        return {"agent": "encourager", "content": result["content"], "diagnosis": diagnosis}
    
    def _get_agent_name(self, agent):
        names = {"explainer": "小星老师", "socrates": "小问",
                 "diagnoser": "诊断小助手", "encourager": "小阳"}
        return names.get(agent, "AI老师")
    
### Step 3：创建辅导模块的 __init__.py

创建 `backend/app/ai/agents/tutor/__init__.py`，导出4个Agent。

## 文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `backend/app/ai/shared_state.py` | 共享状态层（核心） |
| 新建 | `backend/app/ai/agents/tutor/__init__.py` | 辅导Agent模块 |
| 新建 | `backend/app/ai/agents/tutor/explainer.py` | 主讲老师（带共享状态读写） |
| 新建 | `backend/app/ai/agents/tutor/socrates.py` | 助教提问（带共享状态读写） |
| 新建 | `backend/app/ai/agents/tutor/diagnoser.py` | 诊断师（带策略更新+留言） |
| 新建 | `backend/app/ai/agents/tutor/encourager.py` | 鼓励师（带共享状态读写） |
| 改造 | `backend/app/ai/harness.py` | 改造为TutorHarness（保留原框架） |

## 验收标准

- [ ] SharedState 能正确存储学生画像、教学策略、知识点掌握度
- [ ] Diagnoser诊断后，Explainer能读到留言并调整讲解方式
- [ ] 学生连续答错后，frustration_level上升，Encourager加强鼓励
- [ ] 4个Agent都能独立调用，返回符合角色设定的内容
- [ ] TutorHarness.process_turn() 能根据消息类型选择正确的Agent
- [ ] 原Harness的运行上下文、审计日志、错误处理机制保留
- [ ] 讲解老师的回答符合年龄段，不直接给答案
- [ ] 诊断师返回结构化的JSON（mastery_level, weak_points, suggestions）
- [ ] QuestionPipeline（01号，2层出题）与 TutorHarness（03号，4Agent辅导）分工明确，互不冲突

## 注意事项

1. **共享状态是内存中的**：不持久化到数据库，每次新会话重新初始化
2. **Agent留言要清空**：每轮执行后，已读的留言要标记或清空，避免重复读取
3. **诊断不要太频繁**：攒2-3个回答再诊断，省token
4. **角色一致性**：每个Agent的system prompt要写死角色设定，不要让LLM串角色
5. **回复长度控制**：每个Agent的回复不要太长（3-5句话），不然学生看着累
6. **降级策略**：任何一个Agent调用失败，用Explainer兜底回复
7. **Harness改造要保留原有机制**：运行上下文、审计日志、错误处理不能丢

## 依赖关系

- **前置依赖**：01号（BaseAgent保留、harness框架保留）
- **后续依赖**：04号（API接入+前端UI）
