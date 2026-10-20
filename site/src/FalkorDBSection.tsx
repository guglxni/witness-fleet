import { useState } from 'react';
import './falkordb-section.css';

const sourceRoot = 'https://github.com/guglxni/witness-fleet/blob/51e789daf75fff7f8bb29b84523679813449aa7d/';

const capabilities = [
  {id:'graph',label:'Property graph',eyebrow:'01 / CONNECTED RECORD',title:'A decision has branches, not just a log line.',body:'Typed nodes connect a Decision to its Restriction, accountable Owner and exact EvidenceSpan. The span points to an immutable Revision and Source. A Release can lift the restriction and identify its approving owner.',codeLabel:'CANONICAL RELATIONSHIPS',code:'Decision -[:IMPOSES]-> Restriction -[:APPLIES_TO]-> Corridor\nDecision -[:OWNED_BY]-> Owner\nDecision -[:SUPPORTED_BY]-> EvidenceSpan\nEvidenceSpan -[:IN_REVISION]-> Revision -[:REVISION_OF]-> Source\nRelease -[:LIFTS]-> Restriction',source:'src/witness_fleet/graph/store.py#L48-L96',sourceLabel:'store.py · canonical graph schema',sourceHint:'Typed-node and relationship allowlists'},
  {id:'reads',label:'Cypher reads',eyebrow:'02 / OPERATOR INSPECTION',title:'Read the claim attached to a task.',body:'Parameterized Cypher reads expose which retained claim owns a task. The store sends reads through FalkorDB’s read-only ro_query path; identifiers and tenant scope are bound parameters.',codeLabel:'READ · READ-ONLY CLIENT PATH',code:'MATCH (c:Claim)-[:CLAIMS_TASK]->\n      (t:Task {id:$task_id,tenant_id:$tenant_id})\nRETURN properties(c) AS claim',source:'src/witness_fleet/graph/store.py#L551-L556',sourceLabel:'store.py · read_task_claims',sourceHint:'Query text; ro_query routing in _query at L159-L161'},
  {id:'fencing',label:'Version-fenced writes',eyebrow:'03 / STALE-WRITE REJECTION',title:'The app checks the version before its graph write.',body:'A conditional graph mutation matches the expected FleetState graph_version, then advances it with the update. A lost compare-and-set returns no result. This is application logic in a single graph query, not a multi-query or robot-side transaction.',codeLabel:'WRITE · CONDITIONAL GRAPH MUTATION',code:"MATCH (s:FleetState {id:'fleet', tenant_id:$tenant_id})\nWHERE s.graph_version=$expected_version\n...\nSET n += $attributes, s.graph_version=s.graph_version+1",source:'src/witness_fleet/graph/store.py#L298-L379',sourceLabel:'store.py · atomic_update',sourceHint:'Expected-version predicate and one conditional graph query'},
  {id:'fleet',label:'Shared fleet context',eyebrow:'04 / TASK + RESOURCE CLAIMS',title:'Tasks, robots and shared resources meet in one tenant graph.',body:'The application selects a named wf:{tenant}:ops graph. Task claims link a Claim to a Task and Robot and reserve required Resources, so contention can be inspected in shared fleet context. Tenant predicates are application scoping, not a substitute for database ACLs.',codeLabel:'READ · RESOURCE RESERVATIONS',code:'MATCH (c:Claim)-[:RESERVES]->\n      (r:Resource {id:$resource_id,tenant_id:$tenant_id})\nRETURN properties(c) AS claim',source:'src/witness_fleet/graph/store.py#L558-L563',sourceLabel:'store.py · read_resource_claims',sourceHint:'Read-only reservation query; conditional claim_task write at L381-L443'},
] as const;

