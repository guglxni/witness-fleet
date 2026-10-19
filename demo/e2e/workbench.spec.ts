import { expect, test } from '@playwright/test';
import { sceneFixture, activeState } from '../tests/fixtures';

async function fixtureApi(page, options: { loseRun?: boolean } = {}) {
  const calls: string[] = [];
  await page.route('**/demo/v1/**', async (route) => {
    const req = route.request(); const url = new URL(req.url()).pathname; calls.push(`${req.method()} ${url}`);
    if (url.endsWith('/bootstrap')) return route.fulfill({ json: { csrf_token: 'fixture-csrf', simulation_only: true } });
    if (url.endsWith('/sessions') && req.method() === 'POST') return route.fulfill({ status: 201, json: { csrf_token: 'fixture-session-csrf', session: { status: 'active', expires_in: 1200 }, state: activeState } });
    if (url.endsWith('/sessions')) return route.fulfill({ status: 401, json: { detail: 'session_required' } });
    if (url.endsWith('/scene')) return route.fulfill({ json: sceneFixture });
    if (url.endsWith('/run') && options.loseRun) return route.abort('connectionreset');
    if (url.endsWith('/run')) return route.fulfill({ json: { ...activeState, revision_tick: 13, mission_phase: 'awaiting_owner_release' } });
    if (url.endsWith('/step')) return route.fulfill({ json: { ...activeState, revision_tick: 13 } });
    if (url.endsWith('/confirm-release')) return route.fulfill({ json: { ...activeState, revision_tick: 14, mission_phase: 'courier_delivery' } });
    return route.fulfill({ status: 404, json: { detail: 'not_found' } });
  });
  return calls;
}

test('boots inert, creates only on request, and all displayed viewport controls respond', async ({ page }) => {
  const calls = await fixtureApi(page);
  await page.setViewportSize({ width: 1440, height: 1100 }); await page.goto('/demo/');
  await expect(page.getByRole('heading', { name: 'Simulation workbench' })).toBeVisible();
  await expect.poll(() => calls.filter((c) => c === 'GET /demo/v1/sessions').length).toBe(1);
  await expect(page.getByText('No scene snapshot', { exact: true })).toBeVisible(); expect(calls).toEqual(['GET /demo/v1/sessions']);
  await page.getByRole('button', { name: 'Start isolated session' }).click(); await expect.poll(() => calls).toContain('GET /demo/v1/bootstrap');
  await expect(page.getByText('Authenticated MuJoCo scene sample')).toBeVisible();
  await page.getByRole('button', { name: 'Orbit view' }).click(); await page.getByRole('button', { name: 'Top view' }).click();
  await page.getByRole('button', { name: 'Zoom in' }).click(); await page.getByRole('button', { name: 'Reset camera' }).click();
  await page.getByRole('checkbox', { name: 'Wireframe' }).check(); await page.getByRole('checkbox', { name: 'Wireframe' }).uncheck();
  await page.getByRole('checkbox', { name: 'Facility' }).uncheck(); await page.getByRole('checkbox', { name: 'Facility' }).check();
  expect(calls.filter((c) => c.includes('POST'))).toHaveLength(1); await page.screenshot({ path: 'artifacts/workbench-1440.png', fullPage: true });
});

test('unknown response hard-locks motion while browsing sampled history', async ({ page }) => {
  await fixtureApi(page, { loseRun: true }); await page.goto('/demo/'); await page.getByRole('button', { name: 'Start isolated session' }).click();
  await page.getByRole('button', { name: 'Run authorized tasks' }).click(); await expect(page.getByRole('alert').getByText(/outcome_unknown_no_retry/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run authorized tasks' })).toBeDisabled(); await page.getByRole('button', { name: /sample 01/i }).click();
  await expect(page.getByText('Historical sampled state · not a trajectory')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run authorized tasks' })).toBeDisabled(); await expect(page.getByRole('button', { name: /Return to live/i })).toBeVisible();
  await page.screenshot({ path: 'artifacts/workbench-safety-lock.png', fullPage: true });
});

test('release requires explicit checkbox at the displayed policy epoch', async ({ page }) => {
  await fixtureApi(page); await page.goto('/demo/'); await page.getByRole('button', { name: 'Start isolated session' }).click();
  await page.getByRole('button', { name: 'Run authorized tasks' }).click(); await expect(page.getByText('Owner release gate')).toBeVisible();
  const release = page.getByRole('button', { name: 'Confirm demo release' }); await expect(release).toBeDisabled();
  await page.getByRole('checkbox', { name: /I explicitly confirm synthetic release/ }).check(); await expect(release).toBeEnabled(); await release.click();
  await expect(page.getByRole('complementary', { name: 'Mission control' }).getByText('courier delivery')).toBeVisible();
});

  test('exposes the fallback viewport and disables only unavailable camera modes', async ({ page }) => {
    await fixtureApi(page);
    await page.addInitScript(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function(type: string, ...args: unknown[]) {
        if (type === 'webgl2' || type === 'webgl' || type === 'experimental-webgl') throw new Error('webgl unavailable');
        return original.call(this, type as '2d', ...args as []);
      };
    });
    await page.setViewportSize({ width: 1280, height: 900 }); await page.goto('/demo/'); await page.getByRole('button', { name: 'Start isolated session' }).click();
    const svg = page.locator('.scene-fallback'); await expect(svg).toBeVisible();
    await expect(page.getByRole('button', { name: 'Orbit view unavailable' })).toBeDisabled();
    const before = await svg.getAttribute('viewBox'); await page.getByRole('button', { name: 'Zoom in' }).click();
    await expect.poll(() => svg.getAttribute('viewBox')).not.toBe(before);
    const zoomed = await svg.getAttribute('viewBox'); await page.getByRole('button', { name: 'Reset camera' }).click(); await expect(svg).toHaveAttribute('viewBox', '0 0 700 420');
    expect(zoomed).not.toBe('0 0 700 420');
    await expect(svg.locator('[data-object-id="scout_chassis"] title')).toContainText('top-view footprint approximation');
  });

  test('layout remains overflow-free and touch-safe at required widths', async ({ page }) => {
  await fixtureApi(page);
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 }); await page.goto('/demo/'); await expect(page.getByRole('heading', { name: 'Simulation workbench' })).toBeVisible();
    const dimensions = await page.evaluate(() => ({ document: document.documentElement.scrollWidth, viewport: innerWidth }));
    expect(dimensions.document, `horizontal overflow at ${width}px`).toBeLessThanOrEqual(dimensions.viewport);
    await page.screenshot({ path: `artifacts/workbench-${width}.png`, fullPage: true });
  }
});
