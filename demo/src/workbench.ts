export type Task = { task_id: string; kind: string; state: string; robot_id: string | null };
export type Robot = { robot_id: string; pose: { x: number; y: number; yaw: number } };
export type Command = { kind: string; state: string; task_id: string | null; robot_id: string | null; effects?: Record<string, boolean> };
export type MissionState = {
  mission_phase: string;
  revision_tick: number;
  tasks: Task[];
  robots: Robot[];
  commands: Command[];
  metrics: Record<string, number | null>;
  expected_policy_epoch: number;
};
export type Geometry = {
  id: string; kind: 'plane' | 'box' | 'cylinder' | 'sphere'; position: [number, number, number];
  quaternion: [number, number, number, number]; size: [number, number, number]; rgba: [number, number, number, number]; body: string | null;
};
export type Site = { id: string; position: [number, number, number]; size: [number, number, number] };
export type SceneSnapshot = {
  schema_version: 1; source: 'mujoco_snapshot'; world_tick: number; model_sha256: string; units: 'm'; up_axis: 'z'; geometries: Geometry[]; sites: Site[];
};
export type Sample = { state: MissionState; scene: SceneSnapshot | null; sampleNumber: number };

const geometryAllowlist: Record<string, [Geometry['kind'], string | null]> = {
  floor: ['plane', null], corridor_south_wall: ['box', null], corridor_north_wall_west: ['box', null],
  corridor_north_wall_east: ['box', null], west_wall: ['box', null], east_wall: ['box', null], scenario_occluder: ['box', null],
  scout_chassis: ['cylinder', 'scout'], recovery_chassis: ['cylinder', 'recovery'], recovery_pusher: ['box', 'recovery'],
  courier_chassis: ['box', 'courier'], carton_geom: ['box', 'carton'], heavy_box_geom: ['box', 'heavy_box'],
  parcel_geom: ['box', 'parcel'], alternate_block_geom: ['box', 'alternate_route_block'],
};
const siteAllowlist = new Set(['south_staging', 'north_staging', 'recovery_bay', 'delivery_zone', 'scout_sensor', 'recovery_sensor', 'courier_sensor']);
const exact = (value: unknown, keys: string[]) => !!value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).sort().join('|') === [...keys].sort().join('|');
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const vector = (v: unknown, n: number, low: number, high: number): v is number[] => Array.isArray(v) && v.length === n && v.every((x) => finite(x) && x >= low && x <= high);

export function validateScene(value: unknown): SceneSnapshot {
  if (!exact(value, ['schema_version', 'source', 'world_tick', 'model_sha256', 'units', 'up_axis', 'geometries', 'sites'])) throw new Error('scene_schema_invalid');
  const v = value as Record<string, unknown>;
  if (v.schema_version !== 1 || v.source !== 'mujoco_snapshot' || !Number.isSafeInteger(v.world_tick) || Number(v.world_tick) < 0 ||
      typeof v.model_sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(v.model_sha256) || v.units !== 'm' || v.up_axis !== 'z' ||
      !Array.isArray(v.geometries) || v.geometries.length > 64 || !Array.isArray(v.sites) || v.sites.length > 16) throw new Error('scene_schema_invalid');
  const ids = new Set<string>();
  for (const raw of v.geometries) {
    if (!exact(raw, ['id', 'kind', 'position', 'quaternion', 'size', 'rgba', 'body'])) throw new Error('scene_schema_invalid');
    const g = raw as Record<string, unknown>;
    const expected = typeof g.id === 'string' ? geometryAllowlist[g.id] : undefined;
    if (!expected || ids.has(g.id as string) || g.kind !== expected[0] || g.body !== expected[1] || !vector(g.position, 3, -100, 100) ||
        !vector(g.quaternion, 4, -1.000001, 1.000001) || Math.abs(Math.hypot(...g.quaternion) - 1) > 1e-5 ||
        !vector(g.size, 3, 0, 20) || !vector(g.rgba, 4, 0, 1)) throw new Error('scene_schema_invalid');
    ids.add(g.id as string);
  }
  const missingGeometries = Object.keys(geometryAllowlist).filter((id) => !ids.has(id));
  const siteIds = new Set<string>();
  for (const raw of v.sites) {
    if (!exact(raw, ['id', 'position', 'size'])) throw new Error('scene_schema_invalid');
    const site = raw as Record<string, unknown>;
    if (typeof site.id !== 'string' || !siteAllowlist.has(site.id) || siteIds.has(site.id) || !vector(site.position, 3, -100, 100) || !vector(site.size, 3, 0, 20)) throw new Error('scene_schema_invalid');
    siteIds.add(site.id);
  }
  const missingSites = [...siteAllowlist].filter((id) => !siteIds.has(id));
  if (missingGeometries.length || missingSites.length) {
    const omitted = [...missingGeometries, ...missingSites].join(', ');
    throw new Error(`scene_incomplete · omitted IDs: ${omitted}`);
  }
  return value as SceneSnapshot;
}

