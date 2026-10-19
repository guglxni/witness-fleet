import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Activity, AlertTriangle, ArrowDownRight, Check, ChevronRight, CircleHelp, Clock3, Cpu, Download, ExternalLink, FileText, LockKeyhole, Pause, Play, Radio, RefreshCw, ShieldCheck, TriangleAlert, Wifi, WifiOff, X } from 'lucide-react';
import { CoordinateSpace } from './CoordinateSpace';
import type { FleetProjection, IncidentRequest, WitnessProjection } from '../api-contract';
import { getHealth, getState, postControl, postIncident, type Health } from './api';
import { acceptSnapshot, decisionStateTone, isFleetProjection, missionControlCapabilities } from './state';

const scenarios: IncidentRequest['scenario'][] = ['SC-001', 'SC-002', 'SC-003', 'SC-004', 'SC-005', 'SC-008'];
type LinkState = 'checking' | 'reachable' | 'live' | 'stale' | 'offline';
type ActionResult = { kind: 'response' | 'error'; message: string } | null;

function approvalScope(episodeId: string | null, releaseId: string | null, policyEpoch: number): string | null {
  return releaseId ? JSON.stringify([episodeId, releaseId, policyEpoch]) : null;
}

function eventId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `operator-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function labelFor(value: unknown, fallback = 'Unknown'): string {
  if (typeof value === 'string' && value.trim()) return value.replaceAll('_', ' ');
  if (typeof value === 'number') return String(value);
  return fallback;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function reasonText(state: FleetProjection): string {
  return state.hold_reason || (state.dispatch_ready ? 'Dispatch gate clear; backend owns authorization.' : 'Dispatch is not ready. Review the independent gates and retained evidence.');
}

export function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [projection, setProjection] = useState<FleetProjection | null>(null);
  const [link, setLink] = useState<LinkState>('checking');
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionResult, setActionResult] = useState<ActionResult>(null);
  const [busy, setBusy] = useState(false);
  const [scenario, setScenario] = useState<IncidentRequest['scenario']>('SC-001');
  const [seed, setSeed] = useState('0');
  const [approvalConfirmation, setApprovalConfirmation] = useState<{ key: string; checked: boolean }>({ key: '', checked: false });
  const [approvalRequestVersion, setApprovalRequestVersion] = useState(0);
  const approvalScopeKey = approvalScope(projection?.episode_id ?? null, projection?.release_id ?? null, projection?.policy_epoch ?? 0);
  const approvalConfirmationKey = `${approvalScopeKey ?? ''}:${approvalRequestVersion}`;
  const approvalChecked = approvalConfirmation.key === approvalConfirmationKey && approvalConfirmation.checked;
  const approvalPayload = useMemo(() => projection?.release_id ? {
    expected_policy_epoch: projection.policy_epoch,
    event_id: eventId(),
  } : null, [approvalScopeKey, approvalRequestVersion]);
  const [witness, setWitness] = useState<WitnessProjection | null>(null);
  const [witnessError, setWitnessError] = useState<string | null>(null);
  const [witnessLoading, setWitnessLoading] = useState(false);
  const [replayIndex, setReplayIndex] = useState(0);
  const [recordQuery, setRecordQuery] = useState('');
  const [robotFilter, setRobotFilter] = useState('all');
  const [eventTypeFilter, setEventTypeFilter] = useState('all');
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [selectedCommandId, setSelectedCommandId] = useState<string | null>(null);
  const streamRef = useRef<EventSource | null>(null);
  const projectionRef = useRef<FleetProjection | null>(null);
  const streamStaleRef = useRef(false);
  const episodeMismatchRef = useRef(false);
  const requestIdsRef = useRef(new Map<string, string>());
  const episodeGenerationRef = useRef(0);
  const refreshSequenceRef = useRef(0);

  const applyProjection = useCallback((incoming: FleetProjection, allowEpisodeChange = false): FleetProjection => {
    const accepted = acceptSnapshot(projectionRef.current, incoming, allowEpisodeChange);
    if (accepted.episode_id !== projectionRef.current?.episode_id) {
      episodeGenerationRef.current += 1;
      setWitness(null);
      setWitnessError(null);
      setWitnessLoading(false);
      setActionResult(null);
      requestIdsRef.current.clear();
    }
    projectionRef.current = accepted;
    setProjection(accepted);
    setLoadError(null);
    return accepted;
  }, []);

  const refresh = useCallback(async () => {
    const sequence = ++refreshSequenceRef.current;
    const generation = episodeGenerationRef.current;
    const isCurrent = () => sequence === refreshSequenceRef.current && generation === episodeGenerationRef.current;
    try {
      const nextHealth = await getHealth();
      if (!isCurrent()) return;
      const nextProjection = await getState();
      if (!isCurrent()) return;
      setHealth(nextHealth);
      if (nextProjection) {
        const current = projectionRef.current;
        if (current && nextProjection.episode_id === current.episode_id && nextProjection.revision < current.revision) return;
        episodeMismatchRef.current = false;
        applyProjection(nextProjection, true);
        if (!streamStaleRef.current) setLink('reachable');
      } else {
        setLink(projectionRef.current ? 'stale' : 'reachable');
      }
    } catch (error) {
      if (!isCurrent()) return;
      setLoadError(error instanceof Error ? error.message : 'The operator API could not be reached.');
      setLink('offline');
    }
  }, [applyProjection]);

  useEffect(() => { void refresh(); }, [refresh]);

  useEffect(() => {
    setReplayIndex((current) => Math.min(current, Math.max(0, (projection?.events.length ?? 0) - 1)));
  }, [projection?.revision, projection?.events.length]);

  useEffect(() => {
    if (!projection || typeof EventSource === 'undefined') return;
    const source = new EventSource('/api/events');
    streamRef.current = source;
    const generation = episodeGenerationRef.current;
    const isCurrent = () => streamRef.current === source && generation === episodeGenerationRef.current;
    const markLive = () => { if (isCurrent() && !streamStaleRef.current) setLink('live'); };
    const markStale = () => {
      if (!isCurrent()) return;
      streamStaleRef.current = true;
      setLink('stale');
      void refresh();
    };
    const takeSnapshot = (event: MessageEvent<string>) => {
      if (!isCurrent()) return;
      try {
        const candidate: unknown = JSON.parse(event.data);
        const current = projectionRef.current;
        // SSE has no cross-episode ordering token. Only scoped, non-regressing
        // snapshots may refresh connection state; REST establishes episode changes.
        if (isFleetProjection(candidate) && current && candidate.episode_id !== current.episode_id) {
          episodeMismatchRef.current = true;
          refreshSequenceRef.current += 1;
          streamStaleRef.current = true;
          setLink('stale');
          setLoadError('Stream episode changed. Refresh API state to establish the active episode.');
          return;
        }
        if (!episodeMismatchRef.current && isFleetProjection(candidate) && current
          && candidate.episode_id === current.episode_id && candidate.revision >= current.revision) {
          streamStaleRef.current = false;
          applyProjection(candidate);
          setLink('live');
        }
      } catch { /* malformed snapshots never replace the current projection */ }
    };
    source.onopen = markLive;
    source.onerror = markStale;
    source.onmessage = takeSnapshot;
    source.addEventListener('snapshot', takeSnapshot as EventListener);
    return () => {
      source.close();
      if (streamRef.current === source) streamRef.current = null;
    };
  }, [applyProjection, projection?.episode_id, refresh]);

  const writeEnabled = (link === 'reachable' || link === 'live') && !busy;
  const missionControls = missionControlCapabilities(projection, writeEnabled);
  const localMission = projection?.operator_mode === 'local_mission';
  const missionPhaseLabel = projection?.mission_phase?.replaceAll('_', ' ') ?? 'phase unavailable';
  const approvalReady = localMission && projection?.mission_phase === 'awaiting_owner_release'
    && missionControls.ownerRelease && writeEnabled;
  const sourceItems = useMemo(() => projection?.sources ?? [], [projection]);
  const eventDecisionIds = projection?.events.flatMap((raw) => {
    const id = asRecord(raw).decision_id;
    return typeof id === 'string' && id ? [id] : [];
  }) ?? [];
  const restrictionDecisionIds = projection?.restrictions.flatMap((raw) => {
    const id = asRecord(raw).id;
    return typeof id === 'string' && id ? [id] : [];
  }) ?? [];
  const decisionIds = [...new Set([...eventDecisionIds, ...restrictionDecisionIds, ...(projection?.release_id ? [projection.release_id] : [])])];
  const replayEvents = projection?.events ?? [];
  const replayEvent = replayEvents[replayIndex];
  const normalizedQuery = recordQuery.trim().toLowerCase();
  const matchesQuery = (record: unknown) => !normalizedQuery || JSON.stringify(record).toLowerCase().includes(normalizedQuery);
  const filteredTasks = (projection?.tasks ?? []).filter((task) => (robotFilter === 'all' || task.robot_id === robotFilter) && matchesQuery(task));
  const filteredCommands = (projection?.commands ?? []).filter((command) => (robotFilter === 'all' || command.robot_id === robotFilter) && matchesQuery(command));
  const filteredSources = sourceItems.filter(matchesQuery);
  const filteredEvents = replayEvents.filter((event) => {
    const value = asRecord(event);
    const type = labelFor(value.type ?? value.event_type ?? value.kind, 'Observed event');
    return (eventTypeFilter === 'all' || type.toLowerCase() === eventTypeFilter) && matchesQuery(event);
  });
  const selectedTask = projection?.tasks.find((task) => task.id === selectedTaskId) ?? null;
  const selectedCommand = projection?.commands.find((command) => command.command_id === selectedCommandId) ?? null;
  const eventTypes = [...new Set(replayEvents.map((event) => labelFor(asRecord(event).type ?? asRecord(event).event_type ?? asRecord(event).kind, 'Observed event').toLowerCase()))];

  const runAction = useCallback(async (label: string, operation: () => Promise<FleetProjection>, idempotencyKey?: string, rotateApprovalDraft = false, allowEpisodeChange = false) => {
    if (!writeEnabled) {
      setActionResult({ kind: 'error', message: 'Writes are locked until a fresh backend snapshot is available.' });
      return;
    }
    const generation = episodeGenerationRef.current;
    // Reads started before this mutation cannot later establish another episode.
    refreshSequenceRef.current += 1;
    setBusy(true);
    setActionResult(null);
    try {
      const updated = await operation();
      if (generation !== episodeGenerationRef.current) return;
      const accepted = applyProjection(updated, allowEpisodeChange);
      setActionResult({ kind: 'response', message: `${label} response received; displaying backend revision ${accepted.revision}.` });
      if (idempotencyKey) requestIdsRef.current.delete(idempotencyKey);
      if (rotateApprovalDraft) setApprovalRequestVersion((version) => version + 1);
      setApprovalConfirmation({ key: '', checked: false });
    } catch (error) {
      if (generation !== episodeGenerationRef.current) return;
      const message = error instanceof Error ? error.message : typeof error === 'object' && error && 'detail' in error ? String(error.detail) : 'Request failed. No local success was assumed.';
      setActionResult({ kind: 'error', message });
    } finally {
      setBusy(false);
    }
  }, [applyProjection, writeEnabled]);

  const createIncident = () => {
    const parsedSeed = Number(seed);
    if (!Number.isSafeInteger(parsedSeed) || parsedSeed < 0 || parsedSeed > 2147483647) {
      setActionResult({ kind: 'error', message: 'Seed must be an integer from 0 to 2147483647.' });
      return;
    }
    const idempotencyKey = `incident:${scenario}:${parsedSeed}`;
    const request: IncidentRequest = { scenario, seed: parsedSeed, event_id: requestEventId(idempotencyKey) };
    void runAction('Incident creation', () => postIncident(request), idempotencyKey, false, true);
  };

  const sendControl = (kind: 'step' | 'run' | 'hold') => {
    if (kind === 'step') void runAction('Step request', () => postControl('/api/step', { ticks: 1, event_id: requestEventId('step') }), 'step');
    if (kind === 'run') void runAction('Run request', () => postControl('/api/run', { event_id: requestEventId('run') }), 'run');
    if (kind === 'hold') void runAction('Hold request', () => postControl('/api/hold', { reason: 'Operator requested hold', event_id: requestEventId('hold') }), 'hold');
  };

  function requestEventId(key: string): string {
    const existing = requestIdsRef.current.get(key);
    if (existing) return existing;
    const next = eventId();
    requestIdsRef.current.set(key, next);
    return next;
  }

  const approveRelease = () => {
    if (!projection?.release_id || !approvalPayload || !writeEnabled) return;
    if (projection.operator_mode === 'local_mission' && (!missionControls.ownerRelease || !approvalChecked)) return;
    const releaseId = projection.release_id;
    void runAction('Approval request', () => postControl(`/api/releases/${encodeURIComponent(releaseId)}/approve`, approvalPayload), undefined, true);
  };

  const loadWitness = async (decisionId: string) => {
    const generation = episodeGenerationRef.current;
    setWitness(null);
    setWitnessError(null);
    setWitnessLoading(true);
    try {
      const response = await fetch(`/api/decisions/${encodeURIComponent(decisionId)}/witness`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const value: unknown = await response.json();
      if (!isWitnessProjection(value)) throw new Error('Invalid witness response.');
      if (generation !== episodeGenerationRef.current) return;
      setWitness(value as WitnessProjection);
    } catch (error) {
      if (generation !== episodeGenerationRef.current) return;
      setWitnessError(error instanceof Error ? error.message : 'Witness could not be loaded.');
    } finally {
      if (generation === episodeGenerationRef.current) setWitnessLoading(false);
    }
  };

  const downloadReplay = () => {
    if (!projection) return;
    const blob = new Blob([JSON.stringify({ schema_version: projection.schema_version, revision: projection.revision, episode_id: projection.episode_id, world_tick: projection.world_tick, events: projection.events }, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `witness-fleet-${projection.episode_id ?? 'snapshot'}-events.json`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  };

  const connectionLabel: Record<LinkState, string> = { checking: 'Checking API', reachable: 'API reachable', live: 'Live stream', stale: 'STALE · writes disabled', offline: 'API offline' };
  const LinkIcon = link === 'live' ? Wifi : link === 'stale' || link === 'offline' ? WifiOff : link === 'checking' ? RefreshCw : Radio;

  return (
    <><a className="skip-link" href="#main-content">Skip to main content</a><main className="app-shell" id="main-content" tabIndex={-1}>
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Witness Fleet home"><span className="brand-mark"><Activity size={20} /></span><span><strong>WITNESS FLEET</strong><small>OPERATOR CONSOLE</small></span></a>
        <div className="topbar-right">
          <span className="mode-chip"><span className="mode-dot" />SIMULATION</span>
          <span className={`connection connection-${link}`} aria-live="polite"><LinkIcon size={15} aria-hidden="true" />{connectionLabel[link]}</span>
          <button className="icon-button refresh-button" type="button" onClick={() => void refresh()} aria-label="Refresh API state" title="Refresh API state"><RefreshCw size={17} /></button>
        </div>
      </header>
      {projection && <nav className="workspace-nav" aria-label="Workspace sections"><a href="#facility-heading">Spatial view</a><a href="#tasks-heading">Tasks & commands</a><a href="#evidence-heading">Sources</a><a href="#timeline-heading">Events</a></nav>}

      {projection && (link === 'stale' || link === 'offline') && <div className="stale-banner" role="alert"><TriangleAlert size={18} /> {link === 'offline' ? 'API offline. ' : 'Live stream interrupted. '}Cached state is stale; Cached revision {projection.revision} · world tick {projection.world_tick}. Writes are disabled until a fresh snapshot arrives.</div>}
      {loadError && <div className="error-banner" role="alert"><AlertTriangle size={18} />{loadError}</div>}

      <section className="overview-strip" aria-label="Fleet overview">
        <div className="overview-title"><span className="eyebrow">WITNESS FLEET <i>/</i> LOCAL SIMULATION</span><h1>Physically clear. Loaded courier still restricted.</h1><p>This is the decision principle, not a live episode status. Physical clearance and company authority are independent gates; the live incident projection below is authoritative.</p></div>
        <div className="overview-stat"><span>EPISODE</span><strong>{projection?.episode_id ?? '—'}</strong><small>{projection?.scenario ?? 'No incident loaded'}</small></div>
        <div className="overview-stat"><span>WORLD TICK</span><strong>{projection ? projection.world_tick : '—'}</strong><small>{projection ? `Revision ${projection.revision}` : 'Awaiting state'}</small></div>
        <div className="overview-stat"><span>POLICY EPOCH</span><strong>{projection?.policy_epoch ?? '—'}</strong><small>{projection ? projection.dispatch_ready ? 'Dispatch gate reports ready' : 'Dispatch gate not ready' : 'Unavailable'}</small></div>
      </section>
      {localMission && <section className="mission-status" aria-label="Local mission status">
        <div><span className="eyebrow">OPT-IN LOCAL MISSION</span><strong>{missionPhaseLabel}</strong></div>
        <div><span>Operator mode</span><strong>local_mission</strong></div>
        <div><span>Demo owner</span><strong>{projection.local_owner_id || 'Unavailable'}</strong><span className="mission-demo-owner-label">synthetic demo owner · not production auth</span></div>
        <small>This explicit test/demo owner is not production authentication.</small>
      </section>}

      <section className="decision-principle" aria-label="Decision principle and live gate status">
        <div className="principle-copy"><span className="principle-mark" aria-hidden="true">01</span><div><p className="eyebrow">DECISION PRINCIPLE <span>· NOT A LIVE EPISODE CLAIM</span></p><h2>Clear floor ≠ permission to proceed.</h2><p>No clearance is inferred from a robot pose or an empty observation list. This API contract does not define a courier-clearance verdict.</p></div></div>
        <div className="principle-gates"><div className="principle-gate"><span>PHYSICAL · S0</span><strong className="tone-unknown">Unknown</strong><small>No clearance verdict in the supplied projection contract</small></div><div className="principle-gate"><span>DISPATCH GATE</span><strong className={projection?.dispatch_ready ? 'tone-clear' : 'tone-blocked'}>{projection ? projection.dispatch_ready ? 'Backend reports ready' : 'Not ready' : 'Unavailable'}</strong><small>{projection?.hold_reason ?? (projection ? 'No hold reason returned' : 'Waiting for incident projection')}</small></div></div>
      </section>

      {!projection ? (
        <section className="waiting-card" aria-live="polite">
          <div className="waiting-icon"><Clock3 size={24} /></div>
          <div><p className="eyebrow">NO INCIDENT PROJECTION</p><h2>Waiting for incident/backend state</h2><p>The API health check is separate from incident state. No robots, tasks, or outcomes are shown until the backend returns a projection.</p></div>
          <div className="health-stamp"><span className={`health-dot ${health?.process === 'healthy' ? 'is-up' : ''}`} />{health?.process === 'healthy' ? 'API reachable' : health ? 'API degraded' : 'Checking API'}</div>
        </section>
      ) : (
        <div className="dashboard-grid">
          <CoordinateSpace robots={projection.robots} />

          <section className="panel reason-panel" aria-labelledby="reason-heading">
            <div className="panel-heading"><div><p className="eyebrow">CURRENT DECISION</p><h2 id="reason-heading">Why is motion gated?</h2></div><span className={`state-badge ${projection.dispatch_ready ? 'badge-clear' : 'badge-unknown'}`}>{projection.dispatch_ready ? <Check size={13} /> : <CircleHelp size={13} />}{projection.dispatch_ready ? 'DISPATCH READY' : 'NOT READY'}</span></div>
            <p className="reason-lead">{reasonText(projection)}</p>
            <div className="gate-list">
              <GateRow icon={<Activity size={15} />} title="Physical" status="Unknown · no S0 clearance evidence" tone="unknown" />
              <GateRow icon={<ShieldCheck size={15} />} title="Policy" status="UNKNOWN · policy permission is not exposed by this contract" tone="unknown" />
              <GateRow icon={<ShieldCheck size={15} />} title="Dispatch" status={projection.dispatch_ready ? 'Backend reports ready' : 'Backend reports not ready'} tone={projection.dispatch_ready ? 'clear' : 'blocked'} />
              <GateRow icon={<FileText size={15} />} title="Claim" status="UNKNOWN · retained source records are not claim verdicts" tone="unknown" />
              <GateRow icon={<Clock3 size={15} />} title="Freshness" status={link === 'stale' || link === 'offline' ? 'Stale cached revision' : `Revision ${projection.revision} observed`} tone={link === 'stale' || link === 'offline' ? 'blocked' : 'observed'} />
            </div>
            <dl className="decision-metadata"><div><dt>Current reason</dt><dd>{projection.hold_reason ?? 'No hold reason returned'}</dd></div><div><dt>Graph version</dt><dd>{projection.graph_version}</dd></div><div><dt>Policy epoch</dt><dd>{projection.policy_epoch}</dd></div><div><dt>Coordinator epoch</dt><dd>{projection.coordinator_epoch}</dd></div><div><dt>Dispatch sequence</dt><dd>{projection.dispatch_sequence}</dd></div></dl>
            <div className="gate-footnote"><LockKeyhole size={15} /> Dispatch readiness is a backend field, not a browser authorization or a physical-clearance verdict.</div>
          </section>

          <section className="panel tasks-panel" aria-labelledby="tasks-heading">
            <div className="panel-heading"><div><p className="eyebrow">DEPENDENCY QUEUE</p><h2 id="tasks-heading">Tasks & commands</h2></div><span className="section-meta">{filteredTasks.length}/{projection.tasks.length} TASKS · {filteredCommands.length}/{projection.commands.length} COMMANDS</span></div>
            <div className="record-filters" aria-label="Record filters"><label className="search-field"><span className="visually-hidden">Search records</span><input type="search" aria-label="Search records" placeholder="Search IDs, states, reasons, provenance…" value={recordQuery} onChange={(event) => setRecordQuery(event.target.value)} /></label><label className="filter-field"><span>Robot</span><select aria-label="Filter by robot" value={robotFilter} onChange={(event) => setRobotFilter(event.target.value)}><option value="all">All robots</option>{projection.robots.map((robot) => <option key={robot.id} value={robot.id}>{robot.id}</option>)}</select></label><button type="button" className="clear-filter" onClick={() => { setRecordQuery(''); setRobotFilter('all'); setEventTypeFilter('all'); }}>Clear filters</button></div>
            <div className="table-scroll"><table><thead><tr><th>Task</th><th>Dependency</th><th>State</th><th>Owner</th><th>Reason codes</th></tr></thead><tbody>
              {filteredTasks.map((task) => <tr key={`task-${task.id}`} className={selectedTaskId === task.id ? 'selected-record' : ''}><td><button type="button" className="record-select" aria-label={`Inspect task ${task.id}`} aria-pressed={selectedTaskId === task.id} onClick={() => setSelectedTaskId(selectedTaskId === task.id ? null : task.id)}><strong>{task.id}</strong><small>{task.kind}</small></button></td><td>{task.depends_on.length ? task.depends_on.map((dependency) => <span className="dependency-chip" key={dependency}>{dependency}</span>) : <span className="muted">Root task</span>}</td><td><StatusTag value={task.state} /></td><td>{task.robot_id ?? 'Unassigned'}</td><td>{task.reason_codes.length ? task.reason_codes.join(', ') : '—'}</td></tr>)}
              {!filteredTasks.length && <tr><td colSpan={5} className="empty-table">No task rows match the current filters.</td></tr>}
            </tbody></table></div>
            {selectedTask && <section className="record-inspector" aria-label="Selected task"><div><span className="eyebrow">TASK INSPECTOR</span><button className="close-inspector" type="button" onClick={() => setSelectedTaskId(null)} aria-label="Close task inspector">×</button></div><h3>{selectedTask.id}</h3><dl><div><dt>Kind</dt><dd>{selectedTask.kind}</dd></div><div><dt>State</dt><dd>{selectedTask.state}</dd></div><div><dt>Owner</dt><dd>{selectedTask.robot_id ?? 'Unassigned'}</dd></div><div><dt>Dependencies</dt><dd>{selectedTask.depends_on.join(', ') || 'None returned'}</dd></div><div><dt>Reason codes</dt><dd>{selectedTask.reason_codes.join(', ') || 'None returned'}</dd></div><div><dt>Last command</dt><dd>{selectedTask.last_command_id ?? 'Unknown'}</dd></div></dl></section>}
            <div className="command-ledger"><div className="subsection-heading"><div><span className="eyebrow">COMMAND / RECEIPT LEDGER</span><strong>{filteredCommands.length} matching projected commands</strong></div><span className="command-caveat">A controller receipt is not a verified physical outcome.</span></div>{filteredCommands.length ? <div className="command-list">{filteredCommands.map((command) => <article className={`command-row${selectedCommandId === command.command_id ? ' selected-record' : ''}`} key={command.command_id}><button type="button" className="command-select" aria-label={`Inspect command ${command.command_id}`} aria-pressed={selectedCommandId === command.command_id} onClick={() => setSelectedCommandId(selectedCommandId === command.command_id ? null : command.command_id)}><strong>{command.command_id}</strong><small>{command.kind} · {command.robot_id} · tick {command.world_tick}</small></button><StatusTag value={command.state} /><span className="reconciliation">{command.reconciliation_state.replaceAll('_', ' ')}</span><span className="command-reason">{command.reason_codes.length ? command.reason_codes.join(', ') : 'No reason code'}</span><div className="outcome-unknown">Verified outcome <b>Not present in command projection</b></div></article>)}</div> : <p className="empty-copy">No command records match the current filters.</p>}{selectedCommand && <section className="record-inspector" aria-label="Selected command"><div><span className="eyebrow">COMMAND INSPECTOR</span><button className="close-inspector" type="button" onClick={() => setSelectedCommandId(null)} aria-label="Close command inspector">×</button></div><h3>{selectedCommand.command_id}</h3><dl><div><dt>Kind</dt><dd>{selectedCommand.kind}</dd></div><div><dt>Robot</dt><dd>{selectedCommand.robot_id}</dd></div><div><dt>State</dt><dd>{selectedCommand.state}</dd></div><div><dt>Last known state</dt><dd>{selectedCommand.last_known_state ?? 'Unknown'}</dd></div><div><dt>Reconciliation</dt><dd>{selectedCommand.reconciliation_state}</dd></div><div><dt>World tick</dt><dd>{selectedCommand.world_tick}</dd></div><div><dt>Reason codes</dt><dd>{selectedCommand.reason_codes.join(', ') || 'None returned'}</dd></div></dl></section>}</div>
            <p className="queue-caption"><CircleHelp size={14} /> Task dependencies are backend-declared; no missing edge or postcondition is reconstructed by the browser.</p>
          </section>

          <section className="panel evidence-panel" aria-labelledby="evidence-heading">
            <div className="panel-heading"><div><p className="eyebrow">PROVENANCE</p><h2 id="evidence-heading">Witness & retained sources</h2></div><span className="section-meta">GRAPH v{projection.graph_version}</span></div>
            {filteredSources.length ? <div className="source-list">{filteredSources.map((raw, index) => <SourceCard key={JSON.stringify([projection.episode_id, asRecord(raw).revision_id ?? asRecord(raw).source_id ?? index])} source={asRecord(raw)} index={index} />)}</div> : <p className="empty-copy">{sourceItems.length ? 'No retained source records match the current filters.' : 'No retained source records are present in this projection. No evidence chain is inferred.'}</p>}
            {decisionIds.map((decisionId) => <button type="button" className="witness-link" key={`witness-${decisionId}`} onClick={() => void loadWitness(decisionId)} disabled={witnessLoading}><FileText size={15} /> Open witness for {decisionId}<ChevronRight size={15} /></button>)}
            {witnessError && <p className="inline-error" role="alert">Witness unavailable: {witnessError}</p>}
            {witnessLoading && <p className="inline-status" role="status">Loading backend witness…</p>}
            {witness && <WitnessCard witness={witness} decisionIds={decisionIds} onOpenDecision={(decisionId) => void loadWitness(decisionId)} />}
          </section>

          <section className="panel controls-panel" aria-labelledby="controls-heading">
            <div className="panel-heading"><div><p className="eyebrow">OPERATOR ACTIONS</p><h2 id="controls-heading">Control & recovery</h2></div><span className="section-meta">{localMission ? 'OPT-IN LOCAL MISSION' : 'INSPECTION ONLY · INERT'}</span></div>
            <div className="action-controls">
              <label className="field-label" htmlFor="scenario">Scenario</label><select id="scenario" value={scenario} onChange={(event) => setScenario(event.target.value as IncidentRequest['scenario'])} disabled={!writeEnabled || localMission}><option value="SC-001">SC-001</option><option value="SC-002">SC-002</option><option value="SC-003">SC-003</option><option value="SC-004">SC-004</option><option value="SC-005">SC-005</option><option value="SC-008">SC-008</option></select>
              <label className="field-label" htmlFor="seed">Seed</label><input id="seed" type="number" min="0" max="2147483647" step="1" value={seed} onChange={(event) => setSeed(event.target.value)} disabled={!writeEnabled || localMission} />
              {!localMission && <button className="button button-primary create-button" type="button" disabled={!writeEnabled} onClick={createIncident}><Play size={16} /> Create incident</button>}
            </div>
            <p className="control-guidance" id="dispatch-guidance">{localMission ? 'Step submits one graph-authorized task (the existing bounded-ticks endpoint); Run advances bounded tasks and stops before owner release or completion. No task is approved automatically.' : 'Inspection-only mode is inert. Step, Run, Hold, and owner release remain disabled; incident creation creates only an inspection projection.'}</p>
            <div className="control-actions" aria-describedby="dispatch-guidance">
              <button className="button button-secondary" type="button" disabled={!missionControls.stepTask} onClick={() => sendControl('step')}><ArrowDownRight size={16} /> {localMission ? 'Step task' : 'Step 1 tick'}</button>
              <button className="button button-secondary" type="button" disabled={!missionControls.run} onClick={() => sendControl('run')}><Play size={16} /> {localMission ? 'Run tasks' : 'Run'}</button>
              <button className="button button-danger" type="button" disabled={!missionControls.hold} onClick={() => sendControl('hold')}><Pause size={16} /> Hold</button>
              <button className="button button-secondary replay-button" type="button" disabled={!projection} onClick={downloadReplay}><Download size={16} /> Export events</button>
            </div>
            {localMission && projection.mission_phase === 'awaiting_owner_release' && projection.release_id && <div className="approval-box mission-release-box">
              <div className="approval-heading"><AlertTriangle size={17} /><strong>Explicit local demo-owner release</strong><span>Policy epoch {projection.policy_epoch}</span></div>
              <p>Recovery and verification are complete. Run is paused here. This configured synthetic owner is a test/demo identity, not production authentication; submitting the request does not auto-approve or assert real-world authority.</p>
              <dl className="approval-scope"><div><dt>Release</dt><dd>{projection.release_id}</dd></div><div><dt>Local demo owner</dt><dd>{projection.local_owner_id || 'Unavailable'}</dd></div><div><dt>Policy epoch</dt><dd>{projection.policy_epoch}</dd></div></dl>
              <label className="approval-check"><input type="checkbox" checked={approvalChecked} disabled={!writeEnabled || !missionControls.ownerRelease} onChange={(event) => setApprovalConfirmation({ key: approvalConfirmationKey, checked: event.target.checked })} /><span>I explicitly request the local demo-owner release. This is not production authentication or automatic approval.</span></label>
              <pre className="approval-payload" aria-label="Approval request payload">{JSON.stringify(approvalPayload, null, 2)}</pre>
              <button className="button button-approval" type="button" disabled={!approvalReady || !approvalChecked} onClick={approveRelease}>{localMission ? 'Submit local demo-owner release request for' : 'Submit approval request for'} {projection.release_id}{localMission ? ' (local mission only)' : ''}</button>
            </div>}
            {actionResult && <div className={`action-result result-${actionResult.kind}`} role="status">{actionResult.kind === 'error' ? <X size={16} /> : null}{actionResult.message}</div>}
            <div className="model-state"><Cpu size={16} /><span><b>Model: {projection.model_mode}</b><small>{projection.model_mode === 'disabled' ? 'Disabled — deterministic baseline. No synthetic scores.' : 'Only backend-provided model data is shown.'}</small></span></div>
          </section>

          <section className="panel timeline-panel" aria-labelledby="timeline-heading">
            <div className="panel-heading"><div><p className="eyebrow">OBSERVED EVENT LOG</p><h2 id="timeline-heading">Timeline</h2></div><span className="section-meta">{filteredEvents.length}/{projection.events.length} EVENTS</span></div>
            <div className="record-filters event-filters"><label className="filter-field"><span>Event type</span><select aria-label="Filter by event type" value={eventTypeFilter} onChange={(event) => setEventTypeFilter(event.target.value)}><option value="all">All types</option>{eventTypes.map((type) => <option key={type} value={type}>{type.replaceAll('_', ' ')}</option>)}</select></label></div>
            {filteredEvents.length ? <ol className="timeline">{filteredEvents.map((raw, index) => <TimelineEvent key={`event-${index}`} event={raw} />)}</ol> : <p className="empty-copy">{projection.events.length ? 'No timeline events match the current filters.' : 'No timeline events in the current backend projection.'}</p>}
          </section>

          <section className="panel replay-panel" aria-labelledby="replay-heading" aria-label="Replay inspector">
            <div className="panel-heading"><div><p className="eyebrow">BACKEND SNAPSHOT EVENTS</p><h2 id="replay-heading">Replay inspector</h2></div><span className="section-meta">{replayEvents.length ? `${replayIndex + 1} / ${replayEvents.length}` : 'NO EVENTS'}</span></div>
            <p className="replay-note">Review the event records included in this backend projection. This is a record browser, not a simulator playback.</p>
            {replayEvent === undefined ? <p className="empty-copy">No events are available to replay in this projection.</p> : <ReplayEvent event={replayEvent} index={replayIndex} />}
            <div className="replay-controls"><button className="button button-secondary" type="button" aria-label="Previous event" disabled={!replayEvent || replayIndex === 0} onClick={() => setReplayIndex((current) => Math.max(0, current - 1))}>Previous</button><button className="button button-secondary" type="button" aria-label="Next event" disabled={!replayEvent || replayIndex >= replayEvents.length - 1} onClick={() => setReplayIndex((current) => Math.min(replayEvents.length - 1, current + 1))}>Next</button></div>
          </section>
        </div>
      )}

      {!projection && <section className="panel setup-panel" aria-labelledby="setup-heading"><div className="panel-heading"><div><p className="eyebrow">STARTUP</p><h2 id="setup-heading">Create or await an incident</h2></div><span className="section-meta">REQUEST ONLY · NO LOCAL OUTCOME</span></div><div className="action-controls setup-controls"><label className="field-label" htmlFor="scenario-empty">Scenario</label><select id="scenario-empty" value={scenario} onChange={(event) => setScenario(event.target.value as IncidentRequest['scenario'])} disabled={!writeEnabled}>{scenarios.map((entry) => <option key={entry}>{entry}</option>)}</select><label className="field-label" htmlFor="seed-empty">Seed</label><input id="seed-empty" type="number" min="0" max="2147483647" step="1" value={seed} onChange={(event) => setSeed(event.target.value)} disabled={!writeEnabled} /><button className="button button-primary create-button" type="button" disabled={!writeEnabled} onClick={createIncident}><Play size={16} /> Create incident</button></div>{actionResult && <div className={`action-result result-${actionResult.kind}`} role="status">{actionResult.kind === 'error' ? <X size={16} /> : null}{actionResult.message}</div>}</section>}

      <footer className="footer-bar"><span><span className="sensor-pill">LOCAL</span> Read-only projections until an explicit backend request.</span><span><span className="footer-health" />{health?.process === 'healthy' ? 'Health probe: healthy' : 'Health probe: unconfirmed'}</span></footer>
    </main></>
  );
}

function GateRow({ icon, title, status, tone }: { icon: React.ReactNode; title: string; status: string; tone: string }) {
  return <div className="gate-row"><span className="gate-icon" aria-hidden="true">{icon}</span><strong>{title}</strong><span className={`gate-status tone-${tone}`}><span className="status-symbol">{tone === 'clear' || tone === 'observed' ? '●' : tone === 'blocked' ? '!' : '?'}</span>{status}</span></div>;
}

function StatusTag({ value }: { value: string }) {
  const state = value.toLowerCase().replaceAll('_', ' ');
  const className = decisionStateTone(value);
  return <span className={`status-tag tag-${className}`}><span aria-hidden="true">{className === 'verified' ? '✓' : className === 'unresolved' ? '!' : className === 'in-progress' ? '◷' : '·'}</span>{state}</span>;
}

function SourceCard({ source, index }: { source: Record<string, unknown>; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const [retainedText, setRetainedText] = useState<string | null>(null);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const quote = typeof source.quote === 'string' ? source.quote : typeof source.text === 'string' ? source.text : null;
  const sourceId = labelFor(source.source_id ?? source.revision_id, `Source ${index + 1}`);
  const revisionId = typeof source.revision_id === 'string' ? source.revision_id : null;
  const loadRetainedText = async () => {
    if (!revisionId) return;
    setSourceError(null);
    try {
      const response = await fetch(`/api/sources/${encodeURIComponent(revisionId)}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const record: unknown = await response.json();
      if (!record || typeof record !== 'object' || typeof (record as Record<string, unknown>).text !== 'string') throw new Error('Source response has no retained text.');
      setRetainedText((record as Record<string, unknown>).text as string);
    } catch (error) {
      setSourceError(error instanceof Error ? error.message : 'Retained source could not be loaded.');
    }
  };
  const displayedText = quote ?? retainedText;
  return <article className="source-card"><div className="source-card-head"><FileText size={16} /><strong>{sourceId}</strong><span className="source-type">{labelFor(source.type ?? source.kind, 'retained record')}</span></div><div className="source-meta">Revision {labelFor(source.revision_id, 'unknown')} · Owner {labelFor(source.owner ?? source.actor_id, 'unknown')} · Restriction {labelFor(source.restriction, 'unspecified')}</div><dl className="source-fingerprint">{typeof source.normalized_hash === 'string' && <div><dt>Normalized hash</dt><dd className="mono">{source.normalized_hash}</dd></div>}{typeof source.normalizer_version === 'string' && <div><dt>Normalizer</dt><dd>{source.normalizer_version}</dd></div>}</dl>{displayedText ? <><blockquote className={expanded ? 'quote-expanded' : ''}>“{displayedText}”</blockquote>{displayedText.length > 180 && <button type="button" className="text-button" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}>{expanded ? 'Show less' : 'Read retained text'}</button>}</> : revisionId ? <button type="button" className="text-button" onClick={() => void loadRetainedText()}>Load retained source {revisionId}</button> : <p className="muted">No retained text or revision locator returned.</p>}{sourceError && <p className="inline-error" role="alert">Source unavailable: {sourceError}</p>}</article>;
}

