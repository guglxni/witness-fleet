import { expect, test, type Page } from '@playwright/test';

async function assertNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
}

test('empty backend stays evidence-first at supported viewport', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');

  await expect(page.getByRole('heading', { name: /Physically clear\. Loaded courier still restricted\./i })).toBeVisible();
  await expect(page.getByText(/NOT A LIVE EPISODE CLAIM/i)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Waiting for incident/backend state' })).toBeVisible();
  await expect(page.getByText('No incident loaded', { exact: true })).toBeVisible();
  await expect(page.getByText('API reachable', { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('region', { name: 'Decision principle and live gate status' }).locator('.principle-gate').first().locator('strong')).toHaveText('Unknown');
  await expect(page.getByRole('button', { name: /Create incident/i })).toBeEnabled();

  const response = await page.request.get('/api/state');
  expect(response.status()).toBe(503);
  await expect(page.getByRole('heading', { name: 'Robot pose projection', exact: true })).toHaveCount(0);
  await assertNoHorizontalOverflow(page);
  expect(errors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('evidence-first-waiting.png'), fullPage: true });
});

test('empty backend console has no horizontal overflow at narrow and short viewports', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 320, height: 700 });
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Physically clear\. Loaded courier still restricted\./i })).toBeVisible();
  await expect(page.getByRole('button', { name: /Create incident/i })).toBeVisible();
  await assertNoHorizontalOverflow(page);
  expect(errors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('evidence-first-waiting-narrow.png'), fullPage: true });
});

test('synthetic connected projection keeps tasks, receipts, and source evidence distinct', async ({ page }, testInfo) => {
  // Explicit synthetic test-only API data. It is never served by the frontend or production backend.
  const state = {
    schema_version: 1, revision: 7, episode_id: 'episode-synthetic-e2e', scenario: 'SC-003', world_tick: 18,
    graph_version: 4, policy_epoch: 2, coordinator_epoch: 3, dispatch_sequence: 9, dispatch_ready: false,
    hold_reason: 'SOURCE_SCOPE_UNKNOWN', model_mode: 'disabled', sensor_mode: 'S0',
    robots: [
      { id: 'scout-test', role: 'scout', pose: { x: -4, y: -.35, yaw: 0 }, state: 'idle', footprint_m: .22, last_observation_tick: 18 },
      { id: 'recovery-test', role: 'recovery', pose: { x: 0, y: -.5, yaw: 1.57 }, state: 'idle', footprint_m: .38, last_observation_tick: 18 },
      { id: 'courier-test', role: 'courier', pose: { x: -6, y: 0, yaw: 0 }, state: 'held', footprint_m: .5, last_observation_tick: 18 },
    ],
    tasks: [{ id: 'task-deliver-test', kind: 'deliver', state: 'BLOCKED', robot_id: 'courier-test', depends_on: ['task-recovery-test'], reason_codes: ['SOURCE_SCOPE_UNKNOWN'], last_command_id: 'command-test' }],
    commands: [{ command_id: 'command-test', robot_id: 'courier-test', kind: 'deliver', state: 'CONTROLLER_DONE', last_known_state: 'done', reconciliation_state: 'awaiting_observation', world_tick: 18, reason_codes: [] }],
    observations: [], restrictions: [],
    sources: [{ source_id: 'source-test', revision_id: 'revision-test', owner: 'Maintenance', restriction: 'Courier corridor scope unresolved', text: 'Loaded couriers remain restricted until release.', normalized_hash: 'sha256:test-only', normalizer_version: 'synthetic-test-v1' }],
    events: [{ event_id: 'event-test', type: 'COMMAND_RECORDED', world_tick: 18, decision_id: 'decision-test' }],
    approval_required: false, release_id: null, metrics: {},
  };
  await page.route('**/api/health', (route) => route.fulfill({ json: { process: 'healthy', dispatch_ready: false } }));
  await page.route('**/api/state', (route) => route.fulfill({ json: state }));
  await page.route('**/api/events**', (route) => route.fulfill({ status: 200, contentType: 'text/event-stream', body: `id: 7\nevent: snapshot\ndata: ${JSON.stringify(state)}\n\n` }));

  await page.goto('/');
  await expect(page.getByText('episode-synthetic-e2e')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Robot pose projection' })).toBeVisible();
  await expect(page.getByLabel('Robots').getByRole('listitem')).toHaveCount(3);
  await expect(page.getByText('task-recovery-test')).toBeVisible();
  await expect(page.getByRole('table').getByText('SOURCE_SCOPE_UNKNOWN')).toBeVisible();
  await expect(page.getByRole('button', { name: /Open witness for decision-test/i })).toBeVisible();
  await expect(page.getByText('CONTROLLER DONE', { exact: false }).first()).toBeVisible();
  await expect(page.getByText('Not present in command projection')).toBeVisible();
  await expect(page.getByText('Loaded couriers remain restricted until release.')).toBeVisible();
  await expect(page.getByRole('button', { name: /Open witness for revision-test/i })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Open witness for decision-test/i })).toBeVisible();
  await assertNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('synthetic-connected-projection.png'), fullPage: true });
});

test('main reason and evidence metadata meet readable minimums at 320px', async ({ page }, testInfo) => {
  const state = {
    schema_version: 1, revision: 7, episode_id: 'episode-synthetic-mobile', scenario: 'SC-003', world_tick: 18,
    graph_version: 4, policy_epoch: 2, coordinator_epoch: 3, dispatch_sequence: 9, dispatch_ready: false,
    hold_reason: 'RUNTIME_INTEGRATION_INCOMPLETE', model_mode: 'disabled', sensor_mode: 'S0',
    robots: [], tasks: [], commands: [], observations: [], restrictions: [],
    sources: [{ source_id: 'source-mobile', revision_id: 'revision-mobile', text: 'Retained test-only text.', normalized_hash: 'sha256:test', normalizer_version: 'test-v1' }],
    events: [], approval_required: false, release_id: null, metrics: {},
  };
  await page.setViewportSize({ width: 320, height: 700 });
  await page.route('**/api/health', (route) => route.fulfill({ json: { process: 'healthy', dispatch_ready: false } }));
  await page.route('**/api/state', (route) => route.fulfill({ json: state }));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Why is motion gated?' })).toBeVisible();
  const sizes = await page.evaluate(() => Object.fromEntries(
    ['.reason-lead', '.gate-status', '.decision-metadata dt', '.decision-metadata dd', '.section-meta', '.source-meta', '.status-tag', '.state-badge', 'th', 'td', '.overview-stat small']
      .map((selector) => [selector, [...document.querySelectorAll(selector)].map((element) => parseFloat(getComputedStyle(element).fontSize))]),
  ));
  expect(sizes['.reason-lead']?.every((size) => size >= 16)).toBe(true);
  expect(Object.entries(sizes).filter(([selector]) => selector !== '.reason-lead').every(([, values]) => values.length === 0 || values.every((size) => size >= 13))).toBe(true);
  await assertNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('connected-readable-320.png'), fullPage: true });
});
