import { describe,expect,it,vi } from 'vitest';
import { mountNetworkAtmosphere } from '../src/vantaBackground';

function setMotion(reduced:boolean,coarse=false){
 const current=new Set<(event:MediaQueryListEvent)=>void>();
 const listeners=new Set<(event:MediaQueryListEvent)=>void>();
 Object.defineProperty(window,'matchMedia',{configurable:true,value:vi.fn((query:string)=>({matches:query.includes('reduced-motion')?reduced:query.includes('pointer: fine')?!coarse:false,media:query,addEventListener:(_type:string,fn:(event:MediaQueryListEvent)=>void)=>listeners.add(fn),removeEventListener:(_type:string,fn:(event:MediaQueryListEvent)=>void)=>listeners.delete(fn),dispatchEvent:()=>true,onchange:null,addListener:()=>{},removeListener:()=>{},}))});
 return{listeners,current};
}

describe('network-atmosphere boundaries',()=>{
 it('does not schedule WebGL in reduced motion or on coarse pointers',()=>{
  const schedule=vi.spyOn(window,'requestIdleCallback').mockImplementation(()=>0 as number);
  setMotion(true);mountNetworkAtmosphere(document.createElement('div'));expect(schedule).not.toHaveBeenCalled();
  setMotion(false,true);mountNetworkAtmosphere(document.createElement('div'));expect(schedule).not.toHaveBeenCalled();
 });
});
