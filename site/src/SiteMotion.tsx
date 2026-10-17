import { useEffect } from 'react';
import { useReducedMotion } from './useReducedMotion';

export function SiteMotion({paused}:{paused:boolean}){
 const reduced=useReducedMotion();
 useEffect(()=>{
  if(reduced||paused)return;
  let alive=true;let dispose=()=>{};let idleId:number|undefined;
  const schedule=window.requestIdleCallback??((cb:IdleRequestCallback)=>window.setTimeout(()=>cb({didTimeout:false,timeRemaining:()=>0}),180));
  idleId=schedule(()=>{
   void import('./motion').then(({attachSiteMotion})=>{
    if(!alive)return;
    const controller=attachSiteMotion();dispose=()=>controller.revert();
   }).catch(()=>undefined);
  });
  return()=>{alive=false;if(idleId!==undefined){if(window.cancelIdleCallback)window.cancelIdleCallback(idleId);else window.clearTimeout(idleId);}dispose();};
 },[paused,reduced]);
 return null;
}
