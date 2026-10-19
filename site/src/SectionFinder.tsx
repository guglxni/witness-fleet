import {useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {ArrowDownRight, Search, X} from 'lucide-react';
import './section-finder.css';

const destinations = [
 {id:'judge',title:'Start here',detail:'Choose the simulation, source code, or recorded film.',tags:'overview introduction'},
 {id:'falkordb',title:'FalkorDB graph explorer',detail:'Inspect the schema, Cypher and execution boundaries.',tags:'nodes relationships database graph'},
 {id:'evidence',title:'Evidence chain',detail:'Explore the five phases behind an accountable move.',tags:'proof phase mechanism'},
 {id:'recorded-evidence',title:'Recorded evidence',detail:'Search retained task and command receipts.',tags:'proof snapshots data record'},
 {id:'film',title:'Product film',detail:'Watch Witness Fleet × FalkorDB on YouTube.',tags:'video movie'},
 {id:'applications',title:'Applications',detail:'Explore proposed factory, warehouse and campus workflows.',tags:'industry use cases'},
 {id:'value-model',title:'Value worksheet',detail:'An explicitly hypothetical workflow calculation.',tags:'calculate cost economics'},
 {id:'pilot',title:'Pilot path',detail:'Scope a bounded evaluation and its validation needs.',tags:'integration deployment'},
 {id:'faq',title:'Questions & boundaries',detail:'What is demonstrated, and what is not.',tags:'help faq limits'},
];

export function SectionFinder(){
 const [open,setOpen]=useState(false);
 const [query,setQuery]=useState('');
 const trigger=useRef<HTMLButtonElement>(null);
 const dialog=useRef<HTMLDivElement>(null);
 const input=useRef<HTMLInputElement>(null);
 const close=(restore=true)=>{setOpen(false);setQuery('');if(restore)trigger.current?.focus();};
 useEffect(()=>{
  const keydown=(event:KeyboardEvent)=>{
   const target=event.target;
   const editing=target instanceof HTMLElement&&(target.matches('input,textarea,select')||target.isContentEditable);
   if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'&&!editing){event.preventDefault();if(open)close();else setOpen(true);}
  };
  document.addEventListener('keydown',keydown);
  return()=>document.removeEventListener('keydown',keydown);
 },[open]);
 useEffect(()=>{
  if(!open)return;
  input.current?.focus();
  const priorOverflow=document.body.style.overflow;
  document.body.style.overflow='hidden';
  const keydown=(event:KeyboardEvent)=>{
   if(event.key==='Escape'){event.preventDefault();close();return;}
   if(event.key!=='Tab')return;
   const focusable=Array.from(dialog.current?.querySelectorAll<HTMLElement>('button,a[href],input')??[]);
   const first=focusable[0],last=focusable.at(-1);
   if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
   else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
  };
  document.addEventListener('keydown',keydown);
  return()=>{document.body.style.overflow=priorOverflow;document.removeEventListener('keydown',keydown);};
 },[open]);
 const matches=destinations.filter(item=>`${item.title} ${item.detail} ${item.tags}`.toLowerCase().includes(query.trim().toLowerCase()));
 return <>
  <button ref={trigger} type="button" className="section-finder-trigger" aria-label="Find a section" aria-haspopup="dialog" onClick={()=>setOpen(true)}><Search size={16}/><span>Explore</span><kbd>⌘ K</kbd></button>
  {open&&createPortal(<div className="section-finder-backdrop" onMouseDown={event=>{if(event.target===event.currentTarget)close();}}>
   <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby="section-finder-title" className="section-finder-dialog">
    <div className="section-finder-heading"><span id="section-finder-title">Explore Witness Fleet</span><button type="button" aria-label="Close section finder" onClick={()=>close()}><X size={18}/></button></div>
    <label className="section-finder-search"><Search size={20}/><input ref={input} type="search" aria-label="Search sections" placeholder="Graph, evidence, simulation…" value={query} onChange={event=>setQuery(event.target.value)}/><kbd>ESC</kbd></label>
    <div className="section-finder-results">{matches.map((item,index)=><a key={item.id} href={`#${item.id}`} onClick={()=>{close(false);requestAnimationFrame(()=>{const el=document.getElementById(item.id);if(el){el.tabIndex=-1;el.focus({preventScroll:true});}});}}><span className="section-finder-index">{String(index+1).padStart(2,'0')}</span><span><strong>{item.title}</strong><small>{item.detail}</small></span><ArrowDownRight size={18}/></a>)}{matches.length===0&&<p className="section-finder-empty">No matching section. Try graph, evidence, or film.</p>}</div>
    <p className="section-finder-footer">Navigate this page · no mission action is performed</p>
   </div>
  </div>,document.body)}
 </>;
}