type SchemaNode={id:string;label:string;kind:string;description:string;source:string};
type SchemaEdge={id:string;from:string;to:string;verb:string;meaning:string;source:string};
const nodes:SchemaNode[]=[
  {id:'Decision',label:'Decision',kind:'POLICY EVENT',description:'A typed policy evaluation record that can be connected to its restrictions, owner and supporting evidence.',source:'src/witness_fleet/graph/store.py#L48-L96'},
  {id:'Restriction',label:'Restriction',kind:'HOLD BOUNDARY',description:'A restriction imposed by a decision and associated with an operational corridor.',source:'src/witness_fleet/graph/store.py#L48-L96'},
  {id:'Corridor',label:'Corridor',kind:'OPERATIONAL SCOPE',description:'The corridor to which a restriction applies.',source:'src/witness_fleet/graph/store.py#L48-L96'},
  {id:'Owner',label:'Owner',kind:'ACCOUNTABILITY',description:'An accountable owner associated with a decision; releases can also identify an approving owner.',source:'src/witness_fleet/graph/store.py#L48-L96'},
  {id:'EvidenceSpan',label:'EvidenceSpan',kind:'SOURCE-BACKED SUPPORT',description:'The exact span of evidence supporting a decision, linked onward to a revision and its source.',source:'src/witness_fleet/graph/store.py#L48-L96'},
  {id:'Revision',label:'Revision',kind:'IMMUTABLE REVISION',description:'A specific source revision that contains the evidence span.',source:'src/witness_fleet/graph/store.py#L48-L96'},
  {id:'Source',label:'Source',kind:'SOURCE RECORD',description:'The source record to which a revision belongs.',source:'src/witness_fleet/graph/store.py#L48-L96'},
  {id:'Release',label:'Release',kind:'RELEASE EVENT',description:'A release event that lifts a restriction and identifies an approving owner.',source:'src/witness_fleet/graph/store.py#L48-L96'},
];
const edges:SchemaEdge[]=[
  {id:'IMPOSES',from:'Decision',to:'Restriction',verb:'IMPOSES',meaning:'Decision → Restriction. The decision imposes the restriction.',source:'src/witness_fleet/graph/store.py#L48-L96'},
  {id:'APPLIES_TO',from:'Restriction',to:'Corridor',verb:'APPLIES_TO',meaning:'Restriction → Corridor. The restriction applies to the corridor.',source:'src/witness_fleet/graph/store.py#L48-L96'},
  {id:'OWNED_BY',from:'Decision',to:'Owner',verb:'OWNED_BY',meaning:'Decision → Owner. The decision names its accountable owner.',source:'src/witness_fleet/graph/store.py#L48-L96'},
  {id:'SUPPORTED_BY',from:'Decision',to:'EvidenceSpan',verb:'SUPPORTED_BY',meaning:'Decision → EvidenceSpan. The decision is supported by the exact evidence span.',source:'src/witness_fleet/graph/store.py#L48-L96'},
  {id:'IN_REVISION',from:'EvidenceSpan',to:'Revision',verb:'IN_REVISION',meaning:'EvidenceSpan → Revision. The evidence span is contained in a specific revision.',source:'src/witness_fleet/graph/store.py#L48-L96'},
  {id:'REVISION_OF',from:'Revision',to:'Source',verb:'REVISION_OF',meaning:'Revision → Source. The revision belongs to its source record.',source:'src/witness_fleet/graph/store.py#L48-L96'},
  {id:'LIFTS',from:'Release',to:'Restriction',verb:'LIFTS',meaning:'Release → Restriction. The release lifts the restriction.',source:'src/witness_fleet/graph/store.py#L48-L96'},
  {id:'APPROVED_BY',from:'Release',to:'Owner',verb:'APPROVED_BY',meaning:'Release → Owner. The release identifies the approving owner.',source:'src/witness_fleet/graph/store.py#L48-L96'},
];

