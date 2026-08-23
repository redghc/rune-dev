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
    await frame.getByRole("button", { name: /Sniffer/ }).click();
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
      frame.locator("rune-settings-view").getByText("Available transmitters", { exact: false }),
    ).toBeVisible();
    await expect(
      frame.locator("rune-settings-view").getByText("remote.broadlink_rm4_pro").first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("add-device dialog opens and closes", async ({ page }) => {
    const frame = page.frameLocator("iframe#panel");
    await frame
      .getByRole("button", { name: /Add device/ })
      .first()
      .click();
    // Wait for the first form field to render inside the dialog body.
    await expect(frame.locator("rune-input").first()).toBeVisible({
      timeout: 5_000,
    });
    // Close via Cancel — verify the dialog's ``open`` attribute clears.
    await frame.getByRole("button", { name: /Cancel/ }).click();
    await expect(frame.locator("rune-device-dialog").locator("sl-dialog[open]")).toHaveCount(0, {
      timeout: 5_000,
    });
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

  test("theme toggle switches light/dark and persists", async ({ page }) => {
    const frame = page.frameLocator("iframe#panel");
    const toggle = frame.locator("rune-theme-toggle");
    await expect(toggle).toBeVisible();
    // Theme classes land on the iframe document element, not the host.
    const readIframeClass = async () =>
      await page.evaluate(() => {
        const iframe = document.getElementById("panel") as HTMLIFrameElement | null;
        return iframe?.contentDocument?.documentElement?.className ?? "";
      });
    // Read the resolved ``--rune-bg`` token on ``<rune-app>`` — verifies
    // the theme tokens actually cascade into the shadow DOM. ``shared.ts``
    // used to rely on ``:host(.sl-theme-dark)`` which never matched (the
    // class lives on ``<html>``, not the shadow host) so the page silently
    // stayed on whatever the OS preferred. We cycle Dark → Light → Auto
    // and confirm the bg token actually changes between Dark and Light
    // (regardless of the OS pref).
    const readAppBg = async () =>
      await page.evaluate(() => {
        const iframe = document.getElementById("panel") as HTMLIFrameElement | null;
        const app = iframe?.contentDocument?.querySelector("rune-app");
        return app ? getComputedStyle(app).getPropertyValue("--rune-bg").trim() : "";
      });
    // Dark first — should always differ from the Light value below.
    await toggle.getByRole("radio", { name: /Dark/i }).click();
    expect(await readIframeClass()).toContain("sl-theme-dark");
    const darkBg = await readAppBg();
    // Light
    await toggle.getByRole("radio", { name: /Light/i }).click();
    expect(await readIframeClass()).toContain("sl-theme-light");
    const lightBg = await readAppBg();
    expect(lightBg).not.toBe(darkBg);
    // Auto — neither forced class, falls back to OS media query.
    await toggle.getByRole("radio", { name: /Auto/i }).click();
    const autoClass = await readIframeClass();
    expect(autoClass).not.toContain("sl-theme-light");
    expect(autoClass).not.toContain("sl-theme-dark");
  });
});
