import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(
  new URL("../src/app/(main)/ai-questions/page.tsx", import.meta.url),
  "utf8",
);
const floating = readFileSync(new URL("../src/components/ai/floating-ai-button.tsx", import.meta.url), "utf8");
const tutor = readFileSync(new URL("../src/components/ai/tutor-chat.tsx", import.meta.url), "utf8");

test("AI question page calls the two-agent generation API", () => {
  assert.match(page, /apiClient\.post<GenerateResult>\("\/v1\/questions\/generate"/);
  assert.match(page, /出题 Agent/);
  assert.match(page, /审题 Agent/);
  assert.match(page, /course_topic/);
  assert.match(page, /question_types/);
});

test("AI question page allows enough time for the two-agent workflow", () => {
  assert.match(page, /timeout:\s*90_000/);
  assert.match(page, /AI 出题等待超时，请稍后重试/);
});

test("global AI question shortcut routes to the two-agent page", () => {
  assert.match(floating, /router\.push\("\/ai-questions"\)/);
  assert.match(floating, /onQuickPrompt=/);
  assert.match(tutor, /onQuickPrompt\?\.\(prompt\)/);
});

test("AI question page keeps generated questions on the public contract before submission", () => {
  assert.match(page, /question_body/);
  assert.match(page, /quality_status/);
  assert.match(page, /type GeneratedQuestion = \{[\s\S]*?quality_status: string;/);
});

test("AI-generated questions support the three Chinese question types and answer controls", () => {
  assert.match(page, /const \[answers, setAnswers\]/);
  assert.match(page, /onClick=\{\(\) => selectOption\(question, option\.key\)\}/);
  assert.match(page, /单选题/);
  assert.match(page, /多选题/);
  assert.match(page, /填空 1/);
});

test("AI question page gates one batch submission until every question is answered", () => {
  assert.match(page, /const answersComplete = questions\.length > 0 && questions\.every/);
  assert.match(page, /disabled=\{!answersComplete \|\| practiceState === "submitting"\}/);
  assert.match(page, /请完成全部题目后再提交/);
  assert.match(page, /提交全部答案/);
});

test("AI question page posts the exact batch answer set with a retry-stable submission ID", () => {
  assert.match(page, /type PracticeSubmissionState = "answering" \| "submitting" \| "submitted" \| "error"/);
  assert.match(page, /const \[submissionId, setSubmissionId\] = useState<string \| null>\(null\)/);
  assert.match(page, /crypto\.randomUUID\(\)/);
  assert.match(page, /apiClient\.post<GeneratedPracticeSubmitResult>\(\s*`\/v1\/questions\/batches\/\$\{batchId\}\/submit`/);
  assert.match(page, /submission_id: activeSubmissionId/);
  assert.match(page, /answers: questions\.map/);
  assert.match(page, /time_spent_seconds: Math\.max\(0/);
  assert.match(page, /setSubmissionId\(null\)/);
});

test("AI question page freezes answers and renders only server-verified feedback after submission", () => {
  assert.match(page, /const isAnswerLocked = practiceState === "submitting" \|\| practiceState === "submitted"/);
  assert.match(page, /disabled=\{isAnswerLocked\}/);
  assert.match(page, /submissionResult\?\.results\.find/);
  assert.match(page, /服务端判定：\{result\.is_correct \? "回答正确" : "回答错误"\}/);
  assert.match(page, /正确答案：\{result\.correct_answer\}/);
  assert.match(page, /result\.explanation/);
  assert.match(page, /总题数/);
  assert.match(page, /正确数/);
  assert.match(page, /正确率/);
  assert.match(page, /用时/);
});

test("AI question page maps submission failures to fixed Chinese messages", () => {
  assert.match(page, /function getSubmissionErrorMessage/);
  assert.match(page, /提交超时，请稍后重试/);
  assert.match(page, /登录状态已失效，请重新登录后提交/);
  assert.match(page, /题目审核或答案校验未通过，请重新出题后再试/);
  assert.match(page, /出题服务暂时不可用，请稍后再试/);
  assert.doesNotMatch(page, /setError\(cause as/);
});