function WitnessCard({ witness, decisionIds, onOpenDecision }: { witness: WitnessProjection; decisionIds: string[]; onOpenDecision: (decisionId: string) => void }) {
  const positions = witness.nodes.map((node, index) => ({ node, x: 24 + (index % 3) * 190, y: 34 + Math.floor(index / 3) * 92 }));
  const positionById = new Map(positions.map(({ node, x, y }) => [node.id, { x, y }]));
  const width = Math.max(420, Math.min(640, 48 + Math.min(3, witness.nodes.length) * 190));
  const height = Math.max(96, 68 + Math.ceil(witness.nodes.length / 3) * 92);
  return <div className="witness-card"><div className="witness-title"><span>DECISION {witness.decision_id}</span><StatusTag value={witness.status} /></div><p className="witness-completeness">Completeness: {witness.completeness.replaceAll('_', ' ')} · {witness.reason_codes.length ? `Reasons: ${witness.reason_codes.join(', ')}` : 'No reason codes returned'}</p>
    {witness.nodes.length ? <div className="witness-graph-scroll" role="region" aria-label="Scrollable witness graph" tabIndex={0}><svg className="witness-graph" style={{ width, height }} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Graph witness for ${witness.decision_id}`}>
      <defs><marker id="witness-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" className="witness-arrowhead" /></marker></defs>
      {witness.edges.map((edge, index) => {
        const from = positionById.get(edge.source_id);
        const to = positionById.get(edge.target_id);
        if (!from || !to) return null;
        return <g key={`${edge.source_id}-${edge.target_id}-${index}`}><line x1={from.x + 84} y1={from.y + 20} x2={to.x + 84} y2={to.y + 20} className="witness-edge" markerEnd="url(#witness-arrow)" /><text x={(from.x + to.x) / 2 + 84} y={(from.y + to.y) / 2 + 15} className="witness-edge-label">{edge.relationship}</text></g>;
      })}
      {positions.map(({ node, x, y }) => <g key={node.id}><rect x={x} y={y} width="168" height="42" rx="6" className="witness-node" /><text x={x + 8} y={y + 17} className="witness-node-type">{node.type.slice(0, 18)}</text><text x={x + 8} y={y + 33} className="witness-node-label">{node.label.slice(0, 18)}</text></g>)}
    </svg></div> : <p className="empty-copy">The backend returned no witness nodes.</p>}
    <div className="witness-table-wrap"><table className="witness-table" aria-label="Witness nodes"><thead><tr><th>Type</th><th>Node</th></tr></thead><tbody>{witness.nodes.map((node) => <tr key={node.id}><td>{node.type}</td><td><strong>{node.label}</strong><small className="mono">{node.id}</small></td></tr>)}</tbody></table></div>
    <div className="witness-links" aria-label="Related governance witnesses">{decisionIds.filter((id) => id !== witness.decision_id).map((decisionId) => <button type="button" className="witness-link" key={`related-${decisionId}`} onClick={() => onOpenDecision(decisionId)}>{decisionId}</button>)}{witness.edges.map((edge, index) => <p key={`${edge.source_id}-${index}`}><span className="mono">{edge.source_id}</span><ChevronRight size={13} aria-hidden="true" /><span>{edge.relationship}</span><ChevronRight size={13} aria-hidden="true" /><span className="mono">{edge.target_id}</span></p>)}</div>{witness.spans.map((span, index) => <blockquote className="retained-quote" key={`${span.revision_id}-${index}`}>“{span.quote}”<small>Revision {span.revision_id} · characters {span.start}–{span.end}</small></blockquote>)}</div>;
}

function isWitnessProjection(value: unknown): value is WitnessProjection {
  if (!value || typeof value !== 'object') return false;
  const witness = value as Partial<WitnessProjection>;
  return typeof witness.decision_id === 'string' && typeof witness.status === 'string'
    && typeof witness.completeness === 'string' && Array.isArray(witness.reason_codes)
    && witness.reason_codes.every((reason) => typeof reason === 'string')
    && Array.isArray(witness.nodes) && witness.nodes.every((node) => node && typeof node.id === 'string' && typeof node.type === 'string' && typeof node.label === 'string')
    && Array.isArray(witness.edges) && witness.edges.every((edge) => edge && typeof edge.source_id === 'string' && typeof edge.target_id === 'string' && typeof edge.relationship === 'string')
    && Array.isArray(witness.spans) && witness.spans.every((span) => span && typeof span.revision_id === 'string' && Number.isSafeInteger(span.start) && Number.isSafeInteger(span.end) && span.start >= 0 && span.end >= span.start && typeof span.quote === 'string');
}

function TimelineEvent({ event: raw }: { event: unknown }) {
  const event = asRecord(raw);
  const [expanded, setExpanded] = useState(false);
  const type = labelFor(event.type ?? event.event_type ?? event.kind, 'Observed event');
  const id = event.event_id ?? event.id ?? event.command_id ?? '—';
  const tick = event.world_tick ?? event.tick;
  return <li className="timeline-item"><span className="timeline-node" aria-hidden="true"><Activity size={12} /></span><div className="timeline-body"><div className="timeline-top"><strong>{type}</strong><span>{typeof tick === 'number' ? `Tick ${tick}` : 'Tick unknown'}</span></div><p>{labelFor(event.reason ?? event.message ?? event.state, 'Backend event recorded.')}</p><button type="button" className="text-button" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>{expanded ? 'Hide event fields' : 'Inspect event fields'} <ExternalLink size={12} /></button>{expanded && <pre className="event-json">{JSON.stringify({ id, ...event }, null, 2)}</pre>}</div></li>;
}

function ReplayEvent({ event: raw, index }: { event: unknown; index: number }) {
  const event = asRecord(raw);
  const type = labelFor(event.type ?? event.event_type ?? event.kind, 'Observed event');
  const id = event.event_id ?? event.id ?? event.command_id ?? '—';
  const tick = event.world_tick ?? event.tick;
  return <article className="replay-event" aria-live="polite"><div><span className="eyebrow">EVENT {index + 1}</span><StatusTag value={type} /></div><h3>{type}</h3><p>{labelFor(event.reason ?? event.message ?? event.state, 'No event summary returned.')}</p><dl><div><dt>Event ID</dt><dd className="mono">{String(id)}</dd></div><div><dt>World tick</dt><dd>{typeof tick === 'number' ? tick : 'Unknown'}</dd></div></dl><details><summary>Inspect projected fields</summary><pre className="event-json">{JSON.stringify(event, null, 2)}</pre></details></article>;
}
