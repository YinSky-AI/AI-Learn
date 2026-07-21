# 05 - 答题反馈增强：解析 + 知识点 + AI讲解入口

## 任务目标

答题后不再只返回"对/错"，而是返回完整的反馈信息：
- 正确答案和详细解析
- 关联的知识点标签
- 难度标签
- "听AI讲解"按钮（跳转到多Agent辅导）

## 当前代码状态

### 答题API

文件：`backend/app/api/v1/user_courses.py` 或 `backend/app/api/v1/questions.py`

当前的答题提交接口大概返回：
```json
{
  "is_correct": true,
  "score": 10
}
```

只有对错和分数，没有解析和知识点。

### 前端答题页

文件：`frontend/src/app/(main)/learning/[id]/page.tsx`

答题后只显示对错和分数，没有更多信息。

### Question模型

文件：`backend/app/models/question.py`

Question表有 `explanation`、`knowledge_points`、`difficulty` 字段，但答题接口没有返回这些。

## 需要做的改动

### Step 1：增强答题API返回

修改答题提交接口，返回完整的题目信息：

```python
# 在答题接口的返回中增加：
return success_response(
    data={
        "is_correct": is_correct,
        "score": earned_score,
        "total_score": total_score,
        "question": {
            "id": str(question.id),
            "question_text": question.question_text,
            "options": question.options,
            "correct_answer": question.correct_answer,
            "explanation": question.explanation,
            "knowledge_points": question.knowledge_points or [],
            "difficulty": question.difficulty,
            "subject": question.subject,
        },
        "next_question_id": next_q_id if next_q_id else None,
        "progress": {
            "current": current_index + 1,
            "total": total_questions,
            "correct_count": correct_count,
        },
    }
)
```

### Step 2：前端答题结果卡片

在学习页增加一个答题结果卡片组件，答题后展示：

- ✅ 或 ❌ 大图标 + "答对了！"/"答错了"
- 正确答案（答错时标红）
- 详细解析（可展开/收起）
- 知识点标签（chip样式）
- 难度标签（绿/黄/红）
- "听AI讲解"按钮（醒目样式）

组件示例结构：
```tsx
// 新建 frontend/src/components/learning/answer-feedback.tsx

interface AnswerFeedbackProps {
  isCorrect: boolean;
  question: Question;
  userAnswer: string;
  onExplain: () => void;
  onNext: () => void;
}

export function AnswerFeedback({ isCorrect, question, userAnswer, onExplain, onNext }: AnswerFeedbackProps) {
  return (
    <div className={`p-4 rounded-xl border-2 ${isCorrect ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
      {/* 结果标题 */}
      <div className="flex items-center gap-3 mb-3">
        <div className={`text-4xl ${isCorrect ? '' : 'animate-bounce'}`}>
          {isCorrect ? '🎉' : '😅'}
        </div>
        <div>
          <h3 className={`text-xl font-bold ${isCorrect ? 'text-green-700' : 'text-red-700'}`}>
            {isCorrect ? '答对了！' : '答错了'}
          </h3>
          <p className="text-sm text-gray-600">
            {isCorrect ? '太棒了，继续保持~' : '没关系，看看解析弄懂它'}
          </p>
        </div>
      </div>

      {/* 正确答案 */}
      {!isCorrect && (
        <div className="mb-3 p-3 bg-white rounded-lg">
          <p className="text-sm font-medium text-gray-700 mb-1">正确答案</p>
          <p className="text-lg font-semibold text-green-600">{question.correct_answer}</p>
        </div>
      )}

      {/* 解析 */}
      {question.explanation && (
        <div className="mb-3 p-3 bg-white rounded-lg">
          <p className="text-sm font-medium text-gray-700 mb-1">💡 解析</p>
          <p className="text-sm text-gray-600 whitespace-pre-wrap">{question.explanation}</p>
        </div>
      )}

      {/* 知识点标签 */}
      {question.knowledge_points?.length > 0 && (
        <div className="mb-3">
          <p className="text-sm font-medium text-gray-700 mb-1">📚 知识点</p>
          <div className="flex flex-wrap gap-1">
            {question.knowledge_points.map((kp, i) => (
              <span key={i} className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">
                {kp}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 难度标签 */}
      <div className="mb-4">
        <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${
          question.difficulty === 'beginner' ? 'bg-green-100 text-green-700' :
          question.difficulty === 'intermediate' ? 'bg-yellow-100 text-yellow-700' :
          'bg-red-100 text-red-700'
        }`}>
          {question.difficulty === 'beginner' ? '简单' :
           question.difficulty === 'intermediate' ? '中等' : '困难'}
        </span>
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-2">
        <Button
          variant="outline"
          className="flex-1"
          onClick={onExplain}
        >
          <Lightbulb className="w-4 h-4 mr-2" />
          听AI讲解
        </Button>
        <Button className="flex-1" onClick={onNext}>
          下一题
          <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}
```

### Step 3：接入学习页

在 `learning/[id]/page.tsx` 中：
1. 导入 AnswerFeedback 组件
2. 答题后展示反馈卡片（替换原来简单的对错显示）
3. "听AI讲解"按钮点击后调用 `POST /api/v1/ai/explain-question` 接口（04号已定义），参数：
   - `question_id`: 当前题目ID
   - `user_answer`: 用户的答案
   - `is_correct`: 是否答对
   接口返回AI辅导的初始回复，前端拿到后打开 TutorChat 组件并自动显示第一条AI消息

### Step 4：答错自动收录错题本

答题API中，如果答错了，自动添加到错题本（为06号错题本功能做准备）。

如果错题本表还没建好，先打个TODO标记，后面再补。

## 文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 修改 | `backend/app/api/v1/user_courses.py` | 增强答题返回信息 |
| 新建 | `frontend/src/components/learning/answer-feedback.tsx` | 答题反馈卡片组件 |
| 修改 | `frontend/src/app/(main)/learning/[id]/page.tsx` | 接入反馈组件 |

## 验收标准

- [ ] 答题后返回完整的题目信息（解析、知识点、难度）
- [ ] 前端展示美观的反馈卡片
- [ ] 答对和答错有不同的视觉样式
- [ ] "听AI讲解"按钮能正常触发AI辅导对话
- [ ] 知识点标签和难度标签正确显示
- [ ] 解析内容支持换行

## 注意事项

1. **解析可能为空**：不是所有题都有解析，要处理空的情况
2. **选项格式**：options可能是数组也可能是对象数组，展示时要兼容
3. **移动端适配**：反馈卡片在小屏幕上要好看
4. **动画效果**：答对了可以加个小动画，增加成就感
5. **不要打断节奏**：反馈卡片不要太大，"下一题"按钮要醒目

## 依赖关系

- **前置依赖**：04号（辅导系统UI可用）
- **后续依赖**：06号（错题本）
