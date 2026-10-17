import { useEffect, useState } from 'react';
export function useReducedMotion(){const[reduced,setReduced]=useState(true);useEffect(()=>{const media=window.matchMedia('(prefers-reduced-motion: reduce)');setReduced(media.matches);const change=()=>setReduced(media.matches);media.addEventListener('change',change);return()=>media.removeEventListener('change',change);},[]);return reduced;}
