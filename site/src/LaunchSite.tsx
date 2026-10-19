import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ArrowDownRight, ArrowRight, ArrowUpRight, Github, Pause, Play, ShieldCheck } from 'lucide-react';
import { FleetFigure } from './FleetFigure';
import { ANATOMY_PART_COUNT, STORY_PHASES, type StoryPhaseKey, useFleetAnatomy } from './fleetAnatomy';
import { StorySequence } from './StorySequence';
import { ProductFilmTheater } from './ProductFilmTheater';
import { ValueWorksheet } from './ValueWorksheet';
import { useSiteMotion } from './useSiteMotion';
import { ProductApplications } from './ProductApplications';
import { IndustryContext } from './IndustryContext';
import { ProductPathway } from './ProductPathway';
import { FalkorDBSection } from './FalkorDBSection';
import { JudgeStart } from './JudgeStart';
import { RecordedEvidence } from './RecordedEvidence';
import { SectionFinder } from './SectionFinder';
import { useSectionProgress } from './useSectionProgress';
import './style.css';
import './product.css';
import './integration.css';

const demoUrl = import.meta.env.VITE_DEMO_URL?.trim() || 'https://witness-fleet-guglxni.eastus.cloudapp.azure.com/demo';
const sourceUrl = import.meta.env.VITE_GITHUB_URL?.trim() || 'https://github.com/guglxni/witness-fleet';
const phases: StoryPhaseKey[] = STORY_PHASES.map(item => item.key);

