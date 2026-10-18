import { useEffect } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Lenis from 'lenis';

gsap.registerPlugin(ScrollTrigger);
export function useSiteMotion(paused:boolean){
 useEffect(()=>{
  const reduce=window.matchMedia('(prefers-reduced-motion: reduce)');
  const coarse=window.matchMedia('(pointer: coarse)').matches||navigator.maxTouchPoints>0;
  const reflectPreference=()=>document.documentElement.classList.toggle('motion-reduced',reduce.matches);
  let lenis:Lenis|undefined;let stopLenis=()=>{};let context:gsap.Context|undefined;
  const teardown=()=>{context?.revert();context=undefined;stopLenis();stopLenis=()=>{};};
  const setup=()=>{
   reflectPreference();
   teardown();
   if(paused||reduce.matches)return;
   if(!coarse){lenis=new Lenis({duration:1.02,lerp:.075,smoothWheel:true,syncTouch:false,anchors:{offset:-88},prevent:element=>element.closest('[data-native-scroll]')!==null});const tick=(time:number)=>lenis?.raf(time*1000);gsap.ticker.add(tick);gsap.ticker.lagSmoothing(500,33);stopLenis=()=>{gsap.ticker.remove(tick);lenis?.destroy();lenis=undefined;};}
   context=gsap.context(()=>{
    gsap.matchMedia().add('(min-width: 761px)',()=>gsap.fromTo('.hero-copy > *',{y:18,autoAlpha:0},{y:0,autoAlpha:1,duration:.68,stagger:.06,ease:'power2.out',clearProps:'transform,opacity,visibility'}));
    const mm=gsap.matchMedia();
    mm.add('(min-width: 761px)',()=>{
      gsap.fromTo('.hero-art-background',{y:18,rotate:1.2,scale:1.025},{y:-22,rotate:-.5,scale:1,duration:1,ease:'none',scrollTrigger:{trigger:'.wf-hero',start:'top top',end:'bottom top',scrub:.65}});
      gsap.fromTo('.story-image img',{scale:1.07,y:18},{scale:1,y:-12,ease:'none',scrollTrigger:{trigger:'.operational-story',start:'top bottom',end:'bottom top',scrub:.6}});
      gsap.from('.closing-engraving',{x:-60,opacity:.3,ease:'none',scrollTrigger:{trigger:'.closing-section',start:'top bottom',end:'top 20%',scrub:.6}});
    });
    gsap.utils.toArray<HTMLElement>('.applications-intro,.evidence-heading,.pathway-heading,.faq-heading').forEach(el=>gsap.from(el,{y:24,duration:.7,ease:'power3.out',scrollTrigger:{trigger:el,start:'top 90%',once:true},clearProps:'all'}));
    gsap.from('.story-sequence i',{scaleX:0,transformOrigin:'left center',stagger:.18,duration:.65,ease:'power2.inOut',scrollTrigger:{trigger:'.story-sequence',start:'top 92%',once:true}});
    gsap.utils.toArray<HTMLElement>('[data-reveal]').forEach(target=>gsap.fromTo(target,{y:14,autoAlpha:0},{y:0,autoAlpha:1,duration:.52,ease:'power2.out',clearProps:'transform,opacity,visibility',scrollTrigger:{trigger:target,start:'top 90%',once:true}}));
   },document.body);
  };
  setup();reduce.addEventListener('change',setup);
  return()=>{reduce.removeEventListener('change',setup);teardown();};
 },[paused]);
}