export function validateState(value: unknown): MissionState {
  if (!exact(value, ['mission_phase', 'revision_tick', 'tasks', 'robots', 'commands', 'metrics', 'expected_policy_epoch'])) throw new Error('state_schema_invalid');
  const v = value as Record<string, unknown>;
  if (typeof v.mission_phase !== 'string' || !Number.isSafeInteger(v.revision_tick) || Number(v.revision_tick) < 0 ||
      !Number.isSafeInteger(v.expected_policy_epoch) || Number(v.expected_policy_epoch) < 0 || !Array.isArray(v.tasks) || !Array.isArray(v.robots) || !Array.isArray(v.commands) ||
      !v.metrics || typeof v.metrics !== 'object' || Array.isArray(v.metrics)) throw new Error('state_schema_invalid');
  if (v.mission_phase.length > 64 || v.tasks.length > 32 || v.robots.length > 16 || v.commands.length > 32) throw new Error('state_schema_invalid');
  const isRecord = (item: unknown): item is Record<string, unknown> => !!item && typeof item === 'object' && !Array.isArray(item);
  const exactRow = (item: unknown, required: string[], optional: string[] = []) => isRecord(item) &&
    required.every((key) => Object.hasOwn(item, key)) && Object.keys(item).every((key) => required.includes(key) || optional.includes(key));
  const boundedString = (item: unknown, max: number) => typeof item === 'string' && item.length <= max;
  if (!v.tasks.every((task) => exactRow(task, ['task_id', 'kind', 'state', 'robot_id']) &&
      boundedString(task.task_id, 128) && boundedString(task.kind, 128) && boundedString(task.state, 128) &&
      (task.robot_id === null || boundedString(task.robot_id, 64)))) throw new Error('state_schema_invalid');
  if (!v.robots.every((robot) => exactRow(robot, ['robot_id', 'pose']) && boundedString(robot.robot_id, 64) &&
      isRecord(robot.pose) && Object.keys(robot.pose).sort().join('|') === 'x|y|yaw' &&
      ['x', 'y', 'yaw'].every((axis) => finite(robot.pose[axis]) && Math.abs(robot.pose[axis] as number) <= 10000))) throw new Error('state_schema_invalid');
  if (!v.commands.every((command) => exactRow(command, ['kind', 'state'], ['task_id', 'robot_id', 'effects']) &&
      boundedString(command.kind, 128) && boundedString(command.state, 128) &&
      (!Object.hasOwn(command, 'task_id') || command.task_id === null || boundedString(command.task_id, 128)) &&
      (!Object.hasOwn(command, 'robot_id') || command.robot_id === null || boundedString(command.robot_id, 128)) &&
      (command.effects === undefined || (isRecord(command.effects) && Object.entries(command.effects).every(([key, flag]) => key.length <= 64 && typeof flag === 'boolean'))))) throw new Error('state_schema_invalid');
  const metricKeys = ['recovery_verified', 'delivery_completed', 'unauthorized_executed'];
  if (Object.keys(v.metrics).some((key) => !metricKeys.includes(key)) ||
      Object.values(v.metrics).some((metric) => metric !== null && !finite(metric))) throw new Error('state_schema_invalid');
  return value as MissionState;
}

export type WorkbenchSnapshot = {
  state: MissionState | null; scene: SceneSnapshot | null; samples: Sample[]; selectedSample: number | null;
  busy: boolean; outcomeUnknown: boolean; canMutate: boolean; csrfAvailable: boolean; sessionReady: boolean;
  notice: string; sceneNotice: string; selectedObject: string | null; wireframe: boolean; showFacility: boolean; showSites: boolean; search: string;
  displayedState: MissionState | null; displayedScene: SceneSnapshot | null; live: boolean; releaseArmedEpoch: number | null;
};

