import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  getOrCreateSubmissionPayload,
  getSubmissionErrorMessage,
  hasNormalizedAnswerChanged,
  indexSubmissionResults,
  invalidateSubmissionPayload,
} from "../src/app/(main)/ai-questions/practice-submission.mjs";

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
  assert.match(page, /getOrCreateSubmissionPayload\(/);
  assert.match(page, /submissionPayloadRef\.current/);
  assert.match(page, /submissionInFlightRef\.current/);
  assert.match(page, /hasNormalizedAnswerChanged/);
  assert.match(page, /setSubmissionId\(null\)/);
});

test("AI question page freezes answers and renders only server-verified feedback after submission", () => {
  assert.match(page, /const isAnswerLocked = practiceState === "submitting" \|\| practiceState === "submitted"/);
  assert.match(page, /disabled=\{isAnswerLocked\}/);
  assert.match(page, /indexSubmissionResults\(submissionResult\.results\)/);
  assert.match(page, /resultsByQuestionId\[question\.id\]/);
  assert.match(page, /服务端判定：\{result\.is_correct \? "回答正确" : "回答错误"\}/);
  assert.match(page, /正确答案：\{result\.correct_answer\}/);
  assert.match(page, /result\.explanation/);
  assert.match(page, /总题数/);
  assert.match(page, /正确数/);
  assert.match(page, /正确率/);
  assert.match(page, /用时/);
});

test("AI question page maps submission failures to fixed Chinese messages", () => {
  assert.match(page, /from "\.\/practice-submission\.mjs"/);
  assert.match(page, /getSubmissionErrorMessage,/);
  assert.match(page, /getOrCreateSubmissionPayload,/);
  assert.doesNotMatch(page, /setError\(cause as/);
});

test("AI practice retry reuses the exact frozen request body after a lost response", () => {
  const questions = [
    { id: "q-1", question_type: "CHOICE" },
    { id: "q-2", question_type: "MULTIPLE_CHOICE" },
  ];
  const first = getOrCreateSubmissionPayload(null, {
    submissionId: "submission-1",
    questions,
    answers: { "q-1": " A ", "q-2": "B,A" },
    batchStartedAt: 0,
    questionChangedAt: { "q-1": 1_000, "q-2": 5_000 },
    submittedAt: 8_000,
  });
  const retry = getOrCreateSubmissionPayload(first, {
    submissionId: "submission-2",
    questions,
    answers: { "q-1": "B", "q-2": "A" },
    batchStartedAt: 0,
    questionChangedAt: { "q-1": 9_000, "q-2": 10_000 },
    submittedAt: 12_000,
  });

  assert.deepEqual(retry, first);
  assert.equal(JSON.stringify(retry), JSON.stringify(first));
  assert.deepEqual(first.answers, [
    { question_id: "q-1", user_answer: "A", time_spent_seconds: 1 },
    { question_id: "q-2", user_answer: "A,B", time_spent_seconds: 7 },
  ]);
  assert.equal(first.answers.reduce((total, answer) => total + answer.time_spent_seconds, 0), 8);
});

test("AI practice only invalidates a submission for a normalized answer change or a new batch", () => {
  assert.equal(hasNormalizedAnswerChanged("A", " A ", "CHOICE"), false);
  assert.equal(hasNormalizedAnswerChanged("A,B", "B,A", "MULTIPLE_CHOICE"), false);
  assert.equal(hasNormalizedAnswerChanged("A", "B", "CHOICE"), true);

  const firstBatchPayload = getOrCreateSubmissionPayload(null, {
    submissionId: "submission-1",
    questions: [{ id: "q-1", question_type: "CHOICE" }],
    answers: { "q-1": "A" },
    batchStartedAt: 0,
    questionChangedAt: { "q-1": 1_000 },
    submittedAt: 2_000,
  });
  assert.equal(invalidateSubmissionPayload(firstBatchPayload, { currentAnswer: "A", nextAnswer: " A ", questionType: "CHOICE" }), firstBatchPayload);
  assert.equal(invalidateSubmissionPayload(firstBatchPayload, { currentAnswer: "A", nextAnswer: "B", questionType: "CHOICE" }), null);
  assert.equal(invalidateSubmissionPayload(firstBatchPayload, { isNewBatch: true }), null);

  const newBatchPayload = getOrCreateSubmissionPayload(invalidateSubmissionPayload(firstBatchPayload, { isNewBatch: true }), {
    submissionId: "submission-2",
    questions: [{ id: "q-3", question_type: "CHOICE" }],
    answers: { "q-3": "C" },
    batchStartedAt: 3_000,
    questionChangedAt: { "q-3": 4_000 },
    submittedAt: 5_000,
  });

  assert.notEqual(newBatchPayload.submission_id, firstBatchPayload.submission_id);
});

test("AI practice maps HTTP string codes to fixed Chinese messages", () => {
  assert.equal(getSubmissionErrorMessage({ code: "HTTP_401" }), "登录状态已失效，请重新登录后提交。");
  assert.equal(getSubmissionErrorMessage({ code: "HTTP_409" }), "题目审核或答案校验未通过，请重新出题后再试。");
  assert.equal(getSubmissionErrorMessage({ code: "HTTP_422" }), "题目审核或答案校验未通过，请重新出题后再试。");
  assert.equal(getSubmissionErrorMessage({ code: "HTTP_503" }), "出题服务暂时不可用，请稍后再试。");
  assert.equal(getSubmissionErrorMessage({ name: "AbortError" }), "提交超时，请稍后重试。");
});

test("AI practice associates unordered verified results by question ID", () => {
  const resultsByQuestionId = indexSubmissionResults([
    { question_id: "q-2", is_correct: false },
    { question_id: "q-1", is_correct: true },
  ]);

  assert.equal(resultsByQuestionId["q-1"].is_correct, true);
  assert.equal(resultsByQuestionId["q-2"].is_correct, false);
});
