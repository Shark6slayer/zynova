import { test, expect } from "@playwright/test";

test("Zynova homepage loads without uncaught JavaScript errors", async ({ page }) => {
  const errors: string[] = [];

  page.on("pageerror", error => errors.push(error.message));

  const response = await page.goto("https://zynova.intellidev.in", {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });

  expect(response, "Homepage should return a response").not.toBeNull();
  expect(response!.status()).toBeLessThan(500);

  await expect(page.locator("body")).not.toBeEmpty();

  expect(errors, "Unexpected uncaught JavaScript errors").toEqual([]);
});
