import { expect, test } from '@playwright/test';

test('FalkorDB selector is explanatory only and leaves the mission story unchanged', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');

  const section = page.locator('#falkordb');
  const activePhase = page.locator('.sequence-list button[aria-current="step"]');
  const phaseBefore = await activePhase.innerText();
  const startUrl = page.url();
  const selector = page.getByRole('group', { name: 'FalkorDB capabilities' });
  const propertyGraph = selector.getByRole('button', { name: /Property graph/i });
  await propertyGraph.focus();
  await page.keyboard.press('Tab');
  await page.keyboard.press('Tab');
  await page.keyboard.press('Space');

  const versionFenced = selector.getByRole('button', { name: /Version-fenced writes/i });
  await expect(versionFenced).toHaveAttribute('aria-pressed', 'true');
  await expect(section.locator('.fdb-capability-copy h3')).toContainText('version before its graph write');
  await expect(activePhase).toHaveText(phaseBefore, { useInnerText: true });
  expect(page.url()).toBe(startUrl);
  await expect(page.locator('#falkordb')).toContainText(/no query runs from this page/i);
});
