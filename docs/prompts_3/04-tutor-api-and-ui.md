# 04 - 多Agent辅导系统：API接入 + 前端对话UI

## 任务目标

把上一步做好的多Agent辅导系统：
1. 接到后端API上（改造现有的 `/ai/chat` 接口）
2. 在前端做一个多角色对话UI（不同Agent不同头像/颜色/名字）
3. 支持答题后触发AI讲解（从答题页直接跳转到辅导对话）

## 当前代码状态

### 后端API

文件：`backend/app/api/v1/ai.py`

当前的 `POST /chat` 是单角色的，直接调LLM：
```python
@router.post("/chat")
async def chat(body: ChatRequest):
    # 直接调provider.chat()
    # 单Prompt，单角色
    ...
```

### 前端学习页

文件：`frontend/src/app/(main)/learning/[id]/page.tsx`

有一个AI聊天面板，但也是单角色的，只有一个"AI助手"。

### 前端类型定义

文件：`frontend/src/types/api.ts`

有ChatRequest和ChatResponse的类型定义。

## 需要做的改动

### Step 1：改造后端API

修改 `backend/app/api/v1/ai.py`，把 `/chat` 改成调用 `TutorHarness`（改造后的harness.py）：

```python
from app.ai.harness import TutorHarness

# 在ChatRequest中增加字段：
class ChatRequest(BaseModel):
    message: str
    message_type: str = "question"  # question/answer/casual
    topic: str = ""
    age_group: str = "9-12"
    context: Optional[Dict[str, Any]] = None
    conversationHistory: Optional[List[Dict[str, str]]] = None

# 新增TutorResponse
class TutorResponse(BaseModel):
    speaker: str  # explainer/socrates/diagnoser/encourager
    speaker_name: str  # 小星老师/小问/小阳
    content: str
    diagnosis: Optional[Dict[str, Any]] = None
    next_expected: str  # student_question/student_answer/continue
    suggestions: Optional[List[str]] = None


@router.post("/chat")
async def chat(
    body: ChatRequest,
    user_id: Optional[uuid.UUID] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    多Agent辅导对话接口
    
    根据消息类型，由不同的Agent回复：
    - question（提问）→ Explainer讲解老师
    - answer（回答）→ Socrates提问 / Diagnoser诊断
    - casual（闲聊）→ Encourager鼓励师
    """
    try:
        # 先提取参数
        topic = body.topic
        age_group = body.age_group or "9-12"
        
        harness = TutorHarness(db_session=db)
        await harness.start_session(
            user_id=str(user_id) if user_id else None,
            age_group=age_group,
            subject=topic,
            topic=topic,
        )
        
        # 从context中提取信息
        context_str = ""
        
        if body.context:
            # 如果有题目信息，拼到context里
            if "question" in body.context:
                q = body.context["question"]
                context_str = f"当前题目：{q.get('question_text', '')}\n"
                context_str += f"答案：{q.get('correct_answer', '')}\n"
                context_str += f"解析：{q.get('explanation', '')}\n"
                if not topic:
                    topic = q.get("subject", "")
        
        result = await harness.process_turn(
            message=body.message,
            message_type=body.message_type,
        )
        
        # 加上建议问题
        suggestions = _generate_suggestions(result["speaker"], topic)
        
        return success_response(
            data=TutorResponse(
                speaker=result["speaker"],
                speaker_name=result["speaker_name"],
                content=result["content"],
                diagnosis=result.get("diagnosis"),
                next_expected=result["next_expected"],
                suggestions=suggestions,
            )
        )
        
    except Exception as e:
        logger.error(f"辅导对话失败: {e}")
        # 降级：返回简单回复
        return success_response(
            data=TutorResponse(
                speaker="explainer",
                speaker_name="小星老师",
                content="抱歉，我遇到了一点小问题，能再说一遍吗？",
                next_expected="student_question",
            )
        )


def _generate_suggestions(speaker: str, topic: str) -> List[str]:
    """生成推荐的后续问题"""
    base = [
        f"再给我讲讲{topic}吧",
        "出一道题考考我",
        "这个知识点重要吗？",
    ]
    return base[:3]
```

### Step 2：新增答题后讲解接口

在 `ai.py` 中新增一个接口，用于答题后一键触发AI讲解：

