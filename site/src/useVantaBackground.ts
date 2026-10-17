import { useEffect, useRef, useState } from 'react';
import type { VantaEffect } from 'vanta/dist/vanta.net.min.js';
type NetFactory=(options:Record<string,unknown>)=>VantaEffect;
export function useVantaBackground(enabled:boolean){
 const hostRef=useRef<HTMLDivElement>(null);const[supported,setSupported]=useState(false);
 useEffect(()=>{
  const host=hostRef.current;const motion=matchMedia('(prefers-reduced-motion: reduce)');const precision=matchMedia('(pointer: fine)');
  if(!host||!enabled||motion.matches||!precision.matches||!('WebGLRenderingContext'in window))return;
  let alive=true;let effect:VantaEffect|undefined;
  const timer=setTimeout(async()=>{
   try{const[THREE,module]=await Promise.all([import('three'),import('vanta/dist/vanta.net.min.js')]);if(!alive||motion.matches)return;
    const raw=module.default;const NET=(typeof raw==='function'?raw:(raw as unknown as {default:NetFactory}).default) as NetFactory;
    effect=NET({el:host,THREE,mouseControls:false,touchControls:false,gyroControls:false,minHeight:280,minWidth:280,scale:1,scaleMobile:1,color:0x697957,backgroundColor:0xf5f2ea,points:6,maxDistance:20,spacing:20,showDots:false,backgroundAlpha:0});setSupported(true);
   }catch{setSupported(false);}
  },350);
  const dispose=()=>{alive=false;clearTimeout(timer);effect?.destroy();effect=undefined;host.replaceChildren();setSupported(false);};
  motion.addEventListener('change',dispose);return()=>{motion.removeEventListener('change',dispose);dispose();};
 },[enabled]);return{hostRef,supported};
}
