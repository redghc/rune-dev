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
      const selects = frame.locator("rune-select");
      const first = selects.nth(0);
      const firstSl = first.locator("sl-select");
      await first.locator(".display").click();
      await expect(firstSl).toHaveAttribute("open", "");
      await firstSl.locator("sl-option", { hasText: name }).first().click();
      await expect(dialog).toHaveAttribute("open", "", { timeout: 3_000 });

      // Second select (async transmitter) if visible.
      const count = await selects.count();
      if (count > 1) {
        const second = selects.nth(1);
        const secondSl = second.locator("sl-select");
        await second.locator(".display").click();
        await expect(secondSl).toHaveAttribute("open", "", { timeout: 5_000 });
        await secondSl.locator("sl-option").first().click();
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
    const select = frame.locator("rune-select").first();
    const selectSl = select.locator("sl-select");
    await select.locator(".display").click();
    await expect(selectSl).toHaveAttribute("open", "");

    // Click on dialog overlay backdrop: dismisses select, dialog stays open
    const overlay = dialog.locator('[part="overlay"]');
    await overlay.click({ position: { x: 10, y: 10 } });
    await expect(selectSl).not.toHaveAttribute("open", "");
    await expect(dialog).toHaveAttribute("open", "", { timeout: 3_000 });

    // Subsequent click on overlay with no select open: dialog closes
    await overlay.click({ position: { x: 10, y: 10 } });
    await expect(frame.locator("rune-dialog sl-dialog[open]")).toHaveCount(0, { timeout: 3_000 });
  });

  test("device dialog exposes both IR and RF transmitter/receiver fields and validates at least one transmitter", async ({
    page,
  }) => {
    const frame = await openFrame(page);
    await frame
      .getByRole("button", { name: /Add device/ })
      .first()
      .click();
    await expect(frame.locator("rune-input").first()).toBeVisible({ timeout: 5_000 });

    // Verify IR & RF transmitter fields are visible
    const selects = frame.locator("rune-select");
    const irTx = selects.nth(1);
    const rfTx = selects.nth(2);
    const irRx = selects.nth(3);
    const rfRx = selects.nth(4);

    await expect(irTx).toBeVisible();
    await expect(rfTx).toBeVisible();
    await expect(irRx).toBeVisible();
    await expect(rfRx).toBeVisible();

    // Fill device name
    const nameInput = frame.locator("rune-input").first().locator("input");
    await nameInput.fill("Test Dual IR-RF Fan");

    // Click Create without transmitters -> shows error
    await frame.getByRole("button", { name: /Create/ }).click();
    await expect(
      frame.locator(".err", { hasText: /At least one transmitter|Se requiere al menos un emisor/ }),
    ).toBeVisible({ timeout: 3_000 });

    // Pick IR transmitter
    const irTxSl = irTx.locator("sl-select");
    await irTx.locator(".display").click();
    await irTxSl.locator("sl-option").first().click();

    // Create device should now submit without the transmitter error
    await frame.getByRole("button", { name: /Create/ }).click();
    await expect(frame.locator(".err")).toHaveCount(0, { timeout: 3_000 });
  });
});