function BranchingGraph(){
  const [selected,setSelected]=useState<{type:'node'|'edge';id:string}>({type:'node',id:'Decision'});
  const [wrap,setWrap]=useState(false);
  const [copyStatus,setCopyStatus]=useState('');
  const edge=selected.type==='edge'?edges.find(item=>item.id===selected.id):undefined;
  const node=selected.type==='node'?nodes.find(item=>item.id===selected.id):undefined;
  const detailsSource=edge?.source??node?.source??nodes[0]!.source;
  const fullSource=`${sourceRoot}${detailsSource}`;
  const code=capabilities.find(item=>item.id==='graph')!.code;
  async function copyCode(){try{await navigator.clipboard.writeText(code);setCopyStatus('Copied schema excerpt');}catch{setCopyStatus('Copy unavailable; select code to copy');}}
  return <div className="fdb-workbench">
    <div className="fdb-workbench-top"><div><span className="fdb-eyebrow">SCHEMA EXPLORER / APPLICATION GRAPH</span><h3>Follow the evidence path.</h3><p>Choose a node or a directed relationship to inspect its meaning and pinned source.</p></div><span className="fdb-live-badge">SCHEMA ONLY <i/> NOT LIVE</span></div>
    <div className="fdb-schema-grid">
      <div className="fdb-graph-column"><div className="fdb-graph-heading"><span>PROPERTY GRAPH / SCHEMA</span><span>{nodes.length} NODE TYPES · {edges.length} RELATIONSHIPS</span></div>
        <SchemaDiagram selected={selected} onSelect={setSelected}/>
        <div className="fdb-legend"><span><i className="fdb-legend-node"/> Node label</span><span><i className="fdb-legend-edge"/> Selectable directed relationship</span><span>Keyboard: Tab, Enter or Space</span></div>
      </div>
      <aside className="fdb-schema-detail" aria-label="Selected schema detail" aria-live="polite"><div className="fdb-detail-top"><span className="fdb-eyebrow">{edge?'RELATIONSHIP / DIRECTED EDGE':'NODE TYPE / SCHEMA'}</span><span>01 / 01</span></div>{edge?<><h4>{edge.verb}</h4><div className="fdb-edge-direction"><span>{edge.from}</span><i aria-hidden="true">→</i><span>{edge.to}</span></div><p>{edge.meaning}</p><dl><div><dt>Directed pattern</dt><dd><code>({edge.from})-[:{edge.verb}]-&gt;({edge.to})</code></dd></div><div><dt>Semantics</dt><dd>{edge.meaning.replace(`${edge.from} → ${edge.to}. `,'')}</dd></div></dl></>:<><h4>{node?.label}</h4><span className="fdb-node-kind">{node?.kind}</span><p>{node?.description}</p><dl><div><dt>Node label</dt><dd><code>:{node?.label}</code></dd></div><div><dt>Graph role</dt><dd>{node?.kind}</dd></div></dl></>}<a className="fdb-detail-source" href={fullSource} target="_blank" rel="noreferrer">View pinned schema source <span aria-hidden="true">↗</span></a></aside>
    </div>
    <details className="fdb-code-explorer"><summary><h4>Schema excerpt</h4><span>Optional source notation</span></summary><div className="fdb-code-explorer-head"><div><span className="fdb-eyebrow">SOURCE-PINNED QUERY / LOCAL INSPECTION</span></div><div className="fdb-code-actions"><button type="button" onClick={copyCode}>Copy excerpt</button><button type="button" aria-pressed={wrap} onClick={()=>setWrap(value=>!value)}>{wrap?'Disable wrap':'Wrap lines'}</button><span className="fdb-copy-status" role="status" aria-live="polite">{copyStatus}</span></div></div><div className={`fdb-code-window ${wrap?'is-wrapped':''}`} tabIndex={0} aria-label="Scrollable schema code excerpt"><pre><code>{code}</code></pre></div><p className="fdb-code-note">Explanatory excerpt only. No query executes from this page. <a href={`${sourceRoot}src/witness_fleet/graph/store.py#L48-L96`} target="_blank" rel="noreferrer">Source lines 48–96 ↗</a></p></details>
  </div>;
}
type Selection={type:'node'|'edge';id:string};
type DiagramProps={selected:Selection;onSelect:(next:Selection)=>void};
const positions:Record<string,[number,number]>={Decision:[30,110],Restriction:[430,110],Corridor:[830,110],Owner:[430,310],Release:[830,310],EvidenceSpan:[30,510],Revision:[430,510],Source:[830,510]};
const routes:Record<string,{path:string;label:[number,number]}>= {
  IMPOSES:{path:'M210 148 H430',label:[320,148]},
  APPLIES_TO:{path:'M610 148 H830',label:[720,148]},
  OWNED_BY:{path:'M210 148 H315 V348 H430',label:[315,248]},
  SUPPORTED_BY:{path:'M120 186 V510',label:[120,348]},
  IN_REVISION:{path:'M210 548 H430',label:[320,548]},
  REVISION_OF:{path:'M610 548 H830',label:[720,548]},
  LIFTS:{path:'M920 310 V245 H520 V186',label:[740,245]},
  APPROVED_BY:{path:'M830 348 H610',label:[720,348]},
};
const shortKinds:Record<string,string>={Decision:'Policy event',Restriction:'Hold boundary',Corridor:'Scope',Owner:'Accountability',EvidenceSpan:'Evidence',Revision:'Immutable record',Source:'Provenance',Release:'Release event'};
function SchemaDiagram({selected,onSelect}:DiagramProps){
  return <div className="fdb-diagram-region" role="region" aria-label="Scrollable canonical schema diagram" tabIndex={0}>
    <svg className="fdb-diagram-desktop" viewBox="0 0 1040 640" role="group" aria-label="Canonical FalkorDB schema diagram">
      <desc>Eight schema node types joined by eight directed relationships. Decision imposes Restriction, which applies to Corridor. Decision is owned by Owner and supported by EvidenceSpan. EvidenceSpan is in Revision, which is a revision of Source. Release lifts Restriction and is approved by Owner. Explanatory schema subset, not live database records.</desc>
      <defs><marker id="fdb-schema-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M1 1 L9 5 L1 9 Z"/></marker></defs>
      <text className="fdb-diagram-lane" x="30" y="55">POLICY / HOLD + RELEASE</text>
      <text className="fdb-diagram-lane" x="30" y="470">EVIDENCE / IMMUTABLE PROVENANCE</text>
      {edges.map(edge=><path key={edge.id} className={`fdb-diagram-connector ${selected.type==='edge'&&selected.id===edge.id?'is-selected':''}`} data-edge-id={edge.id} data-from={edge.from} data-to={edge.to} d={routes[edge.id]!.path} markerEnd="url(#fdb-schema-arrow)"/>)}
      {nodes.map(node=>{const [x,y]=positions[node.id]!;return <foreignObject key={node.id} x={x} y={y} width="180" height="76" data-node-id={node.id}><button type="button" className={`fdb-schema-node ${selected.type==='node'&&selected.id===node.id?'is-selected':''}`} aria-pressed={selected.type==='node'&&selected.id===node.id} onClick={()=>onSelect({type:'node',id:node.id})}><small>{shortKinds[node.id]}</small>{' '}<strong>{node.label}</strong></button></foreignObject>;})}
      {edges.map(edge=>{const [x,y]=routes[edge.id]!.label;return <foreignObject key={edge.id} x={x-88} y={y-32} width="176" height="64"><button type="button" className={`fdb-schema-edge ${selected.type==='edge'&&selected.id===edge.id?'is-selected':''}`} aria-label={`${edge.verb} relationship ${edge.from} to ${edge.to}`} aria-pressed={selected.type==='edge'&&selected.id===edge.id} onClick={()=>onSelect({type:'edge',id:edge.id})}><span>{edge.verb}</span></button></foreignObject>;})}
    </svg>
    <p className="fdb-diagram-caption">Directed schema subset · arrows point from the subject to its related record. Scroll sideways on smaller screens; Tab selects each node and relationship.</p>
  </div>;
}

