import { expect, test } from "@playwright/test";

const PANEL_URL = "/host.html";

test.describe("RUNE sidebar panel", () => {
  test.beforeEach(async ({ page }) => {
    page.on("pageerror", (err) => {
      throw err;
    });
    await page.goto(PANEL_URL);
    // Wait for the panel iframe to mount and render at least one
    // rune-app custom element.
    const frame = page.frameLocator("iframe#panel");
    await frame.locator("rune-app").waitFor({ state: "attached" });
  });

  test("renders the sidebar nav with all four sections", async ({ page }) => {
    const frame = page.frameLocator("iframe#panel");
    const nav = frame.locator("rune-app nav");
    await expect(nav).toBeVisible();
    await expect(nav.getByRole("button", { name: /Devices/ })).toBeVisible();
    await expect(nav.getByRole("button", { name: /Sniffer/ })).toBeVisible();
    await expect(nav.getByRole("button", { name: /Actions/ })).toBeVisible();
    await expect(nav.getByRole("button", { name: /Settings/ })).toBeVisible();
  });

  test("devices view shows the populated mock list", async ({ page }) => {
    const frame = page.frameLocator("iframe#panel");
    await expect(frame.locator("rune-device-card")).toHaveCount(2, {
      timeout: 10_000,
    });
    await expect(frame.getByText("Bedroom fan")).toBeVisible();
    await expect(frame.getByText("Living room light")).toBeVisible();
  });

  test("sniffer view shows the captured signal mock", async ({ page }) => {
    const frame = page.frameLocator("iframe#panel");
    await frame
      .getByRole("button", { name: /Sniffer/ })
      .click();
    await expect(frame.getByText("AC remote")).toBeVisible({ timeout: 10_000 });
    await expect(frame.getByText("power").first()).toBeVisible();
  });

  test("actions view shows the binding mock", async ({ page }) => {
    const frame = page.frameLocator("iframe#panel");
    await frame.getByRole("button", { name: /Actions/ }).click();
    await expect(frame.getByText("Power on AC when warm")).toBeVisible({
      timeout: 10_000,
    });
  });

  test("settings view shows stat cards and entity tables", async ({ page }) => {
    const frame = page.frameLocator("iframe#panel");
    await frame.getByRole("button", { name: /Settings/ }).click();
    // Wait for the section swap to complete.
    await expect(frame.locator("rune-settings-view")).toBeVisible();
    await expect(
      frame.locator("rune-settings-view").getByText("Integration", { exact: true }),
    ).toBeVisible();
    await expect(
      frame.locator("rune-settings-view").getByText("Devices", { exact: true }),
    ).toBeVisible();
    await expect(
      frame
        .locator("rune-settings-view")
        .getByText("Available transmitters", { exact: false }),
    ).toBeVisible();
    await expect(
      frame
        .locator("rune-settings-view")
        .getByText("remote.broadlink_rm4_pro")
        .first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("add-device dialog opens and closes", async ({ page }) => {
    const frame = page.frameLocator("iframe#panel");
    await frame.getByRole("button", { name: /Add device/ }).first().click();
    // Wait for the first form field to render inside the dialog body.
    await expect(frame.locator("rune-input").first()).toBeVisible({
      timeout: 5_000,
    });
    // Close via Cancel — verify the dialog's ``open`` attribute clears.
    await frame.getByRole("button", { name: /Cancel/ }).click();
    await expect(
      frame.locator("rune-device-dialog").locator("sl-dialog[open]"),
    ).toHaveCount(0, { timeout: 5_000 });
  });

  test("skip-to-content link is keyboard reachable", async ({ page }) => {
    const frame = page.frameLocator("iframe#panel");
    const skip = frame.locator(".skip-link");
    await skip.focus();
    await expect(skip).toBeFocused();
  });

  test("no console errors on initial render", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await page.goto(PANEL_URL);
    const frame = page.frameLocator("iframe#panel");
    await frame.locator("rune-app").waitFor({ state: "attached" });
    // Allow microtask queue to settle.
    await page.waitForTimeout(250);
    expect(errors).toEqual([]);
  });
});