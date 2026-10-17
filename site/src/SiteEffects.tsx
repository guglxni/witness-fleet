import { useEffect } from 'react';
import { useVantaBackground } from './useVantaBackground';

export function SiteEffects(){
 const {hostRef}=useVantaBackground(false);
 useEffect(()=>{
  const importer=import('./motion');let ctx:{revert:()=>void}|undefined;let cancelled=false;
  void importer.then(({attachSiteMotion})=>{if(!cancelled)ctx=attachSiteMotion();});
  return()=>{cancelled=true;ctx?.revert();};
 },[]);
 return <span aria-hidden="true" className="effects-anchor" ref={hostRef}/>;
}