```python
class ExplainQuestionRequest(BaseModel):
    question_id: uuid.UUID
    user_answer: Optional[str] = None
    is_correct: Optional[bool] = None


@router.post("/explain-question")
async def explain_question_after_answer(
    body: ExplainQuestionRequest,
    user_id: uuid.UUID = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    答题后触发AI讲解
    
    根据学生的答题情况（对了/错了），由合适的Agent开始讲解。
    """
    # 查询题目
    from app.models.question import Question
    result = await db.execute(
        select(Question).where(Question.id == body.question_id)
    )
    question = result.scalar_one_or_none()
    
    if not question:
        return error_response(message="题目不存在")
    
    # 构造辅导对话的初始消息
    harness = TutorHarness(db_session=db)
    await harness.start_session(
        user_id=str(user_id) if user_id else None,
        age_group="9-12",
        subject=question.subject,
        topic=question.knowledge_points[0] if question.knowledge_points else question.subject,
    )
    
    if body.is_correct:
        # 答对了 → 先鼓励，再深入提问
        initial_message = f"我做对了这道题，想再深入了解一下相关知识点"
        message_type = "question"
    else:
        # 答错了 → 讲解为什么错了
        initial_message = f"这道题我做错了，能给我讲讲为什么吗？"
        message_type = "question"
    
    result = await harness.process_turn(
        message=initial_message,
        message_type=message_type,
    )
    
    return success_response(
        data={
            "question": {
                "id": str(question.id),
                "text": question.question_text,
                "correct_answer": question.correct_answer,
                "explanation": question.explanation,
            },
            "ai_reply": {
                "speaker": result["speaker"],
                "speaker_name": result["speaker_name"],
                "content": result["content"],
                "diagnosis": result.get("diagnosis"),
                "next_expected": result["next_expected"],
            },
        }
    )
```

### Step 3：前端多角色对话UI组件

新建 `frontend/src/components/ai/tutor-chat.tsx`：

```tsx
"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, Sparkles, Brain, Heart, Lightbulb } from "lucide-react";

// 不同角色的配置
const SPEAKER_CONFIG = {
  explainer: {
    name: "小星老师",
    avatar: "⭐",
    bgColor: "bg-blue-50",
    borderColor: "border-blue-200",
    textColor: "text-blue-800",
    icon: Lightbulb,
  },
  socrates: {
    name: "小问",
    avatar: "🤔",
    bgColor: "bg-purple-50",
    borderColor: "border-purple-200",
    textColor: "text-purple-800",
    icon: Brain,
  },
  diagnoser: {
    name: "诊断小助手",
    avatar: "📊",
    bgColor: "bg-amber-50",
    borderColor: "border-amber-200",
    textColor: "text-amber-800",
    icon: Sparkles,
  },
  encourager: {
    name: "小阳",
    avatar: "😊",
    bgColor: "bg-green-50",
    borderColor: "border-green-200",
    textColor: "text-green-800",
    icon: Heart,
  },
  student: {
    name: "我",
    avatar: "👤",
    bgColor: "bg-gray-100",
    borderColor: "border-gray-200",
    textColor: "text-gray-800",
    icon: null,
  },
};

type Speaker = keyof typeof SPEAKER_CONFIG;

interface Message {
  id: string;
  speaker: Speaker;
  content: string;
  diagnosis?: any;
}

interface TutorChatProps {
  topic?: string;
  initialMessage?: string;
  questionContext?: any;
  onClose?: () => void;
}

export function TutorChat({ topic, initialMessage, questionContext, onClose }: TutorChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 如果有初始消息，自动发送
  useEffect(() => {
    if (initialMessage && messages.length === 0) {
      handleSend(initialMessage, "question");
    }
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (text: string, type: string = "question") => {
    if (!text.trim() || isLoading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      speaker: "student",
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const res = await fetch("/api/v1/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          message_type: type,
          topic: topic,
          age_group: "9-12",
          context: questionContext,
          conversationHistory: messages.slice(-10).map((m) => ({
            role: m.speaker === "student" ? "user" : "assistant",
            content: m.content,
          })),
        }),
      });

      const data = await res.json();
      if (data.code === 0 && data.data) {
        const aiMsg: Message = {
          id: (Date.now() + 1).toString(),
          speaker: data.data.speaker as Speaker,
          content: data.data.content,
          diagnosis: data.data.diagnosis,
        };
        setMessages((prev) => [...prev, aiMsg]);
      }
    } catch (e) {
      console.error("聊天失败", e);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-lg overflow-hidden">
      {/* 头部 */}
      <div className="p-4 bg-gradient-to-r from-blue-500 to-purple-500 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold">AI辅导老师</h3>
            <p className="text-sm opacity-80">
              {topic || "有什么问题都可以问我哦~"}
            </p>
          </div>
          {onClose && (
            <Button variant="ghost" size="sm" onClick={onClose} className="text-white hover:bg-white/20">
              关闭
            </Button>
          )}
        </div>
      </div>

      {/* 消息区 */}
      <ScrollArea className="flex-1 p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 py-8">
            <Sparkles className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p>随时提问，我会帮你理解知识点~</p>
          </div>
        )}

        {messages.map((msg) => {
          const config = SPEAKER_CONFIG[msg.speaker];
          const isStudent = msg.speaker === "student";

          return (
            <div
              key={msg.id}
              className={`flex ${isStudent ? "justify-end" : "justify-start"}`}
            >
              <div className={`max-w-[80%] ${isStudent ? "order-2" : "order-1"}`}>
                {/* 角色名 */}
                <div className={`text-xs mb-1 ${isStudent ? "text-right" : "text-left"} ${config.textColor}`}>
                  {config.name}
                </div>
                {/* 消息气泡 */}
                <div
                  className={`px-4 py-2 rounded-2xl ${config.bgColor} ${config.borderColor} border`}
                >
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                </div>
                {/* 诊断信息（如果有） */}
                {msg.diagnosis && (
                  <div className="mt-2 p-2 bg-amber-50 rounded-lg border border-amber-200 text-xs">
                    <p className="font-medium text-amber-800">📊 掌握程度评估</p>
                    <div className="mt-1 flex items-center gap-2">
                      <div className="flex-1 bg-amber-200 rounded-full h-2">
                        <div
                          className="bg-amber-500 h-2 rounded-full"
                          style={{ width: `${(msg.diagnosis.mastery_level || 0) * 100}%` }}
                        />
                      </div>
                      <span className="text-amber-700">
                        {Math.round((msg.diagnosis.mastery_level || 0) * 100)}%
                      </span>
                    </div>
                    {msg.diagnosis.suggestions?.length > 0 && (
                      <ul className="mt-2 space-y-1">
                        {msg.diagnosis.suggestions.map((s: string, i: number) => (
                          <li key={i} className="text-amber-700">💡 {s}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
        <div ref={scrollRef} />
      </ScrollArea>

      {/* 输入区 */}
      <div className="p-3 border-t">
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend(input)}
            placeholder="输入你的问题..."
            disabled={isLoading}
          />
          <Button onClick={() => handleSend(input)} disabled={isLoading || !input.trim()}>
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
```

