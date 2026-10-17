import { useEffect, useRef, useState } from 'react';
import type { VantaEffect } from 'vanta/dist/vanta.net.min.js';

type NetworkEffectFactory=(options:Record<string,unknown>)=>VantaEffect;
export function Atmosphere({paused}:{paused:boolean}){
 const host=useRef<HTMLDivElement>(null);const effect=useRef<VantaEffect | undefined>(undefined);const[enabled,setEnabled]=useState(false);
 useEffect(()=>{
  const node=host.current;const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');const precise=window.matchMedia('(pointer: fine)');
  if(!node||paused||reduced.matches||!precise.matches||!('WebGLRenderingContext'in window))return;
  let alive=true;let idleId:number|undefined;
  const schedule=window.requestIdleCallback??((callback:IdleRequestCallback)=>window.setTimeout(()=>callback({didTimeout:false,timeRemaining:()=>0}),250));
  idleId=schedule(async()=>{
   try{
    const[THREE,{default:moduleDefault}]=await Promise.all([import('three'),import('vanta/dist/vanta.net.min.js')]);
    const factory=moduleDefault as unknown as {default:NetworkEffectFactory};if(!alive||reduced.matches)return;
    effect.current=factory.default({el:node,THREE,mouseControls:false,touchControls:false,gyroControls:false,minHeight:280,minWidth:280,scale:1,scaleMobile:1,color:0x697957,backgroundColor:0xf5f2ea,points:7,maxDistance:20,spacing:18,showDots:false,speed:.18,backgroundAlpha:0,resize:true});setEnabled(true);
   }catch{/* paper, grid and gradients stay as the no-WebGL fallback */}
  });
  const dispose=()=>{alive=false;if(idleId!==undefined){if(window.cancelIdleCallback)window.cancelIdleCallback(idleId);else window.clearTimeout(idleId);}effect.current?.destroy();effect.current=undefined;if(node)node.replaceChildren();setEnabled(false);};
  reduced.addEventListener('change',()=>{if(reduced.matches)dispose();});
  return dispose;
 },[paused]);
 return <><div className="vanta-surface" data-enabled={enabled} aria-hidden="true" ref={host}/><span className="sr-only">Atmosphere uses a local network visualization when WebGL is available; the paper grid remains when it is not.</span></>;
}
