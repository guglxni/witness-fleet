import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { gsap } from 'gsap';
import Lenis from 'lenis';

gsap.registerPlugin(ScrollTrigger);
export function attachSiteMotion(){
 const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
 const coarse=window.matchMedia('(pointer: coarse)').matches||navigator.maxTouchPoints>0;
 if(reduced.matches)return{revert:()=>{}};
 let smooth:Lenis|undefined;let stopSmooth=()=>{};
 if(!coarse){smooth=new Lenis({duration:1.02,lerp:.075,smoothWheel:true,syncTouch:false,anchors:{offset:-88},prevent:element=>element.closest('[data-native-scroll]')!==null});const tick=(time:number)=>smooth?.raf(time*1000);gsap.ticker.add(tick);gsap.ticker.lagSmoothing(500,33);stopSmooth=()=>{gsap.ticker.remove(tick);smooth?.destroy();};}
 const context=gsap.context(()=>{
  gsap.matchMedia().add('(min-width: 761px)',()=>gsap.fromTo('.hero-copy > *',{y:24,autoAlpha:0},{y:0,autoAlpha:1,duration:.72,stagger:.07,ease:'power2.out',clearProps:'transform,opacity,visibility'}));
  gsap.utils.toArray<HTMLElement>('[data-reveal]').forEach(target=>gsap.fromTo(target,{y:18,autoAlpha:0},{y:0,autoAlpha:1,duration:.56,ease:'power2.out',clearProps:'transform,opacity,visibility',scrollTrigger:{trigger:target,start:'top 89%',once:true}}));
 },document.body);
 return{revert(){context.revert();stopSmooth();}};
}
