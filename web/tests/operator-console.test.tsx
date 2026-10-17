import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from '../src/App';
import type { FleetProjection } from '../api-contract';

// Explicitly synthetic API projection fixture; never used to seed a live UI state.
const liveState: FleetProjection = {
  schema_version: 1, revision: 7, episode_id: 'episode-synthetic-7', scenario: 'SC-003', world_tick: 18,
  graph_version: 4, policy_epoch: 2, coordinator_epoch: 1, dispatch_sequence: 0, dispatch_ready: false,
  hold_reason: 'Evidence incomplete', model_mode: 'disabled', sensor_mode: 'S0',
  robots: [{ id: 'courier-1', role: 'courier', pose: { x: 2.4, y: 1.1, yaw: 0 }, state: 'idle', footprint_m: 0.6, last_observation_tick: 18 }],
  tasks: [], commands: [], observations: [], restrictions: [], sources: [], events: [],
  approval_required: false, release_id: null, metrics: {},
};

function awaitingOwnerState(overrides: Partial<FleetProjection> = {}): FleetProjection {
  const tasks = Array.from({ length: 7 }, (_, index) => ({
    id: `task-${index + 1}`, kind: index === 6 ? 'deliver' : 'recover', state: index < 4 ? 'VERIFIED' : 'PENDING',
    robot_id: null, depends_on: [], reason_codes: [], last_command_id: null,
  }));
  return {
    ...liveState, tasks, operator_mode: 'local_mission', mission_phase: 'awaiting_owner_release', local_owner_id: 'synthetic-owner-demo', approval_required: true, release_id: 'release-demo', hold_reason: null, ...overrides,
  };
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

function approvalPayload(): { expected_policy_epoch: number; event_id: string } {
  return JSON.parse(screen.getByLabelText('Approval request payload').textContent ?? '{}');
}

describe('operator console live-state boundary', () => {
  it('frames the core decision as a principle rather than a live physical claim', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 })));
    render(<App />);

    expect(await screen.findByRole('heading', { name: /Physically clear\. Loaded courier still restricted\./i })).toBeInTheDocument();
    expect(screen.getByText(/NOT A LIVE EPISODE CLAIM/i)).toBeInTheDocument();
    expect(screen.getByText(/No clearance is inferred from a robot pose or an empty observation list/i)).toBeInTheDocument();
  });

  it('keeps physical clearance unknown when a projection has poses but no S0 observation records', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(liveState), { status: 200 })));
    render(<App />);

    expect(await screen.findByText(/Unknown · no S0 clearance evidence/i)).toBeInTheDocument();
    expect(screen.getAllByText('Evidence incomplete').length).toBeGreaterThan(0);
    expect(screen.getByText('Graph version')).toBeInTheDocument();
    expect(screen.getAllByText('UNKNOWN · retained source records are not claim verdicts').length).toBeGreaterThan(0);
    expect(screen.getByText('Policy')).toBeInTheDocument();
    expect(screen.getByText('UNKNOWN · policy permission is not exposed by this contract')).toBeInTheDocument();
    expect(screen.getByText('Coordinator epoch')).toBeInTheDocument();
    expect(screen.getByText('Dispatch sequence')).toBeInTheDocument();
  });

  it('reports a healthy API but never invents robots when incident state is absent', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 }));
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    expect(await screen.findByText(/Waiting for incident\/backend state/i)).toBeInTheDocument();
    expect(screen.getByText('Unavailable', { selector: '.overview-stat small' })).toBeInTheDocument();
    expect(screen.getAllByText(/API reachable/i).length).toBeGreaterThan(0);
    expect(screen.queryByRole('list', { name: /robots/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/courier-1/i)).not.toBeInTheDocument();
  });

  it('labels a retained projection as cached and stale after an offline refresh', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(liveState), { status: 200 }))
      .mockRejectedValueOnce(new Error('connection refused'));
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);

    expect(await screen.findByText('episode-synthetic-7')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Refresh API state/i }));

    expect(await screen.findByText(/Cached revision 7 · world tick 18/i)).toBeInTheDocument();
    expect(screen.getByText(/Cached revision 7 · world tick 18/).closest('.stale-banner')).toHaveTextContent(/cached state is stale/i);
    expect(screen.getByRole('button', { name: /Create incident/i })).toBeDisabled();
    expect(screen.getByText(/Cached revision 7 · world tick 18/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Why is motion gated/i })).toBeInTheDocument();
  });

  it('keeps mutation controls locked when the operator API is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('connection refused')));
    render(<App />);

    expect(await screen.findByRole('alert')).toHaveTextContent('connection refused');
    expect(screen.getByRole('button', { name: /Create incident/i })).toBeDisabled();
  });

  it('renders only backend-projected robot and tick values when state exists', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(liveState), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    expect((await screen.findAllByText('courier-1')).length).toBeGreaterThan(0);
    expect(screen.getByText('18')).toBeInTheDocument();
    expect(screen.queryByText(/Waiting for incident\/backend state/i)).not.toBeInTheDocument();
  });

  it('shows the approval request diff and requires an unchecked confirmation before POST', async () => {
    const restrictedState = awaitingOwnerState({ release_id: 'release-17', revision: 7 });
    const responseState = awaitingOwnerState({ release_id: 'release-17', revision: 8 });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(restrictedState), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(responseState), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);

    const approve = await screen.findByRole('button', { name: /Submit local demo-owner release request for release-17/i });
    const confirmation = screen.getByRole('checkbox', { name: /explicitly request the local demo-owner release/i });
    expect(confirmation).not.toBeChecked();
    expect(approve).toBeDisabled();
    const preview = approvalPayload();
    expect(preview).toMatchObject({ expected_policy_epoch: 2 });
    expect(preview.event_id).toMatch(/^[a-f0-9-]{36}$/i);
    fireEvent.click(confirmation);
    await waitFor(() => expect(approve).toBeEnabled());
    fireEvent.click(approve);

    const result = await screen.findByText(/Approval request response received/i, { selector: '.action-result' });
    expect(result).toHaveClass('result-response');
    expect(result).not.toHaveClass('result-accepted');
    expect(result.querySelector('svg')).toBeNull();
    const [url, init] = fetchMock.mock.calls[2] as [string, RequestInit];
    expect(url).toBe('/api/releases/release-17/approve');
    expect(JSON.parse(String(init.body))).toEqual(preview);
  });

  it('preserves a structured backend denial code in the local demo-owner request result', async () => {
    const restrictedState = awaitingOwnerState({ release_id: 'release-denied' });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(restrictedState), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: { code: 'NOT_AUTHORIZED' } }), { status: 403 }));
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);

    const approve = await screen.findByRole('button', { name: /Submit local demo-owner release request for release-denied/i });
    fireEvent.click(await screen.findByRole('checkbox', { name: /I explicitly request the local demo-owner release/i }));
    fireEvent.click(approve);
    expect(await screen.findByRole('status')).toHaveTextContent('NOT_AUTHORIZED');
    expect(screen.getByRole('status')).toHaveTextContent('HTTP 403');
  });

  it('resets approval confirmation and identity only when release or policy epoch changes', async () => {
    const state = (release_id: string, policy_epoch: number, revision: number) => ({
      ...awaitingOwnerState({ revision }), release_id, policy_epoch,
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(state('release-17', 2, 7)), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(state('release-17', 2, 8)), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(state('release-18', 2, 9)), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(state('release-18', 3, 10)), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('crypto', { randomUUID: vi.fn()
      .mockReturnValueOnce('00000000-0000-4000-8000-000000000001')
      .mockReturnValueOnce('00000000-0000-4000-8000-000000000002')
      .mockReturnValueOnce('00000000-0000-4000-8000-000000000003')
      .mockReturnValueOnce('00000000-0000-4000-8000-000000000004') });
    render(<App />);

    const confirmation = await screen.findByRole('checkbox', { name: /explicitly request the local demo-owner release/i });
    fireEvent.click(confirmation);
    expect(confirmation).toBeChecked();
    const initialId = approvalPayload().event_id;

    fireEvent.click(screen.getByRole('button', { name: /Refresh API state/i }));
    await waitFor(() => expect(screen.getByText('Revision 8 observed')).toBeInTheDocument());
    expect(confirmation).toBeChecked();
    expect(approvalPayload().event_id).toBe(initialId);

    fireEvent.click(screen.getByRole('button', { name: /Refresh API state/i }));
    await waitFor(() => expect(screen.getByRole('button', { name: /Submit local demo-owner release request for release-18/i })).toBeInTheDocument());
    await waitFor(() => expect(confirmation).not.toBeChecked());
    const releaseChangedId = approvalPayload().event_id;
    expect(releaseChangedId).not.toBe(initialId);

    fireEvent.click(confirmation);
    expect(confirmation).toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: /Refresh API state/i }));
    await waitFor(() => expect(screen.getByText('Policy epoch 3')).toBeInTheDocument());
    await waitFor(() => expect(confirmation).not.toBeChecked());
    expect(approvalPayload().event_id).not.toBe(releaseChangedId);
  });

  it('reuses the displayed approval payload after transport failure and rotates only after success', async () => {
    const restrictedState = awaitingOwnerState();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(restrictedState), { status: 200 }))
      .mockRejectedValueOnce(new Error('connection reset'))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...restrictedState, revision: 8 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...restrictedState, revision: 9 }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('crypto', { randomUUID: vi.fn()
      .mockReturnValueOnce('00000000-0000-4000-8000-000000000011')
      .mockReturnValueOnce('00000000-0000-4000-8000-000000000012')
      .mockReturnValueOnce('00000000-0000-4000-8000-000000000013') });
    render(<App />);

    const approve = await screen.findByRole('button', { name: /Submit local demo-owner release request for release-demo/i });
    const confirmation = screen.getByRole('checkbox', { name: /explicitly request the local demo-owner release/i });
    const firstPreview = approvalPayload();
    fireEvent.click(confirmation);
    fireEvent.click(approve);
    expect(await screen.findByText(/connection reset/i)).toBeInTheDocument();
    expect(approvalPayload()).toEqual(firstPreview);

    fireEvent.click(approve);
    expect(await screen.findByText(/Approval request response received; displaying backend revision 8/i, { selector: '.action-result' })).toBeInTheDocument();
    const firstRequest = JSON.parse(String((fetchMock.mock.calls[2]?.[1] as RequestInit).body));
    const retryRequest = JSON.parse(String((fetchMock.mock.calls[3]?.[1] as RequestInit).body));
    expect(firstRequest).toEqual(firstPreview);
    expect(retryRequest).toEqual(firstPreview);
    await waitFor(() => expect(confirmation).not.toBeChecked());
    const nextPreview = approvalPayload();
    expect(nextPreview.event_id).not.toBe(firstPreview.event_id);

    fireEvent.click(confirmation);
    fireEvent.click(approve);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
    const nextRequest = JSON.parse(String((fetchMock.mock.calls[4]?.[1] as RequestInit).body));
    expect(nextRequest).toEqual(nextPreview);
  });

  it('blocks step and run when the projection reports dispatch not ready but allows hold', async () => {
    const heldState = { ...liveState, revision: 8 };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(liveState), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(heldState), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);

    expect(await screen.findByText('episode-synthetic-7')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Step 1 tick/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /^Run$/i })).toBeDisabled();
    const hold = screen.getByRole('button', { name: /^Hold$/i });
    expect(hold).toBeDisabled();
  });

  it('exposes retained source identity and normalization metadata without inventing provenance', async () => {
    const sourceState = {
      ...liveState,
      sources: [{
        source_id: 'source-7', revision_id: 'revision-3', text: 'Pump bearing service interval is 500 hours.',
        normalized_hash: 'sha256:abc123', normalizer_version: 'maintenance-v2',
      }],
    };
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(sourceState), { status: 200 })));

    render(<App />);

    expect(await screen.findByText('sha256:abc123')).toBeInTheDocument();
    expect(screen.getByText('maintenance-v2')).toBeInTheDocument();
    expect(screen.getByText(/Pump bearing service interval is 500 hours\./)).toBeInTheDocument();
  });

  it('renders a keyboard-accessible graph witness and exact retained span from the API', async () => {
    const stateWithDecision = {
      ...liveState,
      sources: [{ source_id: 'source-7', revision_id: 'revision-3', text: 'Retained wording.', normalized_hash: 'sha256:def456', normalizer_version: 'v2' }],
      events: [{ decision_id: 'decision-9', type: 'DECISION_RECORDED', world_tick: 18 }],
    };
    const witness = {
      decision_id: 'decision-9', status: 'UNRESOLVED', reason_codes: ['SOURCE_SCOPE_UNKNOWN'], completeness: 'PARTIAL',
      nodes: [
        { id: 'n-source', type: 'SourceRevision', label: 'revision-3', properties: {} },
        { id: 'n-decision', type: 'Decision', label: 'decision-9', properties: {} },
      ],
      edges: [{ source_id: 'n-source', target_id: 'n-decision', relationship: 'SUPPORTS' }],
      spans: [{ revision_id: 'revision-3', start: 0, end: 16, quote: 'Retained wording.' }],
    };
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(stateWithDecision), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(witness), { status: 200 })));

    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /Open witness for decision-9/i }));

    const graph = await screen.findByRole('img', { name: /Graph witness for decision-9/i });
    expect(graph).toBeInTheDocument();
    expect(graph.querySelector('marker#witness-arrow')).toBeInTheDocument();
    expect(graph.querySelector('line[marker-end="url(#witness-arrow)"]')).toBeInTheDocument();
    expect(screen.getByRole('table', { name: /Witness nodes/i })).toBeInTheDocument();
    expect(screen.getAllByText('SUPPORTS').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Retained wording\./).length).toBeGreaterThan(0);
    expect(screen.getByText(/characters 0–16/i)).toBeInTheDocument();
  });

  it('keeps write actions locked after SSE interruption even when a REST refresh succeeds', async () => {
    class TestEventSource {
      static latest: TestEventSource | null = null;
      onopen: (() => void) | null = null;
      onerror: (() => void) | null = null;
      onmessage: ((event: MessageEvent<string>) => void) | null = null;
      constructor() { TestEventSource.latest = this; }
      addEventListener() { /* native EventSource event registration surface */ }
      close() { /* no transport to close in this isolated test */ }
    }
    vi.stubGlobal('EventSource', TestEventSource);
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(liveState), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(liveState), { status: 200 })));

    render(<App />);
    expect(await screen.findByText('episode-synthetic-7')).toBeInTheDocument();
    await waitFor(() => expect(TestEventSource.latest).not.toBeNull());
    const create = await screen.findByRole('button', { name: /Create incident/i });
    expect(create).toBeEnabled();
    const stream = TestEventSource.latest;
    expect(stream).not.toBeNull();
    stream?.onerror?.();

    expect(await screen.findByRole('alert')).toHaveTextContent(/Cached state is stale/i);
    expect(create).toBeDisabled();
  });

  it('opens backend witnesses for returned restrictions and release without inventing events', async () => {
    const governedState = {
      ...liveState,
      release_id: 'release-actual-1',
      restrictions: [{ id: 'restriction-actual-1', rule_type: 'prohibit' }],
      events: [],
    };
    const witness = {
      decision_id: 'restriction-actual-1', status: 'UNRESOLVED', reason_codes: [], completeness: 'PARTIAL',
      nodes: [], edges: [], spans: [],
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(governedState), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(witness), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);

    expect(await screen.findByRole('button', { name: /Open witness for restriction-actual-1/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Open witness for release-actual-1/i })).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: /Timeline/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Open witness for restriction-actual-1/i }));
    expect(await screen.findByText(/Completeness: PARTIAL/i)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/decisions/restriction-actual-1/witness')).toBe(true);
  });

  it('reuses the request event ID when a network failure leaves the incident outcome unknown', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 }))
      .mockRejectedValueOnce(new Error('connection reset'))
      .mockRejectedValueOnce(new Error('connection reset'));
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    const create = await screen.findByRole('button', { name: /Create incident/i });
    await waitFor(() => expect(create).toBeEnabled());
    fireEvent.click(create);
    expect(await screen.findByText(/Request failed|connection reset/i)).toBeInTheDocument();
    fireEvent.click(create);
    expect(await screen.findAllByText(/Request failed|connection reset/i)).toHaveLength(1);

    const incidentCalls = fetchMock.mock.calls.filter(([url]) => url === '/api/incidents');
    expect(incidentCalls).toHaveLength(2);
    const first = JSON.parse(String((incidentCalls[0]?.[1] as RequestInit).body));
    const second = JSON.parse(String((incidentCalls[1]?.[1] as RequestInit).body));
    expect(second.event_id).toBe(first.event_id);
  });
  it('replays only projected events with explicit previous and next controls', async () => {
    const replayState = {
      ...liveState,
      events: [
        { event_id: 'event-1', type: 'TASK_CREATED', world_tick: 1, state: 'observed' },
        { event_id: 'event-2', type: 'COMMAND_RECORDED', world_tick: 2, state: 'accepted' },
      ],
    };
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(replayState), { status: 200 })));

    render(<App />);

    expect(await screen.findByLabelText(/Replay inspector/i)).toHaveTextContent('TASK CREATED');
    expect(screen.getByRole('button', { name: /Previous event/i })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /Next event/i }));
    expect(screen.getByLabelText(/Replay inspector/i)).toHaveTextContent('COMMAND RECORDED');
    expect(screen.getByLabelText(/Replay inspector/i)).toHaveTextContent('event-2');
  });
});

