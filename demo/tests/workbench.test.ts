import { describe, expect, it, vi } from 'vitest';
import { HostedWorkbench } from '../src/workbench';
import { activeState, sceneFixture } from './fixtures';

function response(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { 'content-type': 'application/json' } });
}

describe('HostedWorkbench safety and sampled evidence', () => {
  it('serializes activation and never sends a duplicate action while the first response is pending', async () => {
    let resolveRun!: (value: Response) => void;
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/run')) return await new Promise<Response>((resolve) => { resolveRun = resolve; });
      if (url.endsWith('/scene')) return response(sceneFixture);
      if (url.endsWith('/sessions')) return response({ session: { status: 'active' }, state: activeState });
      return response({});
    });
    const wb = new HostedWorkbench(fetcher as typeof fetch);
    wb.hydrate('csrf-in-memory-only', activeState);
    const first = wb.runMission();
    expect(wb.snapshot.busy).toBe(true);
    await expect(wb.stepOnce()).resolves.toBe(false);
    expect(fetcher.mock.calls.filter(([url]) => String(url).endsWith('/step'))).toHaveLength(0);
    resolveRun(response({ ...activeState, revision_tick: 13, mission_phase: 'complete' }));
    await expect(first).resolves.toBe(true);
    expect(fetcher.mock.calls.filter(([url]) => String(url).endsWith('/run'))).toHaveLength(1);
  });

  it('latches motion off after a lost mutation response and never retries or creates a replacement session', async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith('/run')) throw new TypeError('network lost');
      if (String(input).endsWith('/scene')) return response(sceneFixture);
      return response({});
    });
    const wb = new HostedWorkbench(fetcher as typeof fetch);
    wb.hydrate('csrf-in-memory-only', activeState);
    await expect(wb.runMission()).resolves.toBe(false);
    expect(wb.snapshot.outcomeUnknown).toBe(true);
    expect(wb.snapshot.notice).toContain('outcome_unknown_no_retry');
    expect(await wb.runMission()).toBe(false);
    expect(await wb.stepOnce()).toBe(false);
    expect(await wb.createSession()).toBe(false);
    expect(fetcher.mock.calls.filter(([url]) => String(url).includes('/demo/v1/'))).toHaveLength(1);
  });

  it('latches motion off when a mutation claims success but its body is malformed', async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => String(input).endsWith('/run')
      ? new Response('{"mission_phase":', { status: 200 }) : response(sceneFixture));
    const wb = new HostedWorkbench(fetcher as typeof fetch);
    wb.hydrate('csrf-in-memory-only', activeState);
    await expect(wb.runMission()).resolves.toBe(false);
    expect(wb.snapshot.outcomeUnknown).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('requires a fresh explicit release confirmation for the exact awaiting epoch', async () => {
    let current = { ...activeState, mission_phase: 'awaiting_owner_release', expected_policy_epoch: 7 };
    const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/confirm-release')) {
        const body = JSON.parse(String(init?.body));
        expect(body.confirmed).toBe(true);
        expect(body.expected_policy_epoch).toBe(7);
        current = { ...current, mission_phase: 'courier_delivery', expected_policy_epoch: 8 };
        return response(current);
      }
      if (url.endsWith('/scene')) return response(sceneFixture);
      return response(current);
    });
    const wb = new HostedWorkbench(fetcher as typeof fetch);
    wb.hydrate('csrf-in-memory-only', current);
    expect(await wb.confirmRelease(false)).toBe(false);
    expect(fetcher).not.toHaveBeenCalled();
    wb.armRelease(true);
    expect(wb.snapshot.releaseArmedEpoch).toBe(7);
    expect(await wb.confirmRelease(true)).toBe(true);
    expect(wb.snapshot.releaseArmedEpoch).toBeNull();
  });

  it('keeps the safety latch across sampled-history selection and labels revision/world tick separately', async () => {
    const fetcher = vi.fn(async () => { throw new TypeError('network lost'); });
    const wb = new HostedWorkbench(fetcher as typeof fetch);
    wb.hydrate('csrf-in-memory-only', activeState);
    wb.setScene(sceneFixture);
    wb.recordSample();
    wb.selectSample(2);
    expect(wb.snapshot.displayedState?.revision_tick).toBe(12);
    expect(wb.snapshot.displayedScene?.world_tick).toBe(84);
    wb.selectSample(null);
    await wb.runMission();
    wb.selectSample(2);
    expect(wb.snapshot.outcomeUnknown).toBe(true);
    expect(wb.snapshot.canMutate).toBe(false);
    expect(wb.snapshot.displayedState?.revision_tick).toBe(12);
    expect(wb.snapshot.live).toBe(false);
  });
});
