import { describe, expect, it, vi } from 'vitest';
import { HostedWorkbench } from '../src/workbench';
import { activeState, sceneFixture } from './fixtures';

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

describe('independent reviewer regressions', () => {
  it.each([400, 404, 409, 429])('locks motion after ambiguous HTTP %i mutation response', async (status) => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => String(input).endsWith('/run')
      ? response({ detail: 'undocumented_or_ambiguous' }, status) : response(sceneFixture));
    const wb = new HostedWorkbench(fetcher as typeof fetch);
    wb.hydrate('csrf', activeState);
    await expect(wb.runMission()).resolves.toBe(false);
    expect(wb.snapshot.outcomeUnknown).toBe(true);
    expect(wb.snapshot.canMutate).toBe(false);
    expect(await wb.stepOnce()).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('locks on nested malformed DTO data in a successful mutation receipt', async () => {
    const malformed = { ...activeState, tasks: [{ ...activeState.tasks[0], state: 17 }] };
    const fetcher = vi.fn(async (input: RequestInfo | URL) => String(input).endsWith('/run')
      ? response(malformed) : response(sceneFixture));
    const wb = new HostedWorkbench(fetcher as typeof fetch);
    wb.hydrate('csrf', activeState);
    await expect(wb.runMission()).resolves.toBe(false);
    expect(wb.snapshot.outcomeUnknown).toBe(true);
    expect(wb.snapshot.canMutate).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('records reattach, create, and refresh samples only after their separate scene fetch attempt', async () => {
    let sceneTick = 84;
    let stateTick = 12;
    const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/bootstrap')) return response({ csrf_token: 'csrf' });
      if (url.endsWith('/sessions') && init?.method === 'POST') return response({ csrf_token: 'csrf', state: { ...activeState, revision_tick: stateTick } });
      if (url.endsWith('/sessions')) return response({ session: { status: 'active' }, state: { ...activeState, revision_tick: stateTick } });
      if (url.endsWith('/scene')) return response({ ...sceneFixture, world_tick: sceneTick });
      return response({});
    });
    const reattached = new HostedWorkbench(fetcher as typeof fetch);
    await expect(reattached.reattach()).resolves.toBe(true);
    expect(reattached.snapshot.samples.at(-1)).toMatchObject({ state: { revision_tick: 12 }, scene: { world_tick: 84 } });

    const created = new HostedWorkbench(fetcher as typeof fetch);
    await expect(created.createSession()).resolves.toBe(true);
    expect(created.snapshot.samples.at(-1)).toMatchObject({ state: { revision_tick: 12 }, scene: { world_tick: 84 } });

    stateTick = 13;
    sceneTick = 85;
    await expect(reattached.refresh()).resolves.toBe(true);
    expect(reattached.snapshot.samples.at(-1)).toMatchObject({ state: { revision_tick: 13 }, scene: { world_tick: 85 } });
  });

  it('shows an unavailable historical state when its selected sample has been evicted', () => {
    const wb = new HostedWorkbench(vi.fn() as typeof fetch);
    wb.hydrate('csrf', activeState);
    wb.selectSample(1);
    for (let i = 0; i < 40; i++) wb.recordSample();
    expect(wb.snapshot.samples).toHaveLength(40);
    expect(wb.snapshot.samples.some((sample) => sample.sampleNumber === 1)).toBe(false);
    expect(wb.snapshot.selectedSample).toBe(1);
    expect(wb.snapshot.displayedState).toBeNull();
    expect(wb.snapshot.live).toBe(false);
  });
});
