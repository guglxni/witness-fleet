import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from '../src/App';
import type { FleetProjection } from '../api-contract';

// Explicitly synthetic transport interleavings; no live backend or mutation.
const snapshot = (episode_id: string, revision = 1): FleetProjection => ({
  schema_version: 1, revision, episode_id, scenario: 'SC-001', world_tick: revision,
  graph_version: 1, policy_epoch: 1, coordinator_epoch: 1, dispatch_sequence: 0,
  dispatch_ready: false, hold_reason: 'Inspection only', model_mode: 'disabled', sensor_mode: 'S0',
  robots: [], tasks: [], commands: [], observations: [], restrictions: [], sources: [], events: [],
  approval_required: false, release_id: null, metrics: {},
});
const missionSnapshot = (episode_id: string, phase: FleetProjection['mission_phase'] = 'recovery_and_verification', overrides: Partial<FleetProjection> = {}): FleetProjection => ({
  ...snapshot(episode_id),
  operator_mode: 'local_mission', mission_phase: phase,
  local_owner_id: 'synthetic-owner-demo', hold_reason: null,
  tasks: Array.from({ length: 7 }, (_, index) => ({
    id: `task-${index + 1}`, kind: index === 6 ? 'deliver' : 'recover', state: phase === 'awaiting_owner_release' && index < 4 ? 'VERIFIED' : 'PENDING',
    robot_id: null, depends_on: [], reason_codes: [], last_command_id: null,
  })),
  ...overrides,
});
const response = (value: unknown) => new Response(JSON.stringify(value), { status: 200 });
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

class TestStream {
  static all: TestStream[] = [];
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  closed = false;
  listeners = new Map<string, EventListener>();
  constructor(readonly url: string) { TestStream.all.push(this); }
  addEventListener(name: string, listener: EventListener) { this.listeners.set(name, listener); }
  close() { this.closed = true; }
  // Deliberately invokes even after close: queued callbacks must be fenced by the app.
  emit(value: FleetProjection) {
    this.listeners.get('snapshot')?.(new MessageEvent('snapshot', { data: JSON.stringify(value) }));
  }
}
const stream = () => TestStream.all.filter((item) => item.url === '/api/events').at(-1)!;
const refresh = () => fireEvent.click(screen.getByRole('button', { name: /Refresh API state/i }));
const create = () => fireEvent.click(screen.getByRole('button', { name: /Create incident/i }));
const visible = (episode: string) => expect(screen.getByText(episode, { exact: true })).toBeInTheDocument();

beforeEach(() => { TestStream.all = []; vi.stubGlobal('EventSource', TestStream); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

async function mount(initial: FleetProjection = snapshot('episode-A')) {
  const reads: ReturnType<typeof deferred<Response>>[] = [];
  const writes: ReturnType<typeof deferred<Response>>[] = [];
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url === '/api/health') return Promise.resolve(response({ process: 'healthy', dispatch_ready: false }));
    const pending = deferred<Response>();
    if (init?.method === 'POST') writes.push(pending); else reads.push(pending);
    return pending.promise;
  });
  vi.stubGlobal('fetch', fetchMock);
  render(<App />);
  await waitFor(() => expect(reads).toHaveLength(1));
  await act(async () => reads[0].resolve(response(initial)));
  await screen.findByText(initial.episode_id!, { exact: true });
  await waitFor(() => expect(stream()).toBeDefined());
  return { reads, writes, fetchMock };
}

