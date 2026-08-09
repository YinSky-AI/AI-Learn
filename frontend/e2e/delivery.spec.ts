import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

async function runCompose(...args: string[]) {
  const { execFileSync } = await import("node:child_process");
  execFileSync("docker", ["compose", ...args], {
    cwd: "..",
    encoding: "utf8",
    stdio: "pipe",
  });
}

test("登录页支持键盘校验且没有严重无障碍问题", async ({ page }) => {
  await page.goto("/login");

  await expect(page.getByRole("heading", { name: "AI学堂" })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByPlaceholder("请输入用户名")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByPlaceholder("请输入密码")).toBeFocused();

  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page.getByText("请输入用户名和密码")).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((item) => item.impact === "critical")).toEqual([]);
});

test("后端健康端点保持公开契约", async ({ request }) => {
  const apiBaseUrl = process.env.API_BASE_URL || "http://localhost:8000";
  const response = await request.get(`${apiBaseUrl}/health`);

  expect(response.ok()).toBeTruthy();
  await expect(response.json()).resolves.toMatchObject({
    code: "SUCCESS",
    message: "服务运行正常",
    data: { status: "healthy" },
  });
});

test("PWA manifest 和离线导航提供真实降级页面", async ({ page }) => {
  const manifestResponse = await page.request.get("/manifest.json");
  expect(manifestResponse.ok()).toBeTruthy();
  await expect(manifestResponse.json()).resolves.toMatchObject({
    display: "standalone",
    lang: "zh-CN",
  });

  await page.goto("/offline");
  await expect(page.getByRole("heading", { name: "网络连接断开" })).toBeVisible();
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.reload();
  await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller));

  await runCompose("stop", "nginx-gateway");
  try {
    await page.goto("/delivery-network-failure", {
      waitUntil: "domcontentloaded",
      timeout: 15_000,
    });
    await expect(page.getByRole("heading", { name: "网络连接断开" })).toBeVisible();
  } finally {
    await runCompose("start", "nginx-gateway");
    await expect
      .poll(
        async () => {
          try {
            return (await page.request.get("/login")).status();
          } catch {
            return 0;
          }
        },
        { timeout: 60_000 },
      )
      .toBe(200);
  }
});

const adaptiveScenarios = [
  {
    slug: "correct",
    name: "正确答案",
    answer: "x=4",
    isCorrect: true,
    steps: undefined,
    diagnosis: {
      status: "not_required",
      knowledge_point_code: "normalize_coefficient",
      first_invalid_step: null,
      evidence: "本次作答正确，无需诊断。",
      confidence: 1,
    },
    expected: "本题回答正确，无需错因诊断",
    expectsRecommendation: false,
  },
  {
    slug: "diagnosed",
    name: "可诊断移项错误",
    answer: "x=-4",
    isCorrect: false,
    steps: ["x+3=7", "x=-4"],
    diagnosis: {
      status: "diagnosed",
      knowledge_point_code: "move_terms_sign",
      misconception_code: "sign_transfer_error",
      first_invalid_step: 2,
      evidence: "第 1 步到第 2 步不再等价。",
      confidence: 0.95,
    },
    expected: "从第 2 步开始",
    expectsRecommendation: true,
  },
  {
    slug: "insufficient",
    name: "证据不足",
    answer: "x=5",
    isCorrect: false,
    steps: undefined,
    diagnosis: {
      status: "insufficient_evidence",
      knowledge_point_code: "equation_equivalence",
      first_invalid_step: null,
      evidence: "没有可验证的相邻步骤。",
      confidence: 0,
    },
    expected: "现有信息还不足以确定具体错因",
    expectsRecommendation: true,
  },
] as const;

