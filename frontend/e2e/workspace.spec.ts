import { expect, test } from "@playwright/test";
const password = process.env.E2E_PASSWORD;
test.beforeEach(async ({ page }) => {
  test.skip(
    !password,
    "Set E2E_PASSWORD to the seed password before running browser tests.",
  );
  await page.goto("/");
  await page.getByLabel("University email").fill("admin@timeforge.example");
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in to TimeForge" }).click();
  await expect(
    page.getByRole("heading", { name: /Welcome back/ }),
  ).toBeVisible();
  await expect(page.locator(".welcome-banner")).toBeVisible();
});
test("academic navigation, responsive layout and keyboard-accessible forms", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.screenshot({ path: "test-results/overview.png", fullPage: true });
  const routes = [
    "data/courses",
    "data/sections",
    "data/lecturers",
    "data/student-groups",
    "data/rooms",
    "data/constraints",
    "users",
    "data/departments",
    "data/academic-years",
    "data/terms",
    "data/buildings",
    "data/room-features",
    "data/time-slots",
    "audit",
    "availability",
    "analytics",
    "notifications",
    "guide",
  ];
  for (const route of routes) {
    await page.goto(`/#${route}`);
    await expect(page.locator("main h1")).toBeVisible();
    await expect(page.getByText("Loading workspace…")).toHaveCount(0);
    await expect(page.locator("main [role=alert]")).toHaveCount(0);
  }
  await page.goto("/#data/courses");
  await page.getByRole("button", { name: "Add Course", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/#dashboard");
  await expect(
    page.getByRole("heading", { name: /Welcome back/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("navigation")).toBeVisible();
  await page
    .getByRole("link", { name: "Timetable studio", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Timetable studio" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/mobile-studio.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
test("generates alternatives, validates edits, saves versions and publishes", async ({
  page,
}) => {
  await page.goto("/#planner");
  await page.getByRole("button", { name: "New timetable" }).click();
  const name = `Browser validation ${Date.now()}`;
  await page.getByLabel("Timetable name").fill(name);
  await page.getByLabel(/Academic term/).selectOption({ index: 1 });
  await page
    .getByRole("button", { name: "Create timetable", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Generate alternatives" }).click();
  await page.getByLabel("Alternatives", { exact: true }).fill("2");
  await page.getByLabel("Total search budget (seconds)").fill("20");
  await page.getByText("Limit generation scope").click();
  await page
    .getByLabel("sections", { exact: true })
    .selectOption(["1", "2", "3"]);
  await page.getByRole("button", { name: "Start generation" }).click();
  await expect(page.getByText(/^No hard conflicts$/i)).toBeVisible({
    timeout: 60000,
  });
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await expect(page.locator(".alternative")).toHaveCount(2);
  await page.screenshot({ path: "test-results/timetable.png", fullPage: true });
  await page.locator(".session").first().click();
  await page.getByLabel("Lock this session").check();
  await page.getByRole("button", { name: "Apply & validate" }).click();
  await expect(
    page.getByRole("button", { name: "Save version" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Save version" }).click();
  await expect(page.getByText("Unsaved changes", { exact: false })).toHaveCount(
    0,
  );
  await page.getByRole("button", { name: "Submit for review" }).click();
  await page.getByLabel("Decision notes").fill("Academic review requested");
  await page.getByRole("button", { name: "Confirm submit" }).click();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await page.getByRole("button", { name: "Confirm approve" }).click();
  await page.getByRole("button", { name: "Publish timetable" }).click();
  await page
    .getByLabel("Decision notes")
    .fill("Reviewed and accepted soft preferences");
  await page.getByRole("button", { name: "Confirm publish" }).click();
  await expect(page.locator(".planner-top .badge")).toHaveText(/published/i);
  await page.getByText("Export", { exact: true }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download ICS" }).click();
  expect((await download).suggestedFilename()).toContain(".ics");
});
