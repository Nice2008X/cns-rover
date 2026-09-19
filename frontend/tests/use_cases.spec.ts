import { test, expect } from "@playwright/test";

const obstacleScenario = {
  name: "malecns_obstacle_avoidance",
  task: "Find the red ball and stop near it.",
  size: [10, 10],
  start: [2, 5, 0],
  target: [7, 5, 0.15],
  obstacles: [[4, 5.4, 0.4]],
  timeout: 60,
  success_distance: 0.5,
  stop_speed: 0.03,
  stop_duration: 0.5,
};

async function configure(request: any, payload: any) {
  const response = await request.post("/api/configure", { data: payload });
  expect(response.ok()).toBeTruthy();
}

test.describe.serial("CNS Rover use-case screenshots", () => {
  test("native MaleCNS obstacle avoidance", async ({ page, request }) => {
    await configure(request, { controller: "malecns", scenario: obstacleScenario });
    await page.goto("/");
    await request.post("/api/speed", { data: { value: 4 } });
    await request.post("/api/run", { data: {} });
    await expect.poll(
      async () => (await (await request.get("/api/state")).json()).debug.mode,
      { timeout: 15000 },
    ).toMatch(/AVOID|APPROACH|STOP/);
    await page.screenshot({ path: "../docs/screenshots/use-case-native-avoidance.png", fullPage: true });
  });

  test("controller and model selection", async ({ page, request }) => {
    await request.post("/api/pause", { data: {} });
    await page.goto("/");
    await page.getByRole("navigation").getByRole("button", { name: "Models", exact: true }).click();
    await page.locator('input[value="malecns"]').check();
    await page.screenshot({ path: "../docs/screenshots/use-case-model-selection.png", fullPage: true });
  });

  test("environment authoring", async ({ page, request }) => {
    await configure(request, { controller: "baseline", scenario: obstacleScenario });
    await page.goto("/");
    await page.getByRole("navigation").getByRole("button", { name: "Environment", exact: true }).click();
    await page.getByRole("button", { name: "Occluded target", exact: false }).click();
    await page.screenshot({ path: "../docs/screenshots/use-case-environment-editor.png", fullPage: true });
  });

  test("synchronized replay inspection", async ({ page, request }) => {
    await configure(request, { controller: "baseline" });
    await page.goto("/");
    await request.post("/api/speed", { data: { value: 4 } });
    await request.post("/api/run", { data: {} });
    await expect(page.getByRole("heading", { name: "Task Completed" })).toBeVisible({ timeout: 15000 });
    const timeline = page.getByRole("slider", { name: "Replay timeline" });
    await timeline.fill("12");
    await page.getByRole("tab", { name: "Model I/O" }).click();
    await expect(page.locator(".replay-banner")).toBeVisible();
    await page.screenshot({ path: "../docs/screenshots/use-case-replay-debugger.png", fullPage: true });
  });

  test("matched controller analysis", async ({ page, request }) => {
    await request.post("/api/reset", { data: {} });
    await page.goto("/");
    await page.getByRole("navigation").getByRole("button", { name: "Analysis", exact: true }).click();
    await page.getByLabel("Seeds per controller").fill("1");
    const native = page.locator(".batch-models label").nth(3).locator("input");
    await native.check();
    await page.screenshot({ path: "../docs/screenshots/use-case-analysis.png", fullPage: true });
  });
});
