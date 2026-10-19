import { expect, test } from '@playwright/test';

test('judge journey prioritizes proof, keeps explanations static, and fits 320px', async ({ page }) => {
  // Isolate only the third-party video document; keep all app/runtime requests observable.
  // Real YouTube playback is verified separately against production.
  await page.route('https://www.youtube-nocookie.com/embed/**', route => route.fulfill({
    status: 200, contentType: 'text/html', body: '<!doctype html><title>YouTube transport isolated for static-control test</title>',
  }));
  const mutations: string[] = [];
  page.on('request', request => {
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())) mutations.push(request.url());
  });
  await page.setViewportSize({ width: 320, height: 760 });
  await page.goto('/');

  const hero = page.locator('.hero');
  const heroLinks = hero.getByRole('link');
  await expect(heroLinks.nth(0)).toHaveAccessibleName(/run the simulation/i);
  await expect(heroLinks.nth(1)).toHaveAccessibleName(/inspect the evidence/i);
  await expect(heroLinks.nth(2)).toHaveAccessibleName(/watch product film/i);
  await expect(heroLinks.nth(0)).toHaveAttribute('href', 'https://witness-fleet-guglxni.eastus.cloudapp.azure.com/demo');
  await expect(heroLinks.nth(1)).toHaveAttribute('href', '#judge');

  await page.getByRole('button', { name: /open navigation menu/i }).click();
  const startHere = page.getByRole('link', { name: 'Start here', exact: true });
  await expect(startHere).toBeVisible();
  await startHere.click();
  await expect(page).toHaveURL(/#judge$/);
  await expect(page.locator('#judge')).toBeVisible();

  await page.locator('.judge-look-for summary').click();
  await expect(page.locator('.judge-look-for')).toHaveAttribute('open', '');
  await expect(page.locator('.judge-look-for')).toContainText(/configured demo-owner release/i);
  expect(mutations).toEqual([]);

  const layout = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth,
    body: document.body.scrollWidth,
  }));
  expect(layout.document).toBeLessThanOrEqual(layout.viewport);
  expect(layout.body).toBeLessThanOrEqual(layout.viewport);

  const sectionOrder = await page.locator('main').evaluate(main =>
    [...main.children].map(element => element.id || element.className.toString().split(' ')[0]),
  );
  expect(sectionOrder.indexOf('hero')).toBeLessThan(sectionOrder.indexOf('judge'));
  expect(sectionOrder.indexOf('judge')).toBeLessThan(sectionOrder.indexOf('principle'));
  expect(sectionOrder.indexOf('principle')).toBeLessThan(sectionOrder.indexOf('falkordb'));
  expect(sectionOrder.indexOf('falkordb')).toBeLessThan(sectionOrder.indexOf('evidence'));
  expect(sectionOrder.indexOf('evidence')).toBeLessThan(sectionOrder.indexOf('film'));
});