export class HostedWorkbench {
  private state: MissionState | null = null;
  private scene: SceneSnapshot | null = null;
  private samples: Sample[] = [];
  private selectedSample: number | null = null;
  private busy = false;
  private outcomeUnknown = false;
  private sessionReady = false;
  private csrf: string | null = null;
  private notice = 'No session attached. Start creates an isolated simulation only after you request it.';
  private sceneNotice = 'Scene snapshot not loaded.';
  private selectedObject: string | null = null;
  private wireframe = false;
  private showFacility = true;
  private showSites = true;
  private search = '';
  private readonly listeners = new Set<() => void>();
  private readonly fetcher: typeof fetch;
  private snapshotCache!: WorkbenchSnapshot;
  constructor(fetcher: typeof fetch = fetch) { this.fetcher = fetcher.bind(globalThis); this.snapshotCache = this.buildSnapshot(); }
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => this.listeners.delete(listener); };
  private emit() { this.snapshotCache = this.buildSnapshot(); this.listeners.forEach((listener) => listener()); }
  get snapshot(): WorkbenchSnapshot { return this.snapshotCache; }
  private buildSnapshot(): WorkbenchSnapshot {
    const historical = this.selectedSample !== null ? this.samples.find((s) => s.sampleNumber === this.selectedSample) : null;
    return { state: this.state, scene: this.scene, samples: [...this.samples], selectedSample: this.selectedSample, busy: this.busy, outcomeUnknown: this.outcomeUnknown,
      canMutate: this.sessionReady && !!this.csrf && !this.busy && !this.outcomeUnknown && this.selectedSample === null, csrfAvailable: !!this.csrf, sessionReady: this.sessionReady,
      notice: this.notice, sceneNotice: this.sceneNotice, selectedObject: this.selectedObject, wireframe: this.wireframe, showFacility: this.showFacility, showSites: this.showSites,
      search: this.search, displayedState: this.selectedSample === null ? this.state : historical?.state ?? null, displayedScene: this.selectedSample === null ? this.scene : historical?.scene ?? null,
      live: this.selectedSample === null, releaseArmedEpoch: this._releaseArmedEpoch };
  }
  private _releaseArmedEpoch: number | null = null;
  hydrate(csrf: string | null, state: MissionState, capture = true) { this.csrf = csrf; this.state = validateState(state); this.sessionReady = true; this._releaseArmedEpoch = null; this.notice = csrf ? 'Session active. Actions remain explicit.' : 'Session reattached read-only. Reload cannot recover the CSRF token; motion is disabled.'; if (capture) this.recordSample(); this.emit(); }
  setScene(value: unknown) { try { this.scene = validateScene(value); this.sceneNotice = 'Authenticated MuJoCo scene sample'; } catch { this.scene = null; this.sceneNotice = 'Scene unavailable · no synthetic geometry is shown'; } this.emit(); }
  private async json(path: string, init?: RequestInit): Promise<unknown> {
    const response = await this.fetcher(`/demo/v1/${path}`, { credentials: 'same-origin', cache: 'no-store', ...init });
    let data: unknown;
    try { data = await response.json(); } catch { if (response.ok) throw new Error('response_malformed'); data = {}; }
    if (!response.ok) {
      const body = data as { detail?: string; error?: string };
      const reason = body.detail || body.error || `http_${response.status}`;
      throw new Error(`http_${response.status}:${reason}`);
    }
    return data;
  }
  private enterBusy() { if (this.busy) return false; this.busy = true; this.emit(); return true; }
  private finishBusy() { this.busy = false; this.emit(); }
  async reattach() {
    if (!this.enterBusy()) return false;
    try {
      const data = await this.json('sessions') as { session?: { status?: string }; state?: unknown };
      if (data.session?.status !== 'active' || !data.state) throw new Error('session_unavailable');
      this.hydrate(null, validateState(data.state), false); await this.fetchScene(); this.recordSample(); return true;
    } catch (error) { this.notice = `No active session attached · ${message(error)}`; this.emit(); return false; }
    finally { this.finishBusy(); }
  }
  async createSession() {
    if (this.outcomeUnknown || this.sessionReady || !this.enterBusy()) return false;
    try {
    const data = await this.json('bootstrap') as { csrf_token?: string };
      if (!data.csrf_token) throw new Error('bootstrap_malformed');
      this.csrf = data.csrf_token;
      const created = await this.json('sessions', { method: 'POST', headers: this.headers(), body: JSON.stringify({ request_id: requestId('create') }) }) as { csrf_token?: string; state?: unknown };
      if (typeof created.csrf_token !== 'string' || !created.state) throw new Error('response_malformed');
      this.hydrate(created.csrf_token, validateState(created.state), false); this.notice = 'Isolated session active · no action runs automatically';
      await this.fetchScene(); this.recordSample(); return true;
    } catch { this.handleUnknown(); return false; }
    finally { this.finishBusy(); }
  }
  async refresh() {
    if (!this.enterBusy()) return false;
    try {
      const value = await this.json('sessions') as { session?: { status?: string }; state?: unknown };
      if (value.session?.status !== 'active' || !value.state) throw new Error('session_unavailable');
      this.state = validateState(value.state); this.notice = 'Read-only state refresh sampled'; this.emit();
      await this.fetchScene(); this.recordSample(); return true;
    } catch (error) { this.notice = `Refresh unavailable · ${message(error)}`; this.emit(); return false; }
    finally { this.finishBusy(); }
  }
  private async fetchScene() {
    try { this.setScene(await this.json('scene')); }
    catch (error) { this.scene = null; this.sceneNotice = `Scene unavailable · ${message(error)} · no synthetic geometry is shown`; this.emit(); }
  }
  private headers() { return { 'Content-Type': 'application/json', 'X-CSRF-Token': this.csrf ?? '' }; }
  private async mutate(path: 'run' | 'step' | 'confirm-release', body: Record<string, unknown>) {
    if (!this.sessionReady || !this.csrf || this.busy || this.outcomeUnknown || this.selectedSample !== null) return false;
    if (!this.enterBusy()) return false;
    try {
      const data = validateState(await this.json(path, { method: 'POST', headers: this.headers(), body: JSON.stringify(body) }));
      this.state = data; this._releaseArmedEpoch = null; this.selectedSample = null; this.notice = 'Controller state receipt received · scene is a separate sample';
      try { this.scene = validateScene(await this.json('scene')); this.sceneNotice = 'Authenticated MuJoCo scene sample · separate read'; }
      catch (sceneError) { this.scene = null; this.sceneNotice = `Scene unavailable · ${message(sceneError)} · no synthetic geometry is shown`; }
      this.recordSample(); this.emit(); return true;
    } catch (error) {
      const reason = message(error);
      if (isAllowlistedPreExecutionRejection(reason)) {
        this.notice = `Action rejected · ${reason.slice(reason.indexOf(':') + 1)}`;
        this.scene = null; this.sceneNotice = 'Scene snapshot not refreshed after rejected action';
      } else this.handleUnknown();
      this.emit(); return false;
    }
    finally { this.finishBusy(); }
  }
  async runMission() { return this.mutate('run', { request_id: requestId('run') }); }
  async stepOnce() { return this.mutate('step', { request_id: requestId('step'), ticks: 1 }); }
  armRelease(checked: boolean) {
    this._releaseArmedEpoch = checked && this.state?.mission_phase === 'awaiting_owner_release' ? this.state.expected_policy_epoch : null; this.emit();
  }
  async confirmRelease(checked: boolean) {
    const state = this.state;
    if (!checked || !state || state.mission_phase !== 'awaiting_owner_release' || this._releaseArmedEpoch !== state.expected_policy_epoch || !this.snapshot.canMutate) return false;
    return this.mutate('confirm-release', { request_id: requestId('release'), expected_policy_epoch: state.expected_policy_epoch, confirmed: true });
  }
  private handleUnknown() {
    this.outcomeUnknown = true; this._releaseArmedEpoch = null;
    this.notice = 'Motion safety lock · outcome_unknown_no_retry. No retry, reset, or replacement session; read-only refresh only.';
    this.emit();
  }
  recordSample() { if (!this.state) return; const next = (this.samples.at(-1)?.sampleNumber ?? 0) + 1; this.samples = [...this.samples, { state: structuredClone(this.state), scene: this.scene ? structuredClone(this.scene) : null, sampleNumber: next }].slice(-40); this.emit(); }
  selectSample(sampleNumber: number | null) { this.selectedSample = sampleNumber; this.emit(); }
  selectObject(id: string | null) { this.selectedObject = id; this.emit(); }
  setWireframe(v: boolean) { this.wireframe = v; this.emit(); }
  setShowFacility(v: boolean) { this.showFacility = v; this.emit(); }
  setShowSites(v: boolean) { this.showSites = v; this.emit(); }
  setSearch(v: string) { this.search = v; this.emit(); }
}
function requestId(prefix: string) { return `${prefix}-${crypto.randomUUID()}`; }
function message(error: unknown) { return error instanceof Error ? error.message : 'request_failed'; }
function isAllowlistedPreExecutionRejection(reason: string) {
  const match = /^http_409:(simulation_action_rejected|release_not_authorized|simulation_held)$/.exec(reason);
  return match !== null;
}
