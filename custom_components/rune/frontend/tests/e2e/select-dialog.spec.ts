import { expect, test } from "@playwright/test";

const PANEL_URL = "/host.html";

async function openFrame(page: import("@playwright/test").Page) {
  await page.goto(PANEL_URL);
  const frame = page.frameLocator("iframe#panel");
  await frame.locator("rune-app").waitFor({ state: "attached" });
  return frame;
}

test.describe("select inside dialog", () => {
  test.beforeEach(async ({ page }) => {
    page.on("pageerror", (err) => {
      throw err;
    });
  });

  for (const name of ["Fan", "Light", "Climate", "Cover", "Media player", "Switch", "Remote"]) {
    test(`category=${name} keeps dialog open`, async ({ page }) => {
      const frame = await openFrame(page);
      await frame
        .getByRole("button", { name: /Add device/ })
        .first()
        .click();
      await expect(frame.locator("rune-input").first()).toBeVisible({ timeout: 5_000 });

      const dialog = frame.locator("rune-dialog sl-dialog[open]").first();
      const select = frame.locator("rune-select sl-select").first();
      await select.locator('[part="combobox"]').click();
      await expect(select).toHaveAttribute("open", "");
      await select.locator("sl-option", { hasText: name }).first().click();
      await expect(dialog).toHaveAttribute("open", "", { timeout: 3_000 });

      // Second select (async transmitter) if visible.
      const selects = frame.locator("rune-select sl-select");
      const count = await selects.count();
      if (count > 1) {
        const second = selects.nth(1);
        await second.locator('[part="combobox"]').click();
        await expect(second).toHaveAttribute("open", "", { timeout: 5_000 });
        await second.locator("sl-option").first().click();
        await expect(dialog).toHaveAttribute("open", "", { timeout: 3_000 });
      }
    });
  }

  test("dismissing select by clicking overlay keeps dialog open, subsequent overlay click closes dialog", async ({
    page,
  }) => {
    const frame = await openFrame(page);
    await frame
      .getByRole("button", { name: /Add device/ })
      .first()
      .click();
    await expect(frame.locator("rune-input").first()).toBeVisible({ timeout: 5_000 });

    const dialog = frame.locator("rune-dialog sl-dialog[open]").first();
    const select = frame.locator("rune-select sl-select").first();
    await select.locator('[part="combobox"]').click();
    await expect(select).toHaveAttribute("open", "");

    // Click on dialog overlay backdrop: dismisses select, dialog stays open
    const overlay = dialog.locator('[part="overlay"]');
    await overlay.click({ position: { x: 10, y: 10 } });
    await expect(select).not.toHaveAttribute("open", "");
    await expect(dialog).toHaveAttribute("open", "", { timeout: 3_000 });

    // Subsequent click on overlay with no select open: dialog closes
    await overlay.click({ position: { x: 10, y: 10 } });
    await expect(frame.locator("rune-dialog sl-dialog[open]")).toHaveCount(0, { timeout: 3_000 });
  });
});
