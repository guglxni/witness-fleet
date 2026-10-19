import { useState } from 'react';
import { ArrowDownRight } from 'lucide-react';

type Scenario = {
  key: string;
  title: string;
  setting: string;
  buyer: string;
  friction: string;
  trigger: string;
  evidence: string;
  response: string;
  metric: string;
  gap: string;
  image: string;
  alt: string;
};

const scenarios: Scenario[] = [
  {
    key: 'factory', title: 'Line-side delivery', setting: 'PRIMARY APPLICATION / FACTORY INTRALOGISTICS',
    buyer: 'Plant or intralogistics operations leader',
    friction: 'A tote or pallet run meets a blocked lane, ambiguous clearance or evidence that has gone stale. The courier waits while the shift keeps moving.',
    trigger: 'What observation cleared the obstruction, and who may release the courier to try again?',
    evidence: 'Task and authority reference · recovery command · fresh courier observation · delivery outcome',
    response: 'Hold for the configured release, then require a fresh route observation before the delivery attempt.',
    metric: 'Exception-to-diagnosis time; operator touch time; evidence completeness per eligible mission.',
    gap: 'No plant, robot, WMS/MES or customer integration is established. Map read-only event sources with an integrator first.',
    image: '/media/campaign/factory.webp', alt: 'Illustrative factory line-side material-flow concept art.'
  },
  {
    key: 'warehouse', title: 'Warehouse exception recovery', setting: 'ILLUSTRATIVE APPLICATION / WAREHOUSE FLOW',
    buyer: 'Warehouse operations or fulfillment integrator',
    friction: 'A replenishment or tote task cannot finish as assigned. The next operator needs to reconstruct which task failed, what was observed and whether a retry is appropriate.',
    trigger: 'Is the outcome known, and is the next command grounded in current evidence?',
    evidence: 'Mission and command identity · observation age · exception disposition · outcome receipt',
    response: 'Keep an unknown outcome on hold for review rather than infer completion or resend by default.',
    metric: 'Exception-to-diagnosis time; ambiguous outcomes; duplicate/retry attempts reviewed.',
    gap: 'Companion fit with existing fleet orchestration is a hypothesis. Vendor event coverage and access remain to validate.',
    image: '/media/campaign/warehouse.webp', alt: 'Illustrative warehouse replenishment and tote-flow concept art.'
  },
  {
    key: 'facility', title: 'Restricted-facility access', setting: 'ILLUSTRATIVE APPLICATION / CONTROLLED FACILITY',
    buyer: 'Facilities operations or site logistics owner',
    friction: 'A route crosses a changing access boundary. Old clearance can be mistaken for current authority unless the workflow makes its freshness and owner explicit.',
    trigger: 'Is the access evidence still current for this task and route?',
    evidence: 'Scoped task authority · access observation reference · configured owner release · resulting task receipt',
    response: 'Hold when the relevant access evidence is missing, stale or outside the configured scope.',
    metric: 'Stale-evidence holds; operator review time; traceable release records per sampled task.',
    gap: 'No facility access-control connector or inspection workflow is demonstrated. Privacy and site procedures need separate review.',
    image: '/media/campaign/hospital.webp', alt: 'Illustrative controlled-facility logistics concept art, not a customer site.'
  }
];

export function ProductApplications() {
  const [selected, setSelected] = useState(0);
  const item = scenarios[selected]!;
  return <section className="applications-section" id="applications" aria-labelledby="applications-title">
    <div className="applications-intro"><div className="app-index"><span>02</span><span>WHERE THE QUESTION SHOWS UP</span></div><div><p className="section-kicker"><span className="kicker-rule"/> ILLUSTRATIVE OPERATING CONTEXTS</p><h2 id="applications-title">Follow the exception,<br/><em>not the promise.</em></h2><p className="applications-summary">Three places to investigate the workflow question. These are applications to explore, not customer deployments.</p></div></div>
    <div className="application-explorer">
      <div className="application-selector" role="group" aria-label="Illustrative application scenarios">
        {scenarios.map((scenario, index) => <button type="button" key={scenario.key} className={`application-choice${selected === index ? ' is-selected' : ''}`} aria-pressed={selected === index} onClick={() => setSelected(index)}>
          <span className="application-choice-no">0{index + 1}</span><span className="application-choice-title">{scenario.title}</span><span className="application-choice-arrow" aria-hidden="true">↗</span>
        </button>)}
      </div>
      <article className="application-detail" aria-live="polite" aria-atomic="true">
        <div className="application-photo"><img key={item.key} src={item.image} alt={item.alt} loading="lazy" width="1000" height="760"/><span className="concept-label">ILLUSTRATIVE CONCEPT</span><span className="application-setting">{item.setting}</span></div>
        <div className="application-copy"><div className="application-title-row"><div><span className="application-live-label">ILLUSTRATIVE APPLICATION · NOT DEPLOYED</span><h3>{item.title}</h3></div><span className="application-number">0{selected + 1} / 03</span></div>
          <div className="application-facts"><div className="application-fact"><span>THE BUYER</span><p>{item.buyer}</p></div><div className="application-fact"><span>THE FRICTION</span><p>{item.friction}</p></div><div className="application-fact"><span>THE AUTHORITY QUESTION</span><p>{item.trigger}</p></div><div className="application-fact"><span>POSSIBLE HOLD / RESPONSE</span><p>{item.response}</p></div><div className="application-fact"><span>EVIDENCE TO MAP</span><p>{item.evidence}</p></div><div className="application-fact"><span>PILOT MEASURE TO AGREE</span><p>{item.metric}</p></div></div>
          <p className="integration-gap"><strong>Integration gap</strong>{item.gap}</p>
        </div>
      </article>
    </div>
    <a className="application-next" href="#evidence">Inspect the evidence path <ArrowDownRight size={15}/></a>
  </section>;
}
