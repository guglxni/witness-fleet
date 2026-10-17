import { useEffect } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Lenis from 'lenis';

gsap.registerPlugin(ScrollTrigger);
export function useSiteMotion(paused:boolean){
 useEffect(()=>{
  if(paused||window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  const coarse=window.matchMedia('(pointer: coarse)').matches||navigator.maxTouchPoints>0;
  let lenis:Lenis|undefined;let stopLenis=()=>{};
  if(!coarse){lenis=new Lenis({duration:1.02,lerp:.075,smoothWheel:true,syncTouch:false,anchors:{offset:-88},prevent:element=>element.closest('[data-native-scroll]')!==null});const tick=(time:number)=>lenis?.raf(time*1000);gsap.ticker.add(tick);gsap.ticker.lagSmoothing(500,33);stopLenis=()=>{gsap.ticker.remove(tick);lenis?.destroy();};}
  const context=gsap.context(()=>{
   gsap.matchMedia().add('(min-width: 761px)',()=>gsap.fromTo('.hero-copy > *',{y:24,autoAlpha:0},{y:0,autoAlpha:1,duration:.72,stagger:.07,ease:'power2.out',clearProps:'transform,opacity,visibility'}));
   gsap.utils.toArray<HTMLElement>('[data-reveal]').forEach(target=>gsap.fromTo(target,{y:18,autoAlpha:0},{y:0,autoAlpha:1,duration:.56,ease:'power2.out',clearProps:'transform,opacity,visibility',scrollTrigger:{trigger:target,start:'top 89%',once:true}}));
  },document.body);
  return()=>{context.revert();stopLenis();};
 },[paused]);
}
