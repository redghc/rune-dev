import { chromium } from "playwright";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 1100 } });
await page.goto("http://127.0.0.1:5180/host.html");
await page.waitForSelector("rune-app");
await page
  .getByRole("button", { name: /Add device/ })
  .first()
  .click();
await page.waitForTimeout(500);
await page.screenshot({ path: "/tmp/dialog-closed.png" });

const selects = page.locator("rune-select sl-select");
await selects.nth(0).locator('[part="combobox"]').click();
await page.waitForTimeout(500);
await page.screenshot({ path: "/tmp/dialog-open.png" });

await browser.close();
