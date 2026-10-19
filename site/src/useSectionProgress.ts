import {useEffect, useRef, useState} from 'react';

const sectionIds = ['judge','applications','falkordb','evidence','film','pilot'];

/** One passive, frame-throttled read; never writes URL or scrolling position. */
export function useSectionProgress() {
  const [activeSection,setActiveSection] = useState('');
  const progressRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const span = document.documentElement.scrollHeight - window.innerHeight;
      const fraction = span > 0 ? Math.min(1,Math.max(0,window.scrollY / span)) : 0;
      if(progressRef.current) progressRef.current.style.width = `${fraction * 100}%`;
      const visible = sectionIds.map(id => ({id,box:document.getElementById(id)?.getBoundingClientRect()}))
        .filter(item => item.box && item.box.top < window.innerHeight * .45 && item.box.bottom > 120)
        .sort((a,b)=>Math.abs(a.box!.top-120)-Math.abs(b.box!.top-120));
      setActiveSection(visible[0]?.id || '');
    };
    const schedule = () => {if(!frame) frame=requestAnimationFrame(update);};
    window.addEventListener('scroll',schedule,{passive:true});
    window.addEventListener('resize',schedule);
    const resize = new ResizeObserver(schedule);
    resize.observe(document.body);
    schedule();
    return () => {cancelAnimationFrame(frame);resize.disconnect();window.removeEventListener('scroll',schedule);window.removeEventListener('resize',schedule);};
  },[]);
  return {activeSection,progressRef};
}