for (const scenario of adaptiveScenarios) {
  test(`AI 方程练习展示${scenario.name}诊断且控制台无错误`, async ({ page }, testInfo) => {
    const consoleErrors: string[] = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    await page.addInitScript(() => {
      const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }));
      localStorage.setItem("alp_access_token", `header.${payload}.signature`);
      localStorage.setItem("alp_refresh_token", "test-refresh-token");
    });
    await page.route("**/api/v1/**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      const respond = (data: unknown) => route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ code: "SUCCESS", message: "ok", data }),
      });
      if (path.endsWith("/questions/generate")) {
        return respond({
          batch_id: "22222222-2222-2222-2222-222222222222",
          status: "completed",
          total_generated: 1,
          questions: [{
            id: "11111111-1111-1111-1111-111111111111",
            question_body: "解方程 x+3=7。",
            question_type: "FILL_BLANK",
            difficulty_level: "DIFF_MEDIUM",
            quality_status: "passed",
            knowledge_tags: ["move_terms_sign"],
          }],
        });
      }
      if (path.includes("/questions/batches/") && path.endsWith("/submit")) {
        return respond({
          submission_id: "33333333-3333-3333-3333-333333333333",
          batch_id: "22222222-2222-2222-2222-222222222222",
          total_count: 1,
          correct_count: scenario.isCorrect ? 1 : 0,
          accuracy_rate: scenario.isCorrect ? 1 : 0,
          time_spent_seconds: 3,
          results: [{
            question_id: "11111111-1111-1111-1111-111111111111",
            is_correct: scenario.isCorrect,
            correct_answer: "x=4",
            explanation: "等式两边同时除以 2。",
            diagnosis_job_id: "44444444-4444-4444-4444-444444444444",
            diagnosis_status: "pending",
          }],
          gamification: {},
        });
      }
      if (path.includes("/adaptive/diagnoses/")) {
        return respond({
          job_id: "44444444-4444-4444-4444-444444444444",
          state: "succeeded",
          diagnosis: scenario.diagnosis,
          mastery: { before: 0.5, after: scenario.isCorrect ? 0.65 : 0.42, model_version: "bkt-v1" },
          next_action: {
            decision_id: "55555555-5555-5555-5555-555555555555",
            action: scenario.isCorrect ? "practice_same_skill" : scenario.diagnosis.status === "diagnosed" ? "practice_misconception" : "ask_diagnostic_question",
            reason_codes: scenario.diagnosis.status === "diagnosed" ? ["diagnosed_misconception"] : ["insufficient_evidence"],
          },
        });
      }
      if (path.endsWith("/users/me")) {
        return respond({ id: "user-1", nickname: "验收学生", email: "student@example.test", birth_date: "2012-01-01", age_group: "AGE_12_14", avatar_url: null, total_score: 0, streak_days: 0, behavior_profile: {}, last_login_date: null, created_at: "2026-01-01", updated_at: "2026-01-01" });
      }
      return respond({ items: [], total: 0 });
    });

    await page.goto("/ai-questions");
    await page.getByPlaceholder("例如：小学分数加法").fill("一元一次方程");
    await page.getByRole("button", { name: "开始出题" }).click();
    await page.getByLabel("填空 1").fill(scenario.answer);
    if (scenario.steps) {
      await page.getByRole("textbox", { name: "第 1 步", exact: true }).fill(scenario.steps[0]);
      await page.getByRole("button", { name: "添加一步" }).click();
      await page.getByRole("textbox", { name: "第 2 步", exact: true }).fill(scenario.steps[1]);
    }
    await page.getByRole("button", { name: "提交全部答案" }).click();

    await expect(page.getByText(scenario.expected, { exact: false })).toBeVisible();
    if (scenario.expectsRecommendation) {
      await expect(page.getByText("为什么推荐下一步", { exact: true })).toBeVisible();
    }
    expect(consoleErrors).toEqual([]);
    await page.screenshot({
      path: `../test/acceptance/adaptive-learning/task9-${testInfo.project.name}-${scenario.slug}.png`,
      fullPage: true,
    });
  });
}
