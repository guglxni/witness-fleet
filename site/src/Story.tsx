import { useEffect, useRef } from 'react';
import { STORY_PHASES, type StoryPhaseKey } from './fleetAnatomy';
import { Play, Radio } from 'lucide-react';

const requestedFilm=import.meta.env.VITE_FILM_URL?.trim();
export const DEFAULT_FILM_URL='/media/launch.mp4';

export function NativeFilm({onNearView}:{onNearView:()=>void}) {
  const ref=useRef<HTMLVideoElement>(null);
  useEffect(()=>{
    const video=ref.current;
    if(!video)return;
    const observer=new IntersectionObserver(entries=>{
      const latest=entries[entries.length-1];
      if(!latest?.isIntersecting){video.pause();return;}
      onNearView();
    },{rootMargin:'300px'});
    observer.observe(video);
    const onVisibility=()=>{if(document.hidden)video.pause();};
    document.addEventListener('visibilitychange',onVisibility);
    return()=>{observer.disconnect();document.removeEventListener('visibilitychange',onVisibility);video.pause();};
  },[onNearView]);
  return <video ref={ref} className="launch-video" controls playsInline muted preload="none" poster="/media/launch-poster.svg" aria-label="Silent native MuJoCo simulation replay">
    <source src={requestedFilm||DEFAULT_FILM_URL} type="video/mp4"/>
    Your browser does not support this native MP4 replay.
  </video>;
}

export function StorySequence({phase, onPhase, paused}:{phase:StoryPhaseKey;onPhase:(key:StoryPhaseKey)=>void;paused:boolean}) {
  const active=STORY_PHASES.findIndex(item=>item.key===phase);
  return <div className="sequence-layout">
    <ol className="sequence-list" aria-label="Evidence path sequence">
      {STORY_PHASES.map((item,index)=><li key={item.key} className={index===active?'is-active':''} data-past={index<active}>
        <button type="button" className="sequence-button" aria-current={index===active?'step':undefined} aria-label={item.short} onClick={()=>onPhase(item.key)}>
          <span className="sequence-number">0{index+1}</span><span className="sequence-text"><strong>{item.name}</strong><small>{item.status}</small></span><span className="sequence-dot" aria-hidden="true"/>
        </button>
        {index<STORY_PHASES.length-1&&<span className="sequence-line" aria-hidden="true"/>}
      </li>)}
    </ol>
    <article className="sequence-detail" aria-live="polite" key={phase}>
      <div className="sequence-detail-top"><span className="sequence-serial">SEQUENCE / 0{active+1}</span><span className="sequence-wire" aria-hidden="true">◦──────◦</span></div>
      <span className="section-kicker"><span className="kicker-rule"/> {STORY_PHASES[active]!.status}</span>
      <h3>{STORY_PHASES[active]!.name}</h3>
      <p>{STORY_PHASES[active]!.description}</p>
      {phase==='release'&&<p className="truth-note"><Radio size={15}/> The recorded event uses a scripted configured demo-owner identity. It is not a human-authenticated approval.</p>}
      <p className="film-title"><Play size={12} fill="currentColor"/> Native simulation replay below. This mechanism drawing is illustrative.</p>
      <span className="motion-status" data-paused={paused}>{paused?'Motion paused':'State path remains operator-controlled'}</span>
    </article>
  </div>;
}