export function FalkorDBSection(){
  const [selected,setSelected]=useState<(typeof capabilities)[number]['id']>('graph');
  const current=capabilities.find(item=>item.id===selected)!;
  return <section className="fdb-section" id="falkordb" aria-labelledby="fdb-title"><div className="fdb-inner">
    <div className="fdb-intro"><div><p className="section-kicker"><span className="kicker-rule"/> IMPLEMENTATION, NOT A LOGO DROP</p><h2 id="fdb-title">Why FalkorDB is in <br/><em>the execution path.</em></h2></div><p>Witness Fleet uses FalkorDB as the application’s operational property graph: connected fleet state and source-backed evidence are read to decide whether work can proceed or must hold.</p></div>
    <div className="fdb-selector" role="group" aria-label="FalkorDB capabilities">{capabilities.map((item,index)=><button key={item.id} type="button" aria-pressed={selected===item.id} onClick={()=>setSelected(item.id)}><span className="fdb-choice-number">0{index+1}</span><span>{item.label}</span><span aria-hidden="true" className="fdb-choice-mark">{selected===item.id?'↗':'＋'}</span></button>)}</div>
    <div className={`fdb-capability ${selected==='graph'?'is-schema':''}`}><div className="fdb-capability-copy"><span className="fdb-eyebrow">{current.eyebrow}</span><h3>{current.title}</h3><p>{current.body}</p><a className="fdb-source" href={`${sourceRoot}${current.source}`} target="_blank" rel="noreferrer"><span>{current.sourceLabel}</span><span aria-hidden="true">↗</span></a><small className="fdb-source-hint">{current.sourceHint}</small></div>{selected==='graph'?<BranchingGraph/>:<div className="fdb-code-panel"><div className="fdb-code-header"><span>{current.codeLabel}</span><span>{selected==='fencing'?'APP CONDITIONAL WRITE':selected==='reads'||selected==='fleet'?'APP READ PATH · ro_query':'APPLICATION SCHEMA'}</span></div><pre tabIndex={0} aria-label={`${current.codeLabel} source excerpt`}><code>{current.code}</code></pre><p className="fdb-code-note">Explanatory view only. Read excerpts use FalkorDB ro_query; no query runs from this page.</p></div>}</div>
    {selected!=='graph'&&<BranchingGraph/>}
    <div className="fdb-boundaries"><div><span className="fdb-boundary-label">USED IN THE APPLICATION</span><p>FalkorDB client, named per-tenant ops graphs, read-only Cypher reads, typed nodes/relationships, version-checked single-query writes, and per-label unique-id constraints with supporting range indexes.</p><a href={`${sourceRoot}src/witness_fleet/graph/migrations.py#L21-L60`} target="_blank" rel="noreferrer">migrations.py · schema constraints ↗</a></div><div><span className="fdb-boundary-label">PLATFORM CAPABILITY ≠ PRODUCT CLAIM</span><p>Vector and full-text indexes and graph algorithms are broader FalkorDB platform capabilities, not features claimed in this captured allow/hold path. FalkorDB’s sparse-matrix/GraphBLAS engine underlies the database; no project latency benchmark is claimed. The separate GraphRAG-SDK adapter is an isolated synthetic corpus lane, not a source of authority and not part of the recorded mission.</p><a href={`${sourceRoot}services/corpus/sdk_adapter.py#L21-L73`} target="_blank" rel="noreferrer">sdk_adapter.py · isolated corpus lane ↗</a><a className="fdb-platform-source" href="https://docs.falkordb.com/" target="_blank" rel="noreferrer">FalkorDB platform documentation ↗</a></div></div>
    <p className="fdb-safety-note">FalkorDB stores connected evidence; Witness Fleet application code validates authority and enforces the hold boundary. This simulation research prototype is not a robot safety controller, and no physical deployment is claimed.</p>
  </div></section>;
}