describe('opt-in local mission controls', () => {
  const missionState = (mission_phase: NonNullable<FleetProjection['mission_phase']>, overrides: Partial<FleetProjection> = {}): FleetProjection => {
    const tasks = Array.from({ length: 7 }, (_, index) => ({
      id: `task-${index + 1}`, kind: index === 6 ? 'deliver' : index < 4 ? 'recover' : 'verify',
      state: mission_phase === 'awaiting_owner_release' && index < 4 ? 'VERIFIED' : 'PENDING',
      robot_id: null, depends_on: [], reason_codes: [], last_command_id: null,
    }));
    return {
      ...liveState, revision: 12, operator_mode: 'local_mission', mission_phase, local_owner_id: 'synthetic-owner-demo', tasks, hold_reason: null,
      approval_required: mission_phase === 'awaiting_owner_release',
      release_id: mission_phase === 'awaiting_owner_release' ? 'release-demo' : null,
      ...overrides,
    };
  };
  const mountMission = async (state: FleetProjection) => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ process: 'healthy', dispatch_ready: state.dispatch_ready }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(state), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    expect(await screen.findByText(state.episode_id ?? 'episode-synthetic-7')).toBeInTheDocument();
    return fetchMock;
  };

  it('offers task stepping and bounded run for the initial gated local mission without sending on mount', async () => {
    const fetchMock = await mountMission(missionState('recovery_and_verification'));
    const missionStatus = screen.getByRole('region', { name: /Local mission status/i });
    expect(missionStatus).toHaveTextContent(/OPT-IN LOCAL MISSION/i);
    expect(missionStatus).toHaveTextContent(/synthetic demo owner/i);
    expect(screen.getByRole('button', { name: /Step task/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /^Run tasks$/i })).toBeEnabled();
    expect(fetchMock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === 'POST')).toHaveLength(0);
  });

  it('Run stops for an explicit owner release without invoking approval and shows the backend response', async () => {
    const fetchMock = await mountMission(missionState('recovery_and_verification'));
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(missionState('awaiting_owner_release', { revision: 13 })), { status: 200 }));
    fireEvent.click(screen.getByRole('button', { name: /^Run tasks$/i }));
    await waitFor(() => expect(screen.getByRole('button', { name: /Submit local demo-owner release request for release-demo \(local mission only\)/i })).toBeInTheDocument());
    expect(await screen.findByText(/Run request response received; displaying backend revision 13/i, { selector: '.action-result' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Submit local demo-owner release request for release-demo \(local mission only\)/i })).toBeDisabled();
    const [url, init] = fetchMock.mock.calls[2] as [string, RequestInit];
    expect(url).toBe('/api/run');
    expect(JSON.parse(String(init.body))).toEqual({ event_id: expect.any(String) });
    expect(fetchMock.mock.calls.some(([path]) => String(path).includes('/approve'))).toBe(false);
  });

  it('labels Step as one graph-authorized task and preserves the existing bounded-ticks request', async () => {
    const fetchMock = await mountMission(missionState('recovery_and_verification'));
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(missionState('recovery_and_verification', { revision: 13, commands: [{ command_id: 'c1', robot_id: 'recovery', kind: 'recover', state: 'ACCEPTED', last_known_state: null, reconciliation_state: 'pending', world_tick: 0, reason_codes: [] }] })), { status: 200 }));
    fireEvent.click(screen.getByRole('button', { name: /Step task/i }));
    expect(await screen.findByText(/Step request response received; displaying backend revision 13/i, { selector: '.action-result' })).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[2] as [string, RequestInit];
    expect(url).toBe('/api/step');
    expect(JSON.parse(String(init.body))).toEqual({ ticks: 1, event_id: expect.any(String) });
  });

  it('pauses for explicit local demo-owner release without auto-approving', async () => {
    const fetchMock = await mountMission(missionState('awaiting_owner_release'));
    expect(screen.getByRole('button', { name: /^Run tasks$/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Submit local demo-owner release request for release-demo/i })).toBeDisabled();
    expect(screen.getByText(/synthetic demo owner · not production auth/i)).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /I explicitly request the local demo-owner release/i })).not.toBeChecked();
    expect(fetchMock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === 'POST')).toHaveLength(0);
  });

  it('enables courier tasks only when dispatch is ready and disables all controls at completion or hold', async () => {
    const courierState = (dispatch_ready: boolean) => missionState('courier_delivery', { dispatch_ready });
    const fetchMock = await mountMission(courierState(false));
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(courierState(true)), { status: 200 }));
    expect(screen.getByRole('button', { name: /Step task/i })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /Refresh API state/i }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    cleanup();
    await mountMission(courierState(true));
    expect(screen.getByRole('button', { name: /Step task/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /^Run tasks$/i })).toBeEnabled();
    cleanup();
    await mountMission(missionState('complete', { dispatch_ready: true }));
    expect(screen.getByRole('button', { name: /Step task/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /^Run tasks$/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /^Hold$/i })).toBeDisabled();
    cleanup();
    await mountMission(missionState('held', { dispatch_ready: true }));
    expect(screen.getByRole('button', { name: /Step task/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /^Run tasks$/i })).toBeDisabled();
  });

  it('keeps inspection-only motion and approval disabled even when dispatch reports ready', async () => {
    const inspectionOnlyState = { ...liveState, dispatch_ready: true, approval_required: true, release_id: 'release-inspection' };
    const fetchMock = await mountMission(inspectionOnlyState);
    expect(screen.getByRole('button', { name: /Step 1 tick/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /^Run$/i })).toBeDisabled();
    expect(screen.queryByRole('button', { name: /Submit approval request for release-inspection/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: /reviewed the preview/i })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === 'POST')).toHaveLength(0);
  });

  it('disables mission actions after a stale/error refresh and for incomplete local mission metadata', async () => {
    const fetchMock = await mountMission(missionState('recovery_and_verification', { dispatch_ready: true }));
    fetchMock.mockRejectedValueOnce(new Error('connection lost'));
    fireEvent.click(screen.getByRole('button', { name: /Refresh API state/i }));
    expect(await screen.findByText('API offline', { selector: '.connection' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Step task/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /^Run tasks$/i })).toBeDisabled();
    cleanup();
    await mountMission(missionState('recovery_and_verification', { mission_phase: undefined }));
    expect(screen.getByRole('button', { name: /Step task/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /^Run tasks$/i })).toBeDisabled();
  });
});
