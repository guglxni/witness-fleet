import * as THREE from 'three';
import type { VantaEffect } from 'vanta/dist/vanta.net.min.js';

let THREEPromise:Promise<typeof THREE>|undefined;
let NETPromise:Promise<(options:Record<string,unknown>)=>VantaEffect>|undefined;

export function mountNetworkAtmosphere(host:HTMLElement,enabled=true){
 const still=window.matchMedia('(prefers-reduced-motion: reduce)');
 const precise=window.matchMedia('(pointer: fine)');
 if(!enabled||still.matches||!precise.matches||!('WebGLRenderingContext'in window))return()=>{};
 let mounted=false;let disposed=false;let effect:VantaEffect|undefined;let idleId:number|undefined;
 const schedule=window.requestIdleCallback??((cb:IdleRequestCallback)=>window.setTimeout(()=>cb({didTimeout:false,timeRemaining:()=>0}),250));
 idleId=schedule(async()=>{
  try{
   THREEPromise??=Promise.resolve(THREE);
   NETPromise??=import('vanta/dist/vanta.net.min.js').then(module=>(module.default as unknown as {default:(options:Record<string,unknown>)=>VantaEffect}).default);
   const[three,net]=await Promise.all([THREEPromise,NETPromise]);if(disposed||still.matches)return;
   effect=net({el:host,THREE:three,mouseControls:false,touchControls:false,gyroControls:false,minHeight:280,minWidth:280,scale:1,scaleMobile:1,color:0x6d7b53,backgroundColor:0xf5f2ea,points:7,maxDistance:20,spacing:18,showDots:false,speed:.2,backgroundAlpha:0,resize:true});mounted=true;
  }catch{/* warm-paper and CSS-grid fallbacks remain visible */}
 });
 const clean=()=>{disposed=true;if(idleId!==undefined){if(window.cancelIdleCallback)window.cancelIdleCallback(idleId);else window.clearTimeout(idleId);}if(effect){effect.destroy();effect=undefined;}if(mounted){mounted=false;host.replaceChildren();}};
 still.addEventListener('change',clean);
 return()=>{still.removeEventListener('change',clean);clean();};
}
