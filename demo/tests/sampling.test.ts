import { describe, expect, it, vi } from 'vitest';
import { HostedWorkbench } from '../src/workbench';
import { activeState, sceneFixture } from './fixtures';

const jsonResponse = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });

describe('separately sampled scene and safety recovery edges', () => {
  it('records the post-action state with the separately fetched post-action scene sample', async () => {
    const nextScene = structuredClone(sceneFixture); nextScene.world_tick = 85;
    const fetcher = vi.fn(async (input: RequestInfo | URL) => String(input).endsWith('/run')
      ? jsonResponse({ ...activeState, revision_tick: 13 })
      : String(input).endsWith('/scene') ? jsonResponse(nextScene) : jsonResponse({}));
    const wb = new HostedWorkbench(fetcher as typeof fetch); wb.hydrate('csrf', activeState); wb.setScene(sceneFixture);
    await expect(wb.runMission()).resolves.toBe(true);
    expect(wb.snapshot.samples.at(-1)?.state.revision_tick).toBe(13);
    expect(wb.snapshot.samples.at(-1)?.scene?.world_tick).toBe(85);
    expect(fetcher.mock.calls.map(([url]) => String(url))).toEqual(['/demo/v1/run', '/demo/v1/scene']);
  });

  it('never displays a live scene as a replacement for a historical sample whose scene was unavailable', () => {
    const wb = new HostedWorkbench(vi.fn() as typeof fetch); wb.hydrate('csrf', activeState);
    wb.setScene(sceneFixture); wb.recordSample(); wb.selectSample(1);
    expect(wb.snapshot.displayedScene).toBeNull();
    expect(wb.snapshot.live).toBe(false);
  });

  it('fails closed for arbitrary transport exceptions without relying on error-message wording', async () => {
    const fetcher = vi.fn(async () => { throw new Error('offline'); });
    const wb = new HostedWorkbench(fetcher as typeof fetch); wb.hydrate('csrf', activeState);
    await expect(wb.runMission()).resolves.toBe(false);
    expect(wb.snapshot.canMutate).toBe(false);
    expect(wb.snapshot.notice).toContain('outcome_unknown_no_retry');
  });

  it('keeps a definite controller rejection distinct from an uncertain mutation outcome', async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => String(input).endsWith('/run')
      ? jsonResponse({ detail: 'simulation_action_rejected' }, 409) : jsonResponse(sceneFixture));
    const wb = new HostedWorkbench(fetcher as typeof fetch); wb.hydrate('csrf', activeState);
    await expect(wb.runMission()).resolves.toBe(false);
    expect(wb.snapshot.outcomeUnknown).toBe(false);
    expect(wb.snapshot.notice).toContain('simulation_action_rejected');
  });
});
