import { getDifficultyMeta } from "../src/components/learning/answer-feedback-meta";
import { getTutorRoleMeta } from "../src/components/ai/tutor-presentation";

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
