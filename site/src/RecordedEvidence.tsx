import {useState} from 'react';
import evidence from './recorded-evidence.json';
import './recorded-evidence.css';

type TaskReceipt = {task_id:string;robot_id:string;kind:string;state:string;last_command_id:string|null};
type CommandReceipt = {command_id:string;task_id:string;robot_id:string;kind:string;state:string;native_status:string;accepted_tick:number;started_tick:number;completed_world_tick:number;contact_count:number|null;max_contact_force_n:number|null;measured_displacement_m:number|null;phase:string|null};
type RecordedStage = {stage:string;recorded_phase:string;observation:{world_tick:number};graph_version:number;policy_epoch:number;approval_required:boolean|null;held:boolean|null;task_count:number;command_count:number;metrics:{delivery_completed:number|null;recovery_verified:number|null;unauthorized_executed:number|null};tasks:TaskReceipt[];commands:CommandReceipt[]};
type RecordedData = {scenario:string;seed:number;recorded_run_status:string;manifest_generated_at_utc:string;source:{sha256:string;captured_source_file_hash_count:number;source_file_hashes_currently_verified:boolean};versions:Record<string,string>;stages:RecordedStage[];release_action:{performed:boolean;human_authenticated:boolean};evidence_boundary:{capture_scope:string;live_db_reads:boolean;live_actions:boolean;current_source_revision_verified:boolean;pre_release_behavior:string;unauthorized_metric:string}};
const data=evidence as RecordedData;
const numberLabel=(value:number|null)=>value===null?'Not recorded':value.toLocaleString('en-US');

