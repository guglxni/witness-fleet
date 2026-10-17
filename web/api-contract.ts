// Operator-only projections. Motion and policy authorizations are backend-owned.
export type RobotProjection = { id: string; role: 'scout'|'recovery'|'courier'; pose: {x:number;y:number;yaw:number}; state: string; footprint_m:number; last_observation_tick:number|null };
export type TaskProjection = {id:string;kind:string;state:string;robot_id:string|null;depends_on:string[];reason_codes:string[];last_command_id:string|null};
export type CommandProjection={command_id:string;robot_id:string;kind:string;state:string;last_known_state:string|null;reconciliation_state:string;world_tick:number;reason_codes:string[]};
export type MissionPhase = 'recovery_and_verification' | 'awaiting_owner_release' | 'courier_delivery' | 'complete' | 'held';
export type OperatorMode = 'inspection_only' | 'local_mission';
export type FleetProjection={schema_version:1;revision:number;episode_id:string|null;scenario:string|null;world_tick:number;graph_version:number;policy_epoch:number;coordinator_epoch:number;dispatch_sequence:number;dispatch_ready:boolean;hold_reason:string|null;operator_mode?:OperatorMode;mission_phase?:MissionPhase;local_owner_id?:string|null;model_mode:'disabled'|'shadow'|'advisory';sensor_mode:'S0';robots:RobotProjection[];tasks:TaskProjection[];commands:CommandProjection[];observations:Record<string,unknown>[];restrictions:Record<string,unknown>[];sources:Record<string,unknown>[];events:Record<string,unknown>[];approval_required:boolean;release_id:string|null;metrics:Record<string,number|null>};
export type WitnessProjection={decision_id:string;status:string;reason_codes:string[];nodes:{id:string;type:string;label:string;properties:Record<string,unknown>}[];edges:{source_id:string;target_id:string;relationship:string}[];spans:{revision_id:string;start:number;end:number;quote:string}[];completeness:string};
export type SourceProjection={revision_id:string;source_id:string;text:string;normalized_hash:string;normalizer_version:string};
export type IncidentRequest={scenario:'SC-001'|'SC-002'|'SC-003'|'SC-004'|'SC-005'|'SC-008';seed:number;event_id:string};
// GET /api/state, GET /api/events SSE (snapshot event), GET /api/decisions/:id/witness
// POST /api/incidents, POST /api/step {ticks:bounded,event_id}, POST /api/run {event_id}
// POST /api/hold {reason,event_id}, POST /api/releases/:id/approve {expected_policy_epoch,event_id}
// Backend resolves synthetic maintenance-owner identity and retained release span itself;
// request JSON may not claim actor_id, permissions or success.