export function LaunchSite() {
  const [stage, setStage] = useState(0);
  const [paused, setPaused] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 1180px)').matches);
  const menuToggle = useRef<HTMLButtonElement>(null);
  const {activeSection,progressRef} = useSectionProgress();
  const anatomy = useFleetAnatomy();
  useSiteMotion(paused);
  const active = STORY_PHASES[stage]!;
  const goTo = (index: number) => setStage((index + phases.length) % phases.length);
  const changeStage = useCallback((key: StoryPhaseKey) => {
    const index = phases.indexOf(key);
    if (index >= 0) goTo(index);
  }, []);
  const closeMobile = (event?: React.MouseEvent<HTMLAnchorElement>) => {
    setMobileOpen(false);
    const href=event?.currentTarget.getAttribute('href');
    if(isMobile&&href?.startsWith('#')){const target=document.querySelector<HTMLElement>(href);if(target){target.tabIndex=-1;requestAnimationFrame(()=>target.focus({preventScroll:true}));}}
  };
  const toggleMotion = () => setPaused(current => !current);
  const toggleNavigation = () => {
    if (!mobileOpen && isMobile) setTimeout(() => document.querySelector<HTMLAnchorElement>('#primary-links a')?.focus(), 0);
    setMobileOpen(open => !open);
  };

  useEffect(() => {
    const media = window.matchMedia('(max-width: 1180px)');
    const update = () => setIsMobile(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    if (!isMobile && mobileOpen) setMobileOpen(false);
  }, [isMobile, mobileOpen]);
  useLayoutEffect(() => {
    if (mobileOpen && isMobile) document.querySelector<HTMLAnchorElement>('#primary-links a')?.focus();
  }, [mobileOpen, isMobile]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && mobileOpen) {
        setMobileOpen(false);
        menuToggle.current?.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [mobileOpen]);

  return <div className={`site-shell wf-site${paused ? ' motion-paused' : ''}`} id="top">
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="site-header wf-header">
      <div ref={progressRef} className="reading-progress" aria-hidden="true"/>
      <a className="wordmark" href="#top" onClick={closeMobile} aria-label="Witness Fleet home">
        <span className="wordmark-emblem" aria-hidden="true"><span/><span/><span/></span>
        <span>WITNESS<span className="wordmark-sep">/</span>FLEET</span>
      </a>
      <nav id="primary-links" hidden={isMobile && !mobileOpen} className={`primary-nav wf-nav${mobileOpen ? ' is-open' : ''}`} aria-label="Primary navigation">
        <a href="#judge" aria-current={activeSection === 'judge' ? 'location' : undefined} onClick={closeMobile}>Start here</a>
        <a href="#applications" aria-current={activeSection === 'applications' ? 'location' : undefined} onClick={closeMobile}>Applications</a>
        <a href="#falkordb" aria-current={activeSection === 'falkordb' ? 'location' : undefined} onClick={closeMobile}>FalkorDB</a>
        <a href="#evidence" aria-current={activeSection === 'evidence' ? 'location' : undefined} onClick={closeMobile}>Evidence</a>
        <a href="#film" aria-current={activeSection === 'film' ? 'location' : undefined} onClick={closeMobile}>Product film</a>
        <a href="#pilot" aria-current={activeSection === 'pilot' ? 'location' : undefined} onClick={closeMobile}>Pilot path</a>
        <a className="nav-source" href={sourceUrl} target="_blank" rel="noreferrer" aria-label="View source on GitHub">Source <Github size={14}/><ArrowUpRight size={12}/></a>
      </nav>
      <div className="header-actions wf-header-actions">
        <SectionFinder/>
        <button className="motion-switch wf-motion" type="button" aria-label={paused ? 'Resume ambient motion' : 'Pause ambient motion'} aria-pressed={paused} onClick={toggleMotion}>
          {paused ? <Play size={14}/> : <Pause size={14}/>}<span>{paused ? 'Resume ambient motion' : 'Pause ambient motion'}</span>
        </button>
        <a className="header-demo wf-demo" href={demoUrl} target="_blank" rel="noreferrer" aria-label="Open simulation — hosted demo (external)">Open simulation <ArrowUpRight size={14}/></a>
        <button ref={menuToggle} type="button" className="menu-toggle wf-menu-toggle" aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'} aria-expanded={mobileOpen} aria-controls="primary-links" onClick={toggleNavigation}><span aria-hidden="true">{mobileOpen ? '×' : 'Menu'}</span></button>
      </div>
    </header>

    <main id="main">
      <section className="hero wf-hero" aria-labelledby="hero-title">
        <div className="vanta-surface" aria-hidden="true"/>
        <div className="hero-inner wf-hero-inner">
          <div className="hero-copy wf-hero-copy">
            <p className="hero-overline"><span className="prototype-mark"/> RESEARCH PROTOTYPE <span className="overline-divider">/</span> MUJOCO SIMULATION</p>
            <h1 id="hero-title">When robots stop,<br/><em>business shouldn't</em><br/>lose the plot.</h1>
            <p className="hero-lede">A graph-backed coordination layer and an evidence layer for robot-fleet exceptions: know what happened, who can release the next move, and whether the job was completed.</p>
            <div className="hero-actions wf-hero-actions">
              <a className="button button-primary" href={demoUrl} target="_blank" rel="noreferrer">Run the simulation <ArrowUpRight size={16}/></a>
              <a className="button button-secondary" href="#judge">Inspect the evidence <ArrowDownRight size={16}/></a>
              <a className="hero-film-link" href="#film"><span className="play-mark" aria-hidden="true">▶</span> Watch product film</a>
            </div>
            <div className="hero-footnote"><ShieldCheck size={16}/><span>Simulation-built research prototype. Not deployed on physical robots.</span></div>
            <a className="fdb-hero-badge" href="#falkordb"><span className="fdb-hero-logo"><img src="/media/falkordb/falkordb-logo-color.svg" alt="FalkorDB" width="106" height="28"/></span><span><strong>BUILT WITH FALKORDB</strong><small>Operational property graph · inspect the implementation ↓</small></span></a>
          </div>
          <div className="hero-visual" aria-label="Illustrative concept art and mechanism drawing">
            <div className="hero-visual-sky" aria-hidden="true"/>
            <div className="hero-art-plane hero-art-background" aria-hidden="true"><img src="/media/campaign/hero.webp" srcSet="/media/campaign/hero-960.webp 960w, /media/campaign/hero.webp 1600w" sizes="(max-width: 1180px) 640px, 900px" alt="" fetchPriority="high" width="1536" height="1024"/></div>
            <div className="hero-visual-index"><span>STUDY 01</span><span>EXCEPTION / RESPONSE</span></div>
              <div className="hero-visual-stamp" aria-hidden="true"><span>PROOF</span><b>≠</b><span>ASSUMPTION</span></div>
            <p className="illustration-note">Concept art · mechanism is an explanatory illustration, not telemetry</p>
          </div>
        </div>
        <div className="hero-baseline"><span>EXCEPTION ACCOUNTABILITY FOR AMR OPERATIONS</span><span>AUTHORITY <i>×</i> EVIDENCE <i>×</i> OUTCOME</span></div>
      </section>

      <JudgeStart demoUrl={demoUrl} sourceUrl={sourceUrl}/>

      <section className="operational-story" id="principle" aria-labelledby="principle-title">
        <div className="story-index"><span>01</span><span>THE OPERATIONAL QUESTION</span><span className="index-rule"/></div>
        <div className="story-main">
          <p className="story-annotation">ONE BLOCKED RUN IS NEVER ONLY ONE BLOCKED RUN.</p>
          <h2 id="principle-title">A route goes quiet.<br/><em>The shift keeps moving.</em></h2>
          <div className="story-lower"><p>A line-side delivery waits at an obstruction. A recovery task begins. The courier is ready to go, but a clear path is not the same as permission.</p><p>Now someone has to reconstruct the decision: what was observed, what was allowed, who released it, and did the delivery finish?</p></div>
        </div>
        <div className="story-visual" aria-label="Illustrative sequence of an exception, not a customer event">
          <div className="story-image"><img src="/media/campaign/factory.webp" alt="" loading="lazy" width="1000" height="760"/><span className="concept-label">ILLUSTRATIVE APPLICATION</span></div>
          <div className="story-caption"><span>LINE-SIDE DELIVERY / EXCEPTION STUDY</span><span>01—04</span></div>
          <div className="story-sequence" data-motion="progress" aria-label="Illustrative exception sequence"><span>BLOCKED</span><i/><span>RECOVERY</span><i/><span>RELEASE?</span><i/><span>DELIVERY</span></div>
        </div>
      </section>

      <FalkorDBSection/>

      <section className="evidence-section" id="evidence" aria-labelledby="evidence-title">
        <div className="section-heading evidence-heading">
          <div><p className="section-kicker"><span className="kicker-rule"/> A RECORDED SIMULATION PATH</p><h2 id="evidence-title">Five phases.<br/><em>One inspectable chain.</em></h2></div>
          <p>Each phase is tied to its own source of truth. Select a stage to inspect the question, source, evidence and hold boundary. This changes the explanation, never a mission.</p>
        </div>
        <div className="evidence-stage-figure"><FleetFigure geometry={anatomy} phaseIndex={stage} paused={paused} onPhase={goTo}/></div>
        <StorySequence phase={active.key} onPhase={changeStage} paused={paused}/>
        <div className="evidence-limits">
          <div className="limit-statement"><span className="limit-symbol" aria-hidden="true">≠</span><div><span className="section-kicker">SHOWN / NOT ESTABLISHED</span><p>The SC-001 recorded MuJoCo path and mission-controller task outcomes are demonstrated. FalkorDB holds the connected operational record; the application evaluates its evidence before allowing or holding an action. Physical deployment, human-authenticated approval, production readiness, certification and customer results are not established. A null value for unauthorized execution is unknown, not a measured zero.</p></div></div>
        </div>
      </section>
      <RecordedEvidence/>

      <ProductFilmTheater/>
      <section className="capture-record" aria-label="Capture provenance">
        <details className="provenance-panel"><summary><span>CAPTURE PROVENANCE</span><span>SC-001 / RECORDED 17 OCT 2026</span><span aria-hidden="true">＋</span></summary><div className="provenance-grid"><div><span>CAPTURE</span><strong>SC-001 · 17 October 2026</strong></div><div><span>ENVIRONMENT</span><strong>MuJoCo simulation only</strong></div><div><span>RECORDED TASKS</span><strong>7 outcomes · all verified</strong></div><div><span>OWNER AUTHENTICATION</span><strong>No · configured demo identity</strong></div><div className="provenance-hash"><span>NATIVE VIDEO SHA-256</span><code>eb6d492ecba72f2323db5bda78d1fa9abb92eb2d6625f47a55fa05769ca7f9c6</code></div><div className="provenance-hash"><span>CAPTURE SCRIPT SHA-256</span><code>377f3327ef2fd4d3fcbb6eb072d71cae56ccdf7e8afd391d28bf2cefe9c90269</code></div></div></details>
      </section>
      <ProductApplications/>
      <IndustryContext/>
      <div id="value-model"><ValueWorksheet/></div>

      <ProductPathway sourceUrl={sourceUrl}/>

      <section className="faq-section" id="faq" aria-labelledby="faq-title"><div className="faq-heading"><p className="section-kicker"><span className="kicker-rule"/> WHAT THE RECORD DOES NOT SAY</p><h2 id="faq-title">Fair questions,<br/><em>careful answers.</em></h2><p>Research prototype · simulation evidence · integration and pricing remain to be validated.</p></div><div className="faq-list">
        <details><summary>Is Witness Fleet running on physical robots? <span>＋</span></summary><p>No. The current proof is a recorded, simulation-built MuJoCo research demonstration; the capture does not establish physical deployment.</p></details>
        <details><summary>Was a person approving each action? <span>＋</span></summary><p>The configured release in this capture is scripted and is not a human-authenticated approval. Permission scope, model intent and recorded outcome are separate things.</p></details>
        <details><summary>Does Witness Fleet replace a fleet manager or safety controller? <span>＋</span></summary><p>No replacement is established. The proposed role is a companion evidence layer for exceptions; any connection to incumbent fleet, WMS/MES or site systems needs validation. It is not a safety-rated controller.</p></details>
        <details><summary>What does the demonstration prove? <span>＋</span></summary><p>Seven recorded simulation task outcomes are marked verified in SC-001, including recovery and delivery. The capture does not establish production operation, certification, customer results or an absence of unauthorized outcomes. That last field is null, meaning unknown.</p></details>
        <details><summary>Is there established pricing or a guaranteed return? <span>＋</span></summary><p>No. A paid scoped evaluation followed, if useful, by a per-site software subscription and integration support is a proposed model. Pricing, demand, savings and ROI have not been established.</p></details>
      </div></section>

      <section className="closing-section" aria-labelledby="closing-title"><div className="closing-engraving" aria-hidden="true"><span>HOLD</span><i>—</i><span>INSPECT</span><i>—</i><span>RELEASE</span></div><p className="section-kicker">BEGIN WITH ONE WORKFLOW</p><h2 id="closing-title">Make the next move<br/><em>easier to account for.</em></h2><p>A proposed, bounded evaluation starts with a workflow, a baseline and the evidence sources an operator can inspect. No physical pilot is offered or claimed.</p><div className="closing-actions"><a className="button button-light" href={demoUrl} target="_blank" rel="noreferrer">Open hosted simulation <ArrowUpRight size={15}/></a><a className="closing-source" href={sourceUrl} target="_blank" rel="noreferrer">Review the source <ArrowRight size={14}/></a></div><a className="draft-link" href="mailto:guglaniaaryan@gmail.com?subject=Witness%20Fleet%20%E2%80%94%20scoped%20workflow%20evaluation&body=I%27d%20like%20to%20discuss%20a%20bounded%20workflow%20evaluation.%0A%0AWorkflow%3A%0AFacility%3A%0AQuestions%3A" aria-label="Opens an email draft">Opens an email draft <ArrowUpRight size={12}/></a><span className="recipient-note">Draft addressed to Aaryan · nothing is sent until you choose to send it.</span></section>
    </main>

    <footer className="site-footer wf-footer"><a className="wordmark" href="#top" aria-label="Witness Fleet, back to top"><span className="wordmark-emblem" aria-hidden="true"><span/><span/><span/></span><span>WITNESS<span className="wordmark-sep">/</span>FLEET</span></a><p>Evidence before motion. Outcomes before claims.</p><a className="footer-source" href={sourceUrl} target="_blank" rel="noreferrer">SOURCE REPOSITORY <Github size={13}/><ArrowUpRight size={12}/></a><span className="footer-copy">RESEARCH PROTOTYPE · SIMULATION-BUILT · NOT FOR PRODUCTION USE</span><span className="footer-statement">A research demonstration. No customers, physical deployments, certification, pricing or product savings are claimed. FalkorDB is the graph store, not a safety controller.</span></footer>
    <div className="sr-only" aria-live="polite">{paused ? 'Ambient motion paused.' : 'Ambient motion enabled.'}</div><span className="sr-only">The figure contains {ANATOMY_PART_COUNT} individually illustrated solid parts.</span>
  </div>;
}