describe('episode projection authority', () => {
  it('renders unverified task labels without verified styling or a check glyph', async () => {
    await mount({ ...snapshot('episode-A'), tasks: ['UNVERIFIED', 'NOT_VERIFIED', 'OUTCOME_VERIFIED'].map((state) => ({
      id: state, kind: 'inspect', state, robot_id: null, depends_on: [], reason_codes: [], last_command_id: null,
    })) });
    const tags = [...document.querySelectorAll('.status-tag')];
    expect(tags.filter((tag) => tag.classList.contains('tag-verified'))).toHaveLength(1);
    for (const label of ['unverified', 'not verified']) {
      const tag = tags.find((entry) => entry.textContent?.endsWith(label));
      expect(tag).toHaveClass('tag-unresolved');
      expect(tag).not.toHaveTextContent('✓');
    }
  });

  it('rehydrates a stream episode mismatch through fresh REST then the replacement stream', async () => {
    const { reads } = await mount();
    const old = stream();
    await act(async () => old.emit(snapshot('episode-B')));
    refresh();
    await waitFor(() => expect(reads).toHaveLength(2));
    await act(async () => reads[1].resolve(response(snapshot('episode-B'))));
    visible('episode-B');
    expect(screen.getByRole('button', { name: /Create incident/i })).toBeDisabled();
    await act(async () => stream().emit(snapshot('episode-B')));
    expect(screen.getByRole('button', { name: /Create incident/i })).toBeEnabled();
    await act(async () => old.emit(snapshot('episode-A', 99)));
    visible('episode-B');
    expect(screen.getByRole('button', { name: /Create incident/i })).toBeEnabled();
  });

  it('ignores an old refresh failure after a new episode has been established', async () => {
    const { reads } = await mount();
    refresh();
    await waitFor(() => expect(reads).toHaveLength(2));
    refresh();
    await waitFor(() => expect(reads).toHaveLength(3));
    await act(async () => reads[2].resolve(response(snapshot('episode-B'))));
    await act(async () => reads[1].reject(new Error('old failure')));
    visible('episode-B');
    expect(screen.queryByText('old failure')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Create incident/i })).toBeEnabled();
  });

  it('keeps the latest same-episode SSE revision when a delayed REST read completes', async () => {
    const { reads } = await mount();
    refresh();
    await waitFor(() => expect(reads).toHaveLength(2));
    await act(async () => stream().emit(snapshot('episode-A', 10)));
    await act(async () => reads[1].resolve(response(snapshot('episode-A', 2))));
    expect(screen.getByText('Revision 10 observed')).toBeInTheDocument();
  });

  it('locks stale controls on an active stream episode mismatch without silently switching episode', async () => {
    await mount();
    await act(async () => stream().emit(snapshot('episode-A', 2)));
    await act(async () => stream().emit(snapshot('episode-B')));
    visible('episode-A');
    expect(screen.getByRole('button', { name: /Create incident/i })).toBeDisabled();
    expect(document.querySelector('.connection')).toHaveTextContent('STALE');
  });

  it('does not reuse unknown-outcome control IDs in a different episode', async () => {
    const { reads, writes, fetchMock } = await mount(missionSnapshot('episode-A', 'recovery_and_verification', { revision: 1 }));
    fireEvent.click(screen.getByRole('button', { name: /^Hold$/i }));
    await act(async () => writes[0].reject(new Error('unknown outcome')));
    refresh();
    await waitFor(() => expect(reads).toHaveLength(2));
    await act(async () => reads[1].resolve(response(missionSnapshot('episode-B', 'recovery_and_verification', { revision: 1 }))));
    expect(screen.queryByText(/unknown outcome/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^Hold$/i }));
    const calls = fetchMock.mock.calls.filter(([url]) => url === '/api/hold');
    expect(calls).toHaveLength(2);
    expect(JSON.parse(calls[0][1]!.body as string).event_id).not.toBe(JSON.parse(calls[1][1]!.body as string).event_id);
    await act(async () => writes[1].resolve(response(missionSnapshot('episode-B', 'recovery_and_verification', { revision: 2 }))));
  });

  it('remounts retained source cards when episode changes even if revision IDs repeat', async () => {
    const sources = [{ source_id: 'source-shared', revision_id: 'revision-shared' }];
    const { reads } = await mount({ ...snapshot('episode-A'), sources });
    fireEvent.click(screen.getByRole('button', { name: /Load retained source/i }));
    await act(async () => reads[1].resolve(response({ text: 'Episode A retained quotation' })));
    expect(screen.getByText(/Episode A retained quotation/)).toBeInTheDocument();
    refresh();
    await waitFor(() => expect(reads).toHaveLength(3));
    await act(async () => reads[2].resolve(response({ ...snapshot('episode-B'), sources })));
    expect(screen.queryByText(/Episode A retained quotation/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Load retained source/i })).toBeInTheDocument();
  });

  it('does not restore freshness from an older REST revision after the stream failed', async () => {
    const { reads } = await mount(snapshot('episode-A', 9));
    await act(async () => stream().onerror?.());
    await waitFor(() => expect(reads).toHaveLength(2));
    await act(async () => reads[1].resolve(response(snapshot('episode-A', 8))));
    expect(screen.getByRole('button', { name: /Create incident/i })).toBeDisabled();
  });

  it('does not restore freshness from an older REST revision after an offline refresh', async () => {
    const { reads } = await mount(snapshot('episode-A', 9));
    refresh();
    await waitFor(() => expect(reads).toHaveLength(2));
    await act(async () => reads[1].reject(new Error('offline')));
    refresh();
    await waitFor(() => expect(reads).toHaveLength(3));
    await act(async () => reads[2].resolve(response(snapshot('episode-A', 8))));
    expect(screen.getByRole('button', { name: /Create incident/i })).toBeDisabled();
  });

  it.each(['already-loaded', 'late-response'] as const)('does not carry %s witness evidence across an episode switch', async (timing) => {
    const initial = { ...snapshot('episode-A'), restrictions: [{ id: 'decision-A' }] };
    const { reads } = await mount(initial);
    fireEvent.click(screen.getByRole('button', { name: /Open witness for decision-A/i }));
    const witness = { decision_id: 'decision-A', status: 'UNRESOLVED', reason_codes: [], completeness: 'PARTIAL', nodes: [], edges: [], spans: [] };
    if (timing === 'already-loaded') {
      await act(async () => reads[1].resolve(response(witness)));
      expect(document.querySelector('.witness-card')).not.toBeNull();
    }
    refresh();
    await waitFor(() => expect(reads).toHaveLength(3));
    await act(async () => reads[2].resolve(response(snapshot('episode-B'))));
    if (timing === 'late-response') await act(async () => reads[1].resolve(response(witness)));
    visible('episode-B');
    expect(document.querySelector('.witness-card')).toBeNull();
    expect(screen.queryByText(/Loading backend witness/i)).not.toBeInTheDocument();
  });

  it('resets approval confirmation when episode changes even if release and policy IDs repeat', async () => {
    const { reads } = await mount(missionSnapshot('episode-A', 'awaiting_owner_release', { approval_required: true, release_id: 'release-shared' }));
    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);
    const oldPayload = screen.getByLabelText('Approval request payload').textContent;
    refresh();
    await waitFor(() => expect(reads).toHaveLength(2));
    const next = missionSnapshot('episode-B', 'awaiting_owner_release', { approval_required: true, release_id: 'release-shared' });
    await act(async () => reads[1].resolve(response(next)));
    visible('episode-B');
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(screen.getByLabelText('Approval request payload').textContent).not.toBe(oldPayload);
  });

  it('bootstraps through REST, not a competing one-shot replay stream', async () => {
    const pending = deferred<Response>();
    vi.stubGlobal('fetch', vi.fn((url: string) => url === '/api/health'
      ? Promise.resolve(response({ process: 'healthy', dispatch_ready: false })) : pending.promise));
    render(<App />);
    await act(async () => TestStream.all.find((item) => item.url.includes('once=true'))?.emit(snapshot('episode-old', 99)));
    await act(async () => pending.resolve(response(snapshot('episode-current'))));
    visible('episode-current');
    expect(TestStream.all.some((item) => item.url.includes('once=true'))).toBe(false);
  });

  it.each(['open', 'error', 'snapshot'] as const)('ignores queued %s callbacks from the previous episode stream', async (callback) => {
    const { writes, fetchMock } = await mount();
    const previous = stream();
    create();
    await act(async () => writes[0].resolve(response(snapshot('episode-B'))));
    const active = stream();
    await act(async () => active.emit(snapshot('episode-B', 2)));
    const calls = fetchMock.mock.calls.length;
    await act(async () => {
      if (callback === 'open') previous.onopen?.();
      if (callback === 'error') previous.onerror?.();
      if (callback === 'snapshot') previous.emit(snapshot('episode-A', 99));
    });
    visible('episode-B');
    expect(document.querySelector('.connection')).toHaveTextContent('Live stream');
    expect(fetchMock).toHaveBeenCalledTimes(calls);
  });

  it.each(['wrong-episode', 'older-revision'] as const)('does not unlock a stale stream on a %s snapshot', async (kind) => {
    await mount(snapshot('episode-A', 9));
    const active = stream();
    await act(async () => active.onerror?.());
    await act(async () => active.emit(kind === 'wrong-episode' ? snapshot('episode-old', 99) : snapshot('episode-A', 8)));
    visible('episode-A');
    expect(screen.getByRole('button', { name: /Create incident/i })).toBeDisabled();
    expect(document.querySelector('.connection')).toHaveTextContent('STALE');
    await act(async () => active.emit(snapshot('episode-A', 9)));
    if (kind === 'wrong-episode') {
      // Contradictory episode evidence requires REST rehydration, not more SSE.
      expect(screen.getByRole('button', { name: /Create incident/i })).toBeDisabled();
    } else {
      expect(screen.getByRole('button', { name: /Create incident/i })).toBeEnabled();
    }
  });

  it('ignores a late incident response after a newer refresh established another episode', async () => {
    const { reads, writes } = await mount();
    create();
    refresh();
    await waitFor(() => expect(reads).toHaveLength(2));
    await act(async () => reads[1].resolve(response(snapshot('episode-C'))));
    await act(async () => writes[0].resolve(response(snapshot('episode-B'))));
    visible('episode-C');
    expect(screen.queryByText(/Incident creation response received/i)).not.toBeInTheDocument();
  });

  it('uses the newest refresh to switch episode and ignores an older REST response', async () => {
    const { reads } = await mount();
    refresh();
    await waitFor(() => expect(reads).toHaveLength(2));
    refresh();
    await waitFor(() => expect(reads).toHaveLength(3));
    await act(async () => reads[2].resolve(response(snapshot('episode-B'))));
    visible('episode-B');
    await act(async () => reads[1].resolve(response(snapshot('episode-A', 99))));
    visible('episode-B');
  });

  it('allows a current incident creation response to establish a new episode with a reset revision', async () => {
    const { writes } = await mount(snapshot('episode-A', 9));
    create();
    await act(async () => writes[0].resolve(response(snapshot('episode-B', 1))));
    visible('episode-B');
  });
});
