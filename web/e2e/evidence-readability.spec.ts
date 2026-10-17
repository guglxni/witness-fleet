import { expect, test } from '@playwright/test';

// Synthetic test-only contract data. Never used by the application as fallback state.
const sourceId = 'source-synthetic-long-retained-maintenance-policy';
const revisionId = `${sourceId}:${'a'.repeat(64)}`;
const decisionId = 'restriction-synthetic-long-loaded-courier-corridor';
const state = {
  schema_version: 1, revision: 7, episode_id: 'episode-synthetic-readability', scenario: 'SC-003', world_tick: 18,
  graph_version: 4, policy_epoch: 2, coordinator_epoch: 3, dispatch_sequence: 0, dispatch_ready: false,
  hold_reason: 'RUNTIME_INTEGRATION_INCOMPLETE', model_mode: 'disabled', sensor_mode: 'S0',
  robots: [], tasks: [{ id: 'task-synthetic-courier-delivery', kind: 'deliver', state: 'BLOCKED', robot_id: 'courier-test', depends_on: ['task-synthetic-clearance'], reason_codes: [], last_command_id: null }],
  commands: [], observations: [], restrictions: [{ id: decisionId }],
  sources: [{ source_id: sourceId, revision_id: revisionId, normalized_hash: 'a'.repeat(64), normalizer_version: 'synthetic-test-v1' }],
  events: [], approval_required: false, release_id: null, metrics: {},
};
const witness = {
  decision_id: decisionId, status: 'active', completeness: 'complete', reason_codes: [],
  nodes: [
    { id: decisionId, type: 'Restriction', label: decisionId },
    { id: sourceId, type: 'Source', label: sourceId },
    { id: revisionId, type: 'Revision', label: revisionId },
  ],
  edges: [{ source_id: revisionId, target_id: sourceId, relationship: 'REVISION_OF' }],
  spans: [{ revision_id: revisionId, start: 0, end: 41, quote: 'Synthetic retained policy for layout tests.' }],
};

for (const width of [320, 1440]) {
  test(`retained evidence leaf text remains readable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route('**/api/health', route => route.fulfill({ json: { process: 'healthy', dispatch_ready: false } }));
    await page.route('**/api/state', route => route.fulfill({ json: state }));
    await page.route('**/api/events**', route => route.fulfill({ contentType: 'text/event-stream', body: `event: snapshot\ndata: ${JSON.stringify(state)}\n\n` }));
    await page.route('**/api/sources/**', route => route.fulfill({ json: { revision_id: revisionId, text: 'Synthetic retained source text for layout testing.' } }));
    await page.route('**/api/decisions/**/witness', route => route.fulfill({ json: witness }));
    await page.goto('/');
    await page.getByRole('button', { name: `Load retained source ${revisionId}` }).click();
    await expect(page.locator('.source-card blockquote')).toBeVisible();
    await page.getByRole('button', { name: `Open witness for ${decisionId}` }).click();
    await expect(page.locator('.witness-card')).toBeVisible();
    const typography = await page.evaluate(() => {
      const selectors = ['.reason-lead', '.gate-status', '.status-tag', '.state-badge', 'th', 'td', 'td strong', 'td small', '.source-card-head strong', '.source-fingerprint dd', '.source-card blockquote', '.mono', '.witness-links p', '.witness-title', '.retained-quote small'];
      return Object.fromEntries(selectors.map(selector => [selector, [...document.querySelectorAll(selector)].map(element => parseFloat(getComputedStyle(element).fontSize))]));
    });
    for (const [selector, sizes] of Object.entries(typography)) {
      expect(sizes.length, `${selector} must be exercised`).toBeGreaterThan(0);
      for (const size of sizes) expect(size, selector).toBeGreaterThanOrEqual(selector === '.reason-lead' ? 16 : 13);
    }
    const graphSizes = await page.locator('.witness-graph text').evaluateAll(elements => elements.map(element => {
      const svg = element as SVGGraphicsElement;
      return parseFloat(getComputedStyle(svg).fontSize) * (svg.getScreenCTM()?.a ?? 0);
    }));
    expect(graphSizes.length).toBeGreaterThan(0);
    for (const size of graphSizes) expect(size, 'rendered graph label size').toBeGreaterThanOrEqual(13);
    await expect(page.getByRole('region', { name: 'Scrollable witness graph' })).toHaveAttribute('tabindex', '0');
    const dimensions = await page.evaluate(() => ({ document: document.documentElement.scrollWidth, viewport: document.documentElement.clientWidth }));
    expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
  });
}