export function RecordedEvidence(){
  const [stageIndex,setStageIndex]=useState(0);
  const stage=data.stages[stageIndex]!;
  const stageLabel=stage.recorded_phase.replaceAll('_',' ');
  const finalIndex=data.stages.findIndex(item=>item.stage==='complete');
  return <section className="recorded-evidence" aria-labelledby="recorded-evidence-heading">
    <div className="recorded-evidence-heading-row">
      <div><span className="section-kicker"><span className="kicker-rule"/> RECORDED RECEIPT · {data.scenario}</span><h2 id="recorded-evidence-heading">Recorded run evidence</h2></div>
      <a className="recorded-download" href="/media/recorded-evidence.json" download="witness-fleet-recorded-evidence.json" aria-label="Download sanitized evidence JSON">Download sanitized evidence JSON <span aria-hidden="true">↗</span></a>
    </div>
    <div className="recorded-evidence-notice" role="note"><strong>Recorded evidence only · no live database reads or actions.</strong><span>This inspector reads a generated, allowlisted JSON receipt. It does not poll a database, control a robot, or initiate mission commands.</span></div>
    <div className="recorded-evidence-toolbar">
      <div className="recorded-run-meta"><span>Recorded run</span><strong>{data.scenario} · seed {data.seed} · {data.recorded_run_status}</strong><small>Manifest generated {data.manifest_generated_at_utc}</small></div>
      <div className="recorded-toggle" role="group" aria-label="Recorded snapshot selector">
        {data.stages.map((item,index)=><button type="button" key={`${item.stage}-${index}`} aria-pressed={index===stageIndex} onClick={()=>setStageIndex(index)} aria-label={`Show ${item.stage==='complete'?'final complete':item.stage} snapshot`}>{index===finalIndex?'Final · complete':item.stage==='courier_delivery'?'Courier delivery snapshot':item.stage}</button>)}
      </div>
    </div>
    <article className="recorded-snapshot" aria-live="polite">
      <div className="recorded-snapshot-header"><div><span className="recorded-eyebrow">{stage.stage==='complete'?'COMPLETE · FINAL RECORDED SNAPSHOT':`${stageLabel} · RECORDED SNAPSHOT`}</span><h3>{stage.stage==='complete'?'Final recorded state':'Recorded stage state'}</h3></div><span className="recorded-tick">Snapshot observed at world tick <strong>{stage.observation.world_tick}</strong></span></div>
      <div className="recorded-stats">
        <div><span>Graph version</span><strong>{stage.graph_version}</strong></div><div><span>Policy epoch</span><strong>{stage.policy_epoch}</strong></div><div><span>Tasks retained</span><strong>{stage.task_count}</strong></div><div><span>Commands retained</span><strong>{stage.command_count}</strong></div>
      </div>
      <div className="recorded-metrics" aria-label="Recorded mission metrics">
        <div><span>Delivery completed</span><strong className="recorded-metric-value">{numberLabel(stage.metrics.delivery_completed)}</strong></div>
        <div><span>Recovery verified</span><strong className="recorded-metric-value">{numberLabel(stage.metrics.recovery_verified)}</strong></div>
        <div><span>Unauthorized executed</span><strong className="recorded-metric-value">{numberLabel(stage.metrics.unauthorized_executed)}</strong>{stage.metrics.unauthorized_executed===null&&<small>Not recorded in retained evidence; null is unknown, not zero.</small>}</div>
      </div>
      <div className="recorded-data-grid">
        <section className="recorded-table-wrap" aria-labelledby="recorded-tasks-heading"><div className="recorded-table-title"><h4 id="recorded-tasks-heading">Task receipts</h4><span>{stage.tasks.length} retained tasks</span></div><div className="recorded-table-scroll" role="region" aria-label="Recorded task receipt table" tabIndex={0}><table><thead><tr><th>Task ID</th><th>Robot</th><th>Type</th><th>State</th></tr></thead><tbody>{stage.tasks.map(task=><tr key={task.task_id}><td><code>{task.task_id}</code></td><td>{task.robot_id}</td><td>{task.kind}</td><td><span className="recorded-state">{task.state}</span></td></tr>)}</tbody></table></div></section>
        <section className="recorded-commands" aria-labelledby="recorded-commands-heading"><div className="recorded-table-title"><h4 id="recorded-commands-heading">Command receipts</h4><span>{stage.commands.length} completed commands</span></div>{stage.commands.map(command=><details key={command.command_id} className="recorded-command"><summary><span className="recorded-command-type">{command.kind}</span><code>{command.command_id}</code><span className="recorded-command-state">{command.state}</span></summary><dl><div><dt>Task / robot</dt><dd><code>{command.task_id}</code> · {command.robot_id}</dd></div><div><dt>Command completion tick</dt><dd>{command.completed_world_tick}</dd></div><div><dt>Accepted / started ticks</dt><dd>{command.accepted_tick} / {command.started_tick}</dd></div><div><dt>Native receipt</dt><dd>{command.native_status}{command.phase?` · ${command.phase}`:''}</dd></div>{command.contact_count!==null&&<div><dt>Contact count</dt><dd>{numberLabel(command.contact_count)}</dd></div>}{command.max_contact_force_n!==null&&<div><dt>Max contact force</dt><dd>{command.max_contact_force_n.toFixed(2)} N</dd></div>}{command.measured_displacement_m!==null&&<div><dt>Measured displacement</dt><dd>{command.measured_displacement_m.toFixed(3)} m</dd></div>}</dl></details>)}{stage.commands.length===0&&<p className="recorded-empty">No command receipt is present at this recorded stage.</p>}</section>
      </div>
      <p className="recorded-time-note">Observation time is the snapshot tick above. Each command completion tick is shown separately; a later snapshot does not redefine when a command completed.</p>
    </article>
    <div className="recorded-proof-boundary"><strong>Pre-release behavior was separately verified by the pinned test contract.</strong><span>The retained capture begins at the post-release <code>courier_delivery</code> snapshot; it contains no pre-release snapshot. The <a href="https://github.com/guglxni/witness-fleet/blob/51e789daf75fff7f8bb29b84523679813449aa7d/tests/e2e/test_hosted_simulation.py" target="_blank" rel="noreferrer">pinned test contract</a> asserts the earlier <code>awaiting_owner_release</code> gate had 4 commands and 0 courier commands. That is contract evidence, not a stored capture.</span></div>
    <div className="recorded-provenance">
      <div><span className="recorded-eyebrow">EVIDENCE LEVEL</span><strong>Retained simulation capture + content hash</strong><small>Tasks and command/native receipts summarized from the retained manifest. Source-code hashes are recorded by that manifest, but not re-verified against current files.</small></div>
      <div><span className="recorded-eyebrow">SOURCE SHA256</span><code>{data.source.sha256}</code><small>Exact retained manifest bytes · {data.source.captured_source_file_hash_count} source-file hashes captured.</small></div>
      <div><span className="recorded-eyebrow">CAPTURED VERSIONS</span><span>{Object.entries(data.versions).map(([name,version])=><span className="recorded-version" key={name}><code>{name}</code> {version}</span>)}</span><small>Captured versions, not a claim about the current checkout or running system.</small></div>
    </div>
    <p className="recorded-contract-note">Tests and CI are contract evidence, not current live evidence. No present-tense database state, deployment, robot action, or current source revision is claimed here.</p>
  </section>;
}