### Step 4：答题后触发辅导

在学习页答题结果展示中，加一个"听AI讲解"按钮，点击后展开TutorChat组件。

修改 `frontend/src/app/(main)/learning/[id]/page.tsx`：
- 导入 TutorChat 组件
- 答题结果展示区域加一个"AI讲解"按钮
- 点击后展开/切换到辅导对话视图

### Step 5：全局浮动AI按钮（可选，有时间再做）

加一个全局右下角浮动的"AI辅导"按钮，点击展开聊天面板，可以随时问问题。

## 文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 修改 | `backend/app/api/v1/ai.py` | 改/chat为多Agent + 新增/explain-question |
| 新建 | `frontend/src/components/ai/tutor-chat.tsx` | 多角色对话UI组件 |
| 修改 | `frontend/src/app/(main)/learning/[id]/page.tsx` | 接入TutorChat + 答题后讲解入口 |
| 修改 | `frontend/src/types/api.ts` | 更新Chat类型定义 |

## 验收标准

- [ ] `/chat` 接口返回多角色格式（speaker, speaker_name, content）
- [ ] 不同类型的消息由不同的Agent回复
- [ ] 前端对话UI中不同角色有不同的颜色和名字
- [ ] 答题后点击"AI讲解"能打开辅导对话，且上下文包含题目信息
- [ ] 诊断结果能展示掌握程度进度条和建议
- [ ] 连续对话能保持上下文

## 注意事项

1. **对话历史不要太长**：只传最近10轮，省token
2. **降级处理**：TutorHarness调用失败时返回默认回复，不要崩
3. **UI响应式**：聊天面板在手机上要能正常显示
4. **角色一致性**：前端展示的角色名和后端返回的要对应
5. **输入防抖**：防止用户连续点发送导致重复请求

## 依赖关系

- **前置依赖**：03号（多Agent辅导系统实现完成）
- **后续依赖**：07号（游戏化）、08号（行为建模）等
