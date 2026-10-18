import { ArrowDownRight, ArrowUpRight, BookOpen, Film, Play } from 'lucide-react';
import './judge-start.css';

const runtimeCommit = '51e789daf75fff7f8bb29b84523679813449aa7d';

export function JudgeStart({ demoUrl, sourceUrl }: { demoUrl: string; sourceUrl: string }) {
  const pinnedSource = `${sourceUrl.replace(/\/$/, '')}/blob/${runtimeCommit}/src/witness_fleet/graph/store.py`;

  return <section className="judge-start" id="judge" aria-labelledby="judge-title">
    <div className="judge-start-inner">
      <div className="judge-start-heading">
        <p className="section-kicker"><span className="kicker-rule"/> A PROOF-FIRST START</p>
        <h2 id="judge-title">Start here.<br/><em>Choose how to inspect.</em></h2>
        <p>Follow one deterministic mission, inspect its source-pinned graph runtime, or use the preserved recording. The simulation is separate from this explanatory page.</p>
      </div>

      <div className="judge-paths" aria-label="Three ways to inspect Witness Fleet">
        <a className="judge-path judge-path-primary" href={demoUrl} target="_blank" rel="noreferrer">
          <span className="judge-path-icon" aria-hidden="true"><Play size={17}/></span>
          <span><strong>Run bounded simulation</strong><small>Hosted demo · visitor-initiated · opens separately</small></span>
          <ArrowUpRight size={16} aria-hidden="true"/>
        </a>
        <a className="judge-path" href={pinnedSource} target="_blank" rel="noreferrer">
          <span className="judge-path-icon" aria-hidden="true"><BookOpen size={17}/></span>
          <span><strong>Inspect source-pinned graph code</strong><small>Runtime at commit {runtimeCommit.slice(0, 12)}</small></span>
          <ArrowUpRight size={16} aria-hidden="true"/>
        </a>
        <div className="judge-path judge-path-recorded">
          <span className="judge-path-icon" aria-hidden="true"><Film size={17}/></span>
          <span><strong>Recorded fallback</strong><small>Saved film and sanitized capture provenance</small><span className="judge-recorded-links"><a href="/media/launch.mp4">Watch or download film <ArrowUpRight size={12}/></a><a href="/media/provenance.json" aria-label="Inspect provenance — sanitized capture">Inspect provenance <ArrowUpRight size={12}/></a></span></span>
        </div>
      </div>

      <div className="judge-explainer">
        <div className="judge-loop">
          <p className="judge-label">STATIC EXPLANATION · NOT A LIVE REQUEST</p>
          <h3>What changes the next move?</h3>
          <ol aria-label="What changes the next move">
            <li><span>01</span><strong>Recovery</strong><small>A blocked route starts a bounded recovery task.</small></li>
            <li><span>02</span><strong>Restriction still gates</strong><small>Clearing the obstruction does not itself grant permission to travel.</small></li>
            <li><span>03</span><strong>Scoped configured release and fresh courier evidence are both required</strong><small>Approval evidence is collected during the configured release; execution separately obtains a fresh courier route observation.</small></li>
            <li><span>04</span><strong>Travel</strong><small>Travel is allowed only after the configured checks and fresh evidence.</small></li>
            <li><span>05</span><strong>Measured delivery</strong><small>Record the delivery outcome; a command receipt alone is not proof of completion.</small></li>
          </ol>
        </div>
        <div className="judge-runtime-summary">
          <p className="judge-label">THE RECORDED EXECUTION LOOP</p>
          <p>A deterministic mission runs centrally coordinated roles: recovery clears the obstruction, while the restriction still gates the courier. A scoped configured release—not human authentication—provides approval evidence, and fresh courier proof is separately required for travel, followed by measured delivery.</p>
          <p>No model inference is in the control path. This explanatory sequence is not a live request; it sends no mission request and shows no live graph or live output.</p>
          <details className="judge-look-for">
            <summary>What to look for <ArrowDownRight size={14} aria-hidden="true"/></summary>
            <ol>
              <li><strong>Recovery then hold:</strong> authorized recovery and verification finish while the courier remains held.</li>
              <li><strong>Release and fresh sensing:</strong> the synthetic configured demo-owner release carries scoped approval evidence, and execution separately requires a fresh courier observation.</li>
              <li><strong>Outcome:</strong> inspect the recorded task receipts for travel and delivery; the guide’s seven outcomes are not a live fleet status.</li>
            </ol>
            <p>Source: JUDGE_GUIDE · recorded SC-001 simulation. A configured owner identity is not proof of a human-authenticated approval.</p>
          </details>
        </div>
      </div>
    </div>
  </section>;
}
