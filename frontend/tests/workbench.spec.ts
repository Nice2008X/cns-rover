import { test, expect } from "@playwright/test";
test("cockpit, completion, synchronized replay, configuration, and batch", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Top-Down World (Ground Truth)" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/cockpit-ready.png",
    fullPage: true,
  });
  await page
    .locator(".run-controls")
    .getByRole("button", { name: "Run", exact: true })
    .click();
  await expect(page.locator(".status")).toHaveText("RUNNING");
  await page
    .locator(".run-controls")
    .getByRole("button", { name: "Pause", exact: true })
    .click();
  await expect(page.locator(".status")).toHaveText("PAUSED");
  await request.post("/api/speed", { data: { value: 4 } });
  await page
    .locator(".run-controls")
    .getByRole("button", { name: "Run", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Task Completed" }),
  ).toBeVisible({ timeout: 15000 });
  await page.screenshot({
    path: "test-results/cockpit-completed.png",
    fullPage: true,
  });
  await page.getByRole("slider", { name: "Replay timeline" }).fill("15");
  await expect(page.locator(".replay-banner")).toContainText("frame 15");
  await page.getByRole("tab", { name: "Model I/O" }).click();
  await expect(page.locator(".debug-content")).toContainText('"frame_id": 15');
  await page.getByRole("button", { name: "Return to live" }).click();
  await expect(page.locator(".replay-banner")).toHaveCount(0);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Environment", exact: true })
    .click();
  await page.getByRole("button", { name: "Target behind vehicle" }).click();
  await page.getByRole("button", { name: "Apply & create new run" }).click();
  await expect(page.locator(".experiment-name")).toContainText("behind");
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Tasks", exact: true })
    .click();
  await page.getByLabel("Timeout (seconds)").fill("1");
  await page.getByRole("button", { name: "Apply & create new run" }).click();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Analysis", exact: true })
    .click();
  await page.getByLabel("Seeds per controller").fill("2");
  await page.getByRole("button", { name: "Run 2 tests" }).click();
  await expect(page.locator(".batch-progress")).toContainText(
    "Batch complete",
    { timeout: 15000 },
  );
  await expect(page.locator(".summary-cards")).toContainText("2");
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Runs / Logs", exact: true })
    .click();
  await expect(page.locator("tbody tr")).not.toHaveCount(0);
  await page
    .getByRole("button", { name: "Replay", exact: true })
    .first()
    .click();
  await expect(page.locator(".replay-banner")).toBeVisible();
  expect(errors).toEqual([]);
});
test("mobile navigation and cockpit fit viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Top-Down World (Ground Truth)" }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: "test-results/cockpit-mobile.png",
    fullPage: true,
  });
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Models", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Controller selection" }),
  ).toBeVisible();
});

test("environment editing, invalid configuration, and settings", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await request.post("/api/reset", { data: {} });
  await page.goto("/");
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Environment", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Simple arena", exact: false })
    .click();
  await page.getByRole("button", { name: "Add obstacle", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Obstacle 1", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Remove selected", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Obstacle 1", exact: true }),
  ).toHaveCount(0);
  const target = page
    .locator(
      ".environment-editor svg[aria-label^='Environment editor'] > circle",
    )
    .first();
  const bounds = await target.boundingBox();
  if (!bounds) throw Error("Target is not rendered");
  await page.mouse.move(
    bounds.x + bounds.width / 2,
    bounds.y + bounds.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(
    bounds.x + bounds.width / 2 + 20,
    bounds.y + bounds.height / 2,
    { steps: 4 },
  );
  await page.mouse.up();
  await expect(page.getByLabel("Target X (m)")).not.toHaveValue("6");
  await page.getByLabel("Target X (m)").fill("0");
  await page.getByRole("button", { name: "Apply & create new run" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Objects must fit inside the room",
  );
  await page.getByLabel("Target X (m)").fill("6");
  await page.getByRole("button", { name: "Apply & create new run" }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Settings", exact: true })
    .click();
  await page.getByLabel("Smooth camera enlargement").check();
  await page.reload();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Settings", exact: true })
    .click();
  await expect(page.getByLabel("Smooth camera enlargement")).toBeChecked();
  expect(errors).toEqual([]);
});

test("native MaleCNS selection exposes neural and avoidance telemetry", async ({ page, request }) => {
  await request.post("/api/configure", { data: { controller: "baseline", scenario: { timeout: 30 } } });
  await page.goto("/");
  await page.getByRole("navigation").getByRole("button", { name: "Models", exact: true }).click();
  await page.locator('input[value="malecns"]').check();
  await page.getByRole("button", { name: "Apply & create new run" }).click();
  await expect.poll(async () => (await (await request.get("/api/state")).json()).controller).toBe("malecns");
  await request.post("/api/run", { data: {} });
  await expect.poll(async () => (await (await request.get("/api/state")).json()).debug.active_neurons).toBeGreaterThan(0);
  await request.post("/api/pause", { data: {} });
  const state = await (await request.get("/api/state")).json();
  expect(state.debug).toHaveProperty("neural_proximity");
  expect(state.debug).toHaveProperty("safety_override");
  await request.post("/api/configure", { data: { controller: "baseline" } });
});
