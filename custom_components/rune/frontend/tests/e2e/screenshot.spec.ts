import { test } from "@playwright/test";

const PANEL_URL = "/host.html";

async function openFrame(page: import("@playwright/test").Page) {
  await page.goto(PANEL_URL);
  const frame = page.frameLocator("iframe#panel");
  await frame.locator("rune-app").waitFor({ state: "attached" });
  return frame;
}

test("screenshot dialog", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 1100 });
  const frame = await openFrame(page);
  await frame
    .getByRole("button", { name: /Add device/ })
    .first()
    .click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: "test-results/dialog-closed.png", fullPage: false });

  const selects = frame.locator("rune-select");
  // Open the IR transmitter dropdown (nth 1) to see rich rows.
  await selects.nth(1).locator(".display").click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: "test-results/dropdown-open.png", fullPage: false });

  // Pick the first option to close dropdown and verify combobox rich display.
  await frame.locator("rune-select sl-select").nth(1).locator("sl-option").first().click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: "test-results/dialog-selected.png", fullPage: false });
});
