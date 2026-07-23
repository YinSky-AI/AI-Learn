import { getDifficultyMeta } from "../src/components/learning/answer-feedback-meta";
import { mapQuizQuestion } from "../src/components/learning/quiz-question-mapper";
import { getTutorRoleMeta, TUTOR_UNAVAILABLE_MESSAGE } from "../src/components/ai/tutor-presentation";
import type { ChatRequest, ChatResponse } from "../src/types/api";

const teacher = getTutorRoleMeta("teacher", "老师");
if (teacher.name !== "老师" || !teacher.className.includes("blue")) {
  throw new Error("老师角色应使用传入名称和蓝色视觉样式");
}

const diagnoser = getTutorRoleMeta("diagnostician", "诊断师");
if (!diagnoser.className.includes("amber")) {
  throw new Error("诊断角色应使用琥珀色视觉样式");
}

if (getDifficultyMeta("beginner").label !== "简单") {
  throw new Error("beginner 难度应显示为简单");
}

if (getDifficultyMeta("advanced").label !== "困难") {
  throw new Error("advanced 难度应显示为困难");
}

if (getDifficultyMeta(undefined).label !== "未标注") {
  throw new Error("没有难度时不得错误显示为困难");
}

const mappedQuestion = mapQuizQuestion({
  id: "question-1",
  question_type: "CHOICE",
  question_body: "1 + 1 等于几？",
  difficulty_level: "intermediate",
  knowledge_points: ["加法"],
});
if (!mappedQuestion || mappedQuestion.difficulty !== "intermediate" || mappedQuestion.knowledgePoints?.[0] !== "加法") {
  throw new Error("题目映射应兼容 difficulty_level 与 knowledge_points");
}

if (mapQuizQuestion({ id: "unknown", question_type: "ESSAY", question_body: "说明原因" }) !== null) {
  throw new Error("未知题型不得被强制伪装为可作答题型");
}

const tutorRequest: ChatRequest = {
  message: "我卡在这一步了",
  context: { is_correct: false, student_answer: "A", question: { id: "question-1", knowledge_points: ["加法"] } },
  conversationHistory: [{ role: "user", content: "题目怎么做？" }],
};
if (tutorRequest.context?.question?.knowledge_points?.[0] !== "加法") {
  throw new Error("辅导请求必须保留题目上下文");
}

const tutorResponse: ChatResponse = {
  messages: [
    { role: "teacher", name: "老师", content: "先说说题目问什么。" },
    { role: "assistant", name: "助教", content: "把条件分成两步。" },
    { role: "diagnostician", name: "诊断师", content: "先核对运算含义。" },
    { role: "encourager", name: "鼓励师", content: "你已经迈出第一步。" },
  ],
  suggested_next_step: "先回答老师的问题。",
};
if (tutorResponse.messages.length !== 4) {
  throw new Error("多角色响应必须保留全部角色消息");
}

if (!TUTOR_UNAVAILABLE_MESSAGE.includes("暂时") || /\{|\}|Error|Exception/.test(TUTOR_UNAVAILABLE_MESSAGE)) {
  throw new Error("前端错误态必须是安全的中文纯文本");
}
