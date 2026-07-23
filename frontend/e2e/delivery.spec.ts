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
